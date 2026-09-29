"""Shadow mode: the first 30 days change nothing a client can see."""

from __future__ import annotations

from holdco import corrections, jobs, metrics, rollout
from holdco.config import HoldcoError
from holdco.diffing import set_path
from holdco.guard import HumanOnlyError
from holdco.util import freeze_clock, parse_date, read_json
from tests.helpers import AGENT, DANA, HUMAN, WorkspaceCase


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
            jobs.approve(self.ws, self.biz, job["id"], DANA, HUMAN)
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
