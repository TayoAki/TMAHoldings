"""The Claude Code workflow scripts, run with scripted agents against a real workspace.

These prove the orchestration logic (what runs when, what gets recorded, how a machine-check
veto feeds back into the next draft) without spending model calls. The live run with real
Claude agents is described in docs/PLAYBOOK.md ("How this was proven").
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import unittest

from holdco import corrections, golden, jobs
from holdco.diffing import set_path
from holdco.util import freeze_clock, parse_date
from tests.helpers import DANA, HUMAN, PASS, REPO, WorkspaceCase

WORKFLOWS = REPO / ".claude" / "workflows"
HARNESS = REPO / "tests" / "workflows" / "harness.mjs"
MOCK = REPO / "tests" / "workflows" / "mock_agent.py"
NODE = shutil.which("node")


@unittest.skipUnless(NODE, "node is needed to run the workflow scripts")
class Workflows(WorkspaceCase):
    def run_workflow(self, name: str, args: dict, env: dict | None = None) -> dict:
        result = subprocess.run([NODE, str(HARNESS), str(WORKFLOWS / f"{name}.js"), json.dumps(args),
                                 sys.executable, str(MOCK)], cwd=REPO, capture_output=True, text=True,
                                timeout=300, env={**os.environ, **(env or {})})
        self.assertEqual(result.returncode, 0, result.stderr[-3000:])
        data = json.loads(result.stdout)
        titles = {p["title"] for p in data["meta"].get("phases", [])}
        self.assertTrue(set(data["phasesUsed"]) <= titles, (data["phasesUsed"], titles))
        return data

    def job_args(self, job: dict) -> dict:
        return {"business": self.biz.slug, "job": job["id"], "state": job["state"], "drafts": len(job["drafts"])}

    def test_process_job_blocks_then_passes_and_stops_at_approval(self):
        job = self.new_job("2026-06")
        job = jobs.add_inputs(self.biz, job["id"], self.inbox / "2026-06-acme-late-receipts")
        data = self.run_workflow("holdco-process-job", {"root": str(self.tmp), "jobs": [self.job_args(job)]})
        self.assertEqual([c["role"] for c in data["calls"]],
                         ["intake", "preparer", "reviewer", "clerk", "preparer", "reviewer", "clerk"])
        final = self.job(job["id"])
        self.assertEqual(final["state"], jobs.AWAITING_APPROVAL)
        self.assertEqual([r["verdict"] for r in final["reviews"]], ["BLOCK", "PASS"])
        self.assertIsNone(final["approval"])
        self.assertFalse((self.biz.outbox_dir / job["id"]).exists())

    def test_machine_checks_veto_a_lenient_reviewer_and_feed_the_next_draft(self):
        job = self.new_job("2026-06")
        job = jobs.add_inputs(self.biz, job["id"], self.inbox / "2026-06-acme-late-receipts")
        data = self.run_workflow("holdco-process-job", {"root": str(self.tmp), "jobs": [self.job_args(job)]},
                                 env={"MOCK_REVIEWER": "lenient"})
        steps = data["out"]["processed"][0]["steps"]
        self.assertIn("machine checks blocked it", steps[1])
        final = self.job(job["id"])
        self.assertEqual(final["state"], jobs.AWAITING_APPROVAL)
        self.assertEqual([e["id"] for e in jobs.latest_draft(self.biz, final)["data"]["excluded"]], ["T-0611"])

    def test_missing_documents_give_a_reviewed_chase(self):
        job = self.new_job("2026-06")
        data = self.run_workflow("holdco-process-job", {"root": str(self.tmp), "jobs": [self.job_args(job)]})
        self.assertEqual([c["role"] for c in data["calls"]], ["intake", "reviewer", "clerk"])
        parent = self.job(job["id"])
        self.assertEqual(parent["state"], jobs.WAITING_ON_CLIENT)
        self.assertEqual(self.job(parent["children"][0])["state"], jobs.AWAITING_APPROVAL)

    def test_preparer_question_parks_the_job_for_a_person(self):
        job = self.new_job("2026-07")
        self.run_workflow("holdco-process-job", {"root": str(self.tmp), "jobs": [self.job_args(job)]})
        final = self.job(job["id"])
        self.assertEqual(final["state"], jobs.NEEDS_HUMAN)
        self.assertEqual(final["questions"][-1]["key"], "T-0706")

    def test_several_jobs_run_in_parallel(self):
        a, b = self.new_job("2026-08"), self.new_job("2026-07")
        data = self.run_workflow("holdco-process-job", {"root": str(self.tmp),
                                                        "jobs": [self.job_args(a), self.job_args(b)]})
        states = {p["job"]: p["state"] for p in data["out"]["processed"]}
        self.assertEqual(states, {a["id"]: "awaiting_approval", b["id"]: "needs_human"})

    def _two_months_of_home_depot_fixes(self) -> None:
        for period, when in (("2026-06", "2026-07-03T09:00:00"), ("2026-07", "2026-08-04T09:00:00")):
            freeze_clock(when)
            job = self.new_job(period)
            if period == "2026-06":
                jobs.add_inputs(self.biz, job["id"], self.inbox / "2026-06-acme-late-receipts")
            job = self.runner().process(job["id"])["job"]
            if job["state"] == jobs.NEEDS_HUMAN:
                jobs.answer(self.biz, job["id"], "Owner's Draw", DANA, HUMAN)
                job = self.runner().process(job["id"])["job"]
            final = jobs.latest_draft(self.biz, job)
            for txn in final["data"]["transactions"]:
                if "HOME DEPOT" in txn["description"]:
                    final = set_path(final, f"data.transactions[{txn['id']}].category", "Materials (COGS)")
            jobs.approve(self.ws, self.biz, job["id"], DANA, HUMAN, passphrase=PASS, final=final, default_reason="client_preference")

    def test_weekly_review_records_the_repeat_for_a_person(self):
        self._two_months_of_home_depot_fixes()
        data = self.run_workflow("holdco-weekly-review", {"root": str(self.tmp), "business": self.biz.slug,
                                                          "asOf": "2026-08-05"})
        self.assertEqual(data["out"]["exact_repeat_proposals"], ["P-0001"])
        self.assertEqual(corrections.list_proposals(self.biz, "proposed")[0]["check"]["match"], "HOME DEPOT")

    def test_eval_workflow_reruns_the_agents_on_golden_cases(self):
        self._two_months_of_home_depot_fixes()
        report = corrections.review(self.ws, self.biz, as_of=parse_date("2026-08-05"))
        accepted = corrections.accept_proposal(self.ws, self.biz, report["new_proposals"][0]["id"], DANA, HUMAN)
        data = self.run_workflow("holdco-eval", {"root": str(self.tmp), "business": self.biz.slug,
                                                 "cases": accepted["golden_cases"]})
        self.assertEqual((data["out"]["passed"], data["out"]["failed"]), (2, 0))
        self.assertEqual(jobs.list_jobs(self.biz, jobs.AWAITING_APPROVAL), [])  # eval jobs stay out of the queue
        self.assertEqual(len(golden.list_cases(self.biz)), 2)

    def test_deal_screen_writes_a_memo(self):
        data = self.run_workflow("holdco-deal-screen", {"root": str(self.tmp),
                                                        "deal": "thesis/deals/example-target.json"})
        self.assertEqual(data["out"]["numbers"]["verdict"], "NEGOTIATE")
        self.assertEqual(len(data["out"]["lens_scores"]), 4)
        self.assertTrue((self.tmp / "thesis/deals/example-target.memo.md").exists())


if __name__ == "__main__":
    unittest.main()
