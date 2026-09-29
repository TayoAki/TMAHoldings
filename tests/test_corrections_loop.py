"""Corrections -> proposed rules -> accepted rules -> regression tests."""

from __future__ import annotations

import unittest

from holdco import corrections, golden, jobs
from holdco.config import HoldcoError
from holdco.diffing import set_path
from holdco.guard import HumanOnlyError
from holdco.rules import RuleSet
from holdco.util import freeze_clock, parse_date
from tests.helpers import AGENT, DANA, HUMAN, WorkspaceCase

MATERIALS = "Materials (COGS)"


class VendorKey(unittest.TestCase):
    def test_vendor_keys(self):
        self.assertEqual(corrections.vendor_key("HOME DEPOT #4410"), "HOME DEPOT")
        self.assertEqual(corrections.vendor_key("ONLINE TRANSFER TO J SMITH"), "J SMITH")
        self.assertEqual(corrections.vendor_key("SHELL OIL 57442"), "SHELL OIL")
        self.assertEqual(corrections.vendor_key("POS AMZN MKTP US*2K4"), "AMZN MKTP")


class Loop(WorkspaceCase):
    def _approve_with_home_depot_fix(self, period: str, when: str) -> dict:
        freeze_clock(when)
        job = self.new_job(period)
        if period == "2026-06":
            jobs.add_inputs(self.biz, job["id"], self.inbox / "2026-06-acme-late-receipts")
        job = self.runner().process(job["id"])["job"]
        if job["state"] == jobs.NEEDS_HUMAN:
            jobs.answer(self.biz, job["id"], "Owner's Draw", DANA, HUMAN)
            job = self.runner().process(job["id"])["job"]
        draft = jobs.latest_draft(self.biz, job)
        final = draft
        for txn in draft["data"]["transactions"]:
            if "HOME DEPOT" in txn["description"]:
                final = set_path(final, f"data.transactions[{txn['id']}].category", MATERIALS)
        return jobs.approve(self.ws, self.biz, job["id"], DANA, HUMAN, final=final,
                            default_reason="client_preference", minutes=10)

    def test_full_loop(self):
        self._approve_with_home_depot_fix("2026-06", "2026-07-03T09:00:00")
        first = corrections.review(self.ws, self.biz, as_of=parse_date("2026-07-08"))
        self.assertEqual(first["new_proposals"], [])
        self.assertEqual(len(first["watch"]), 1)

        self._approve_with_home_depot_fix("2026-07", "2026-08-04T09:00:00")
        second = corrections.review(self.ws, self.biz, as_of=parse_date("2026-08-05"))
        self.assertEqual(len(second["new_proposals"]), 1)
        proposal = second["new_proposals"][0]
        self.assertEqual(proposal["check"], {"type": "vendor_category", "match": "HOME DEPOT", "category": MATERIALS})
        self.assertEqual(proposal["scope"], "client:acme")
        self.assertEqual(len(proposal["evidence_jobs"]), 2)

        again = corrections.review(self.ws, self.biz, as_of=parse_date("2026-08-05"))
        self.assertEqual(again["new_proposals"], [])
        self.assertEqual(again["already_proposed"][0]["proposal"], proposal["id"])

        with self.assertRaises(HumanOnlyError):
            corrections.accept_proposal(self.ws, self.biz, proposal["id"], DANA, AGENT)
        accepted = corrections.accept_proposal(self.ws, self.biz, proposal["id"], DANA, HUMAN)
        rule = RuleSet.for_business(self.ws, self.biz).get(accepted["rule_id"])
        self.assertIsNotNone(rule)
        self.assertEqual(rule.client, "acme")
        self.assertEqual(len(accepted["golden_cases"]), 2)
        with self.assertRaises(HoldcoError):
            corrections.accept_proposal(self.ws, self.biz, proposal["id"], DANA, HUMAN)

        passing = golden.run_eval(self.ws, self.biz, self.runner())
        self.assertEqual((passing["passed"], passing["failed"]), (2, 0))
        failing = golden.run_eval(self.ws, self.biz, self.runner(exclude={accepted["rule_id"]}))
        self.assertEqual(failing["passed"], 0)
        paths = {d["path"] for case in failing["cases"] for d in case["differences"]}
        self.assertTrue(all(p.startswith("categories.") for p in paths), paths)

    def test_a_rule_that_exists_but_was_ignored_is_reported_not_re_proposed(self):
        (self.biz.rules_file).write_text(self.biz.rules_file.read_text() + """
## R-DEMO-050 · Acme: Shell is Vehicle Fuel
- **Applies to:** monthly-close
- **Scope:** client:acme
- **Rule:** Categorize SHELL OIL as "Vehicle Fuel" for Acme.
- **Check:** `{"type": "vendor_category", "match": "SHELL OIL", "category": "Vehicle Fuel"}`
""")
        for when in ("2026-07-10T09:00:00", "2026-07-11T09:00:00"):
            freeze_clock(when)
            corrections.log_correction(self.biz, {
                "job": f"job-{when[8:10]}", "job_type": "monthly-close", "client": "acme", "agent": "preparer",
                "kind": "edit", "category": "client_preference", "path": "data.transactions[T-1].category",
                "before": "Fuel", "after": "Vehicle Fuel", "context": {"description": "SHELL OIL 57442"},
                "note": "", "by": DANA})
        report = corrections.review(self.ws, self.biz, as_of=parse_date("2026-07-12"))
        self.assertEqual(report["new_proposals"], [])
        self.assertEqual(report["rule_not_followed"][0]["rule"], "R-DEMO-050")

    def test_repeated_style_fix_becomes_a_no_phrases_rule(self):
        for n, when in enumerate(("2026-07-10T09:00:00", "2026-07-11T09:00:00")):
            freeze_clock(when)
            corrections.log_correction(self.biz, {
                "job": f"job-{n}", "job_type": "monthly-close", "client": "acme", "agent": "preparer",
                "kind": "edit", "category": "style", "path": "client_message.body_markdown#L3",
                "before": "Per our records, your books are closed.", "after": None, "context": {},
                "note": "", "by": DANA})
        report = corrections.review(self.ws, self.biz, as_of=parse_date("2026-07-12"))
        proposal = report["new_proposals"][0]
        self.assertEqual(proposal["check"]["type"], "no_phrases")
        self.assertEqual(proposal["check"]["phrases"], ["per our records, your books are closed."])

    def test_generic_field_fix_needs_wording_before_it_can_be_accepted(self):
        for n, when in enumerate(("2026-07-10T09:00:00", "2026-07-11T09:00:00")):
            freeze_clock(when)
            corrections.log_correction(self.biz, {
                "job": f"job-{n}", "job_type": "monthly-close", "client": "acme", "agent": "preparer",
                "kind": "edit", "category": "factual_error", "path": "data.period",
                "before": "2026-6", "after": "2026-06", "context": {}, "note": "", "by": DANA})
        proposal = corrections.review(self.ws, self.biz, as_of=parse_date("2026-07-12"))["new_proposals"][0]
        with self.assertRaises(HoldcoError):
            corrections.accept_proposal(self.ws, self.biz, proposal["id"], DANA, HUMAN)

    def test_categories_are_validated(self):
        with self.assertRaises(HoldcoError):
            corrections.log_correction(self.biz, {"kind": "edit", "category": "vibes", "path": "x", "by": DANA})
        self.assertEqual(corrections.require_category("c"), "client_preference")


