"""The path the Claude Code workflow uses: agents write files, the clerk runs `holdco record-run`."""

from __future__ import annotations

from holdco import jobs
from holdco.config import HoldcoError
from holdco.util import read_json, write_json
from tests.helpers import WorkspaceCase


class RecordRun(WorkspaceCase):
    def _agent_draft(self, job: dict, version: int, feedback=None, answers=None) -> str:
        """Stand in for the preparer agent writing work/draft.vN.json."""
        inputs = jobs.job_dir(self.biz, job["id"]) / "input"
        draft = self.runner().prepare("monthly-close", "acme", inputs, job["period"], feedback or [], answers or {})
        rel = f"work/draft.v{version}.json"
        write_json(jobs.job_dir(self.biz, job["id"]) / rel, draft)
        return rel

    def test_clean_run_lands_in_the_approval_queue(self):
        job = self.new_job("2026-08")
        run = {"intake": {"status": "complete", "documents_found": ["bank.csv", "statement.json", "receipts.csv"]},
               "rounds": [{"version": 1, "draft_file": self._agent_draft(job, 1),
                           "review": {"verdict": "PASS", "score": 96, "findings": [], "summary": "Looks right."}}]}
        result = jobs.record_run(self.ws, self.biz, job["id"], run)
        job = result["job"]
        self.assertEqual(job["state"], jobs.AWAITING_APPROVAL)
        self.assertEqual(job["drafts"][0]["author"], "preparer")
        self.assertEqual(len(job["drafts"][0]["sha256"]), 64)
        self.assertEqual(result["summary"], ["intake: complete", "v1: PASS"])

    def test_block_then_pass_over_two_rounds(self):
        job = self.new_job("2026-06")
        jobs.add_inputs(self.biz, job["id"], self.inbox / "2026-06-acme-late-receipts")
        job = self.job(job["id"])
        folder = jobs.job_dir(self.biz, job["id"])
        v1 = self._agent_draft(job, 1)
        findings = self.runner().review("monthly-close", "acme", folder / "input", read_json(folder / v1), {})["findings"]
        v2 = self._agent_draft(job, 2, feedback=findings)
        run = {"intake": {"status": "complete"},
               "rounds": [{"version": 1, "draft_file": v1, "review": {"verdict": "BLOCK", "score": 60, "findings": findings}},
                          {"version": 2, "draft_file": v2, "review": {"verdict": "PASS", "score": 100, "findings": []}}]}
        job = jobs.record_run(self.ws, self.biz, job["id"], run)["job"]
        self.assertEqual([r["verdict"] for r in job["reviews"]], ["BLOCK", "PASS"])
        self.assertEqual(job["state"], jobs.AWAITING_APPROVAL)

    def test_a_pass_on_a_broken_draft_is_still_blocked(self):
        job = self.new_job("2026-06")
        jobs.add_inputs(self.biz, job["id"], self.inbox / "2026-06-acme-late-receipts")
        job = self.job(job["id"])
        run = {"intake": {"status": "complete"},
               "rounds": [{"version": 1, "draft_file": self._agent_draft(job, 1),
                           "review": {"verdict": "PASS", "score": 100, "findings": []}}]}
        job = jobs.record_run(self.ws, self.biz, job["id"], run)["job"]
        self.assertEqual(job["state"], jobs.BLOCKED)
        self.assertEqual(job["reviews"][-1]["findings"][0]["source"], "machine-check")

    def test_missing_documents_create_a_reviewed_chase(self):
        job = self.new_job("2026-06")
        chase = {"subject": "Quick request: 2 items for your June 2026 books",
                 "body_markdown": "Hi Maria,\n\nWe need two receipts:\n\n- Receipt for SHELL OIL 57442 on 2026-06-05 ($96.40)"
                                  "\n- Receipt for GREENLEAF NURSERY on 2026-06-18 ($1,275.50)\n\nThank you!\n— Dana"}
        run = {"intake": {"status": "missing_documents", "chase_message": chase,
                          "missing": [{"document": "receipt:T-0603",
                                       "label": "Receipt for SHELL OIL 57442 on 2026-06-05 ($96.40)"},
                                      {"document": "receipt:T-0608",
                                       "label": "Receipt for GREENLEAF NURSERY on 2026-06-18 ($1,275.50)"}]},
               "chase_review": {"verdict": "PASS", "score": 97, "findings": []}}
        job = jobs.record_run(self.ws, self.biz, job["id"], run)["job"]
        self.assertEqual(job["state"], jobs.WAITING_ON_CLIENT)
        self.assertEqual(self.job(job["children"][0])["state"], jobs.AWAITING_APPROVAL)

    def test_escalation_round(self):
        job = self.new_job("2026-07")
        run = {"intake": {"status": "complete"},
               "rounds": [{"version": 1, "escalation": {"question": "What is the $6,200 transfer to J SMITH?",
                                                        "key": "T-0706",
                                                        "context": {"description": "ONLINE TRANSFER TO J SMITH"}}}]}
        job = jobs.record_run(self.ws, self.biz, job["id"], run)["job"]
        self.assertEqual(job["state"], jobs.NEEDS_HUMAN)
        self.assertEqual(job["questions"][-1]["context"]["description"], "ONLINE TRANSFER TO J SMITH")

    def test_run_without_intake_on_a_fresh_job_is_refused(self):
        job = self.new_job("2026-08")
        with self.assertRaises(HoldcoError):
            jobs.record_run(self.ws, self.biz, job["id"], {"rounds": []})

    def test_invalid_draft_is_refused_with_reasons(self):
        job = self.new_job("2026-08")
        write_json(jobs.job_dir(self.biz, job["id"]) / "work/draft.v1.json", {"job_type": "monthly-close"})
        run = {"intake": {"status": "complete"}, "rounds": [{"version": 1, "draft_file": "work/draft.v1.json"}]}
        with self.assertRaises(HoldcoError) as ctx:
            jobs.record_run(self.ws, self.biz, job["id"], run)
        self.assertIn("missing 'client_message'", str(ctx.exception))
