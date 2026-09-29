"""Shadow mode: until a job type graduates, nothing agents draft can reach a client."""

from __future__ import annotations

from holdco import corrections, jobs, metrics, rollout
from holdco.config import HoldcoError
from holdco.diffing import set_path
from holdco.guard import HumanOnlyError
from holdco.util import freeze_clock, parse_date, read_json
from tests.helpers import AGENT, DANA, HUMAN, OWNER, PASS, WorkspaceCase


class Shadow(WorkspaceCase):
    def setUp(self):
        super().setUp()
        self.set_config(rollout={"monthly-close": "shadow", "document-chase": "shadow"})

    def _shadow_job(self, period: str, when: str, edits: dict, minutes: float) -> dict:
        freeze_clock(when)
        job = self.new_job(period)
        if period == "2026-06":
            jobs.add_inputs(self.biz, job["id"], self.inbox / "2026-06-acme-late-receipts")
        job = self.runner().process(job["id"])["job"]
        if job["state"] == jobs.NEEDS_HUMAN:
            jobs.answer(self.biz, job["id"], "Owner's Draw", DANA, HUMAN)
            job = self.runner().process(job["id"])["job"]
        human = jobs.latest_draft(self.biz, job)
        for path, value in edits.items():
            human = set_path(human, path, value)
        return jobs.shadow_record(self.ws, self.biz, job["id"], DANA, HUMAN, human,
                                  default_reason="client_preference", minutes=minutes)

    def test_shadow_drafts_can_never_be_approved_or_sent(self):
        job = self.to_approval()
        with self.assertRaises(HoldcoError) as ctx:
            jobs.approve(self.ws, self.biz, job["id"], DANA, HUMAN, passphrase=PASS)
        self.assertIn("shadow mode", str(ctx.exception))
        self.assertEqual(self.job(job["id"])["state"], jobs.AWAITING_APPROVAL)

    def test_new_job_types_default_to_shadow(self):
        self.set_config(rollout={})
        self.assertEqual(jobs.rollout_mode(self.biz, "monthly-close"), jobs.SHADOW)

    def test_shadow_compare_logs_differences_and_sends_nothing(self):
        with self.assertRaises(HumanOnlyError):
            jobs.shadow_record(self.ws, self.biz, self.to_approval("2026-08")["id"], DANA, AGENT, {})
        job = self._shadow_job("2026-06", "2026-07-03T09:00:00",
                               {"data.transactions[T-0602].category": "Materials (COGS)"}, minutes=55)
        self.assertEqual(job["state"], jobs.SHADOWED)
        self.assertEqual(job["shadow"]["changes"], 1)
        self.assertFalse(self.biz.outbox_dir.exists() and any(self.biz.outbox_dir.iterdir()))
        entry = corrections.load_corrections(self.biz)[-1]
        self.assertEqual((entry["kind"], entry["after"]), ("shadow", "Materials (COGS)"))
        self.assertTrue((jobs.job_dir(self.biz, job["id"]) / "human-version.json").exists())

    def test_shadow_corrections_feed_the_weekly_review(self):
        self._shadow_job("2026-06", "2026-07-03T09:00:00",
                         {"data.transactions[T-0602].category": "Materials (COGS)"}, minutes=55)
        self._shadow_job("2026-07", "2026-08-04T09:00:00",
                         {"data.transactions[T-0702].category": "Materials (COGS)"}, minutes=50)
        report = corrections.review(self.ws, self.biz, as_of=parse_date("2026-08-05"))
        self.assertEqual(len(report["new_proposals"]), 1)

    def test_graduation_needs_evidence_and_a_person(self):
        self._shadow_job("2026-08", "2026-09-02T09:00:00", {}, minutes=48)
        report = rollout.graduation_report(self.biz, "monthly-close")
        self.assertFalse(report["ready"])
        self.assertIn("only 1 shadow job", report["blocking"][0])
        self.assertEqual(report["manual_minutes_per_job"], 48)
        loose = rollout.graduation_report(self.biz, "monthly-close", criteria={"min_jobs": 1})
        self.assertTrue(loose["ready"])
        with self.assertRaises(HumanOnlyError):
            rollout.set_rollout(self.biz, "monthly-close", "assisted", DANA, AGENT, "ready")
        entry = rollout.set_rollout(self.biz, "monthly-close", "assisted", DANA, HUMAN, "Report ready; GM agrees")
        self.assertEqual((entry["from"], entry["to"]), ("shadow", "assisted"))
        self.assertEqual(read_json(self.biz.dir / "business.json")["rollout"]["monthly-close"], "assisted")

    def test_monday_numbers_show_the_manual_baseline(self):
        self._shadow_job("2026-08", "2026-09-02T09:00:00", {}, minutes=48)
        report = metrics.business_metrics(self.biz, as_of=parse_date("2026-09-28"))
        self.assertEqual(report["shadow"]["manual_minutes_per_job"], 48)
        self.assertIn("manual baseline 48", metrics.format_report(report))

    def test_a_rule_from_shadow_differences_is_tested_against_the_persons_version(self):
        self._shadow_job("2026-06", "2026-07-03T09:00:00",
                         {"data.transactions[T-0602].category": "Materials (COGS)"}, minutes=55)
        self._shadow_job("2026-07", "2026-08-04T09:00:00",
                         {"data.transactions[T-0702].category": "Materials (COGS)"}, minutes=50)
        proposal = corrections.review(self.ws, self.biz, as_of=parse_date("2026-08-05"))["new_proposals"][0]
        accepted = corrections.accept_proposal(self.ws, self.biz, proposal["id"], DANA, HUMAN)
        self.assertEqual(len(accepted["golden_cases"]), 2)
        expected = read_json(self.biz.golden_dir / accepted["golden_cases"][0] / "expected.json")
        categories = {t["id"]: t["category"] for t in expected["data"]["transactions"]}
        self.assertEqual(categories["T-0602"], "Materials (COGS)")

    def test_graduation_starts_over_after_a_rollback(self):
        self._shadow_job("2026-08", "2026-09-02T09:00:00", {}, minutes=48)
        self.assertTrue(rollout.graduation_report(self.biz, "monthly-close", criteria={"min_jobs": 1})["ready"])
        freeze_clock("2026-09-10T09:00:00")
        rollout.set_rollout(self.biz, "monthly-close", "assisted", DANA, HUMAN, "Report ready; GM agrees")
        freeze_clock("2026-09-20T09:00:00")
        rollout.set_rollout(self.biz, "monthly-close", "shadow", DANA, HUMAN, "Incident: wrong totals sent")
        report = rollout.graduation_report(self.biz, "monthly-close", criteria={"min_jobs": 1})
        self.assertEqual(report["shadow_jobs"], 0)
        self.assertFalse(report["ready"])

    def test_a_higher_bar_than_the_window_can_still_be_met(self):
        self.set_config(rollout={"monthly-close": "shadow"}, graduation={"min_jobs": 3})
        for period, when in (("2026-06", "2026-07-03T09:00:00"), ("2026-07", "2026-08-04T09:00:00"),
                             ("2026-08", "2026-09-02T09:00:00")):
            self._shadow_job(period, when, {}, minutes=40)
        report = rollout.graduation_report(self.biz, "monthly-close", last=2)
        self.assertEqual(report["shadow_jobs"], 3)
        self.assertTrue(report["ready"], report["blocking"])

    def test_the_holdco_owner_can_make_the_rollout_call(self):
        entry = rollout.set_rollout(self.biz, "monthly-close", "assisted", OWNER, HUMAN, "GM agrees")
        self.assertEqual(entry["by"], OWNER)
        with self.assertRaises(HumanOnlyError):
            rollout.set_rollout(self.biz, "monthly-close", "shadow", "Someone Else", HUMAN, "no")