class CuratedProposals(WorkspaceCase):
    def test_agent_proposals_need_real_evidence_and_a_person_to_accept(self):
        job = self.to_approval()
        final = set_path(jobs.latest_draft(self.biz, job), "data.transactions[T-0803].category", "Vehicle Fuel")
        jobs.approve(self.ws, self.biz, job["id"], DANA, HUMAN, final=final, default_reason="client_preference")
        draft = {"title": "Acme: Shell is Vehicle Fuel", "applies_to": "monthly-close", "scope": "client:acme",
                 "rule_text": 'For Acme, categorize SHELL OIL as "Vehicle Fuel".', "why": "Maria asked twice.",
                 "check": {"type": "vendor_category", "match": "SHELL OIL", "category": "Vehicle Fuel"},
                 "evidence": ["C-0001"], "golden_candidates": [job["id"]]}
        with self.assertRaises(HoldcoError):
            corrections.create_proposal(self.ws, self.biz, {**draft, "evidence": ["C-9999"]})
        with self.assertRaises(HoldcoError):
            corrections.create_proposal(self.ws, self.biz, {**draft, "check": {"type": "made_up"}})
        proposal = corrections.create_proposal(self.ws, self.biz, draft)
        with self.assertRaises(HoldcoError):
            corrections.create_proposal(self.ws, self.biz, draft)
        with self.assertRaises(HumanOnlyError):
            corrections.accept_proposal(self.ws, self.biz, proposal["id"], DANA, AGENT)
        accepted = corrections.accept_proposal(self.ws, self.biz, proposal["id"], DANA, HUMAN)
        self.assertEqual(len(accepted["golden_cases"]), 1)
        self.assertEqual(golden.run_eval(self.ws, self.biz, self.runner())["failed"], 0)

    def test_materialized_eval_job_skips_straight_to_ready(self):
        job = self.to_approval()
        jobs.approve(self.ws, self.biz, job["id"], DANA, HUMAN)
        case_id = golden.create_case_from_job(self.ws, self.biz, job["id"], ["R-DEMO-003"])
        eval_job = golden.materialize(self.ws, self.biz, case_id)
        self.assertEqual(eval_job["state"], jobs.READY)
        self.assertEqual(eval_job["eval_case"], case_id)
        done = self.runner().process(eval_job["id"])["job"]
        self.assertTrue(golden.compare_job(self.ws, self.biz, case_id, done["id"])["passed"])
        self.assertNotIn(eval_job["id"], [j["id"] for j in jobs.list_jobs(self.biz)])


if __name__ == "__main__":
    unittest.main()
