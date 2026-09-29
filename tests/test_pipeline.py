"""The human approval rule and the pipeline invariants."""

from __future__ import annotations

import json
import unittest

from holdco import corrections, jobs
from holdco.config import HoldcoError
from holdco.diffing import set_path
from holdco.guard import ExecutionContext, HumanOnlyError
from holdco.util import read_json, write_json
from tests.helpers import AGENT, DANA, HUMAN, PASS, SCRIPT, WorkspaceCase

AGENT_ROLES = ("intake", "preparer", "reviewer", "system")


class TransitionTable(unittest.TestCase):
    def test_only_humans_can_approve_or_send(self):
        for (src, dst), roles in jobs.TRANSITIONS.items():
            if dst in (jobs.APPROVED, jobs.SENT):
                self.assertEqual(roles, {"human"}, f"{src} -> {dst} must be human-only")

    def test_no_agent_can_reach_approved_or_sent_from_any_state(self):
        for state in jobs.STATES:
            for role in AGENT_ROLES:
                for target in (jobs.APPROVED, jobs.SENT):
                    job = {"id": "x", "state": state}
                    with self.assertRaises((PermissionError, HoldcoError)):
                        jobs.check_transition(job, target, jobs.Actor(role, "any"))

    def test_sent_is_only_reachable_from_approved(self):
        sources = {src for (src, dst) in jobs.TRANSITIONS if dst == jobs.SENT}
        self.assertEqual(sources, {jobs.APPROVED})


class Pipeline(WorkspaceCase):
    def test_clean_job_reaches_the_approval_queue_and_no_further(self):
        job = self.to_approval()
        self.assertEqual(len(job["drafts"]), 1)
        self.assertEqual(job["reviews"][-1]["verdict"], "PASS")
        self.assertFalse((self.biz.outbox_dir / job["id"]).exists())

    def test_agents_cannot_record_each_others_work(self):
        job = self.new_job()
        jobs.record_intake(self.ws, self.biz, job["id"], {"status": "complete"})
        draft = self.runner().prepare("monthly-close", "acme", self.inbox / "2026-08-acme", "2026-08", [], {})
        with self.assertRaises(PermissionError):
            jobs.record_draft(self.ws, self.biz, job["id"], draft, actor=jobs.REVIEWER)
        jobs.record_draft(self.ws, self.biz, job["id"], draft)
        with self.assertRaises(PermissionError):
            jobs.record_review(self.ws, self.biz, job["id"], {"verdict": "PASS"}, actor=jobs.PREPARER)

    def test_send_requires_approval(self):
        job = self.to_approval()
        with self.assertRaises(HoldcoError):
            jobs.send(self.biz, job["id"], DANA, HUMAN, passphrase=PASS)

    def test_approve_and_send_refuse_agent_and_non_interactive_contexts(self):
        job = self.to_approval()
        for ctx in (AGENT, SCRIPT, ExecutionContext(interactive=True, agent=True)):
            with self.assertRaises(HumanOnlyError):
                jobs.approve(self.ws, self.biz, job["id"], DANA, ctx)
        jobs.approve(self.ws, self.biz, job["id"], DANA, HUMAN, passphrase=PASS, minutes=3)
        with self.assertRaises(HumanOnlyError):
            jobs.send(self.biz, job["id"], DANA, AGENT)
        sent = jobs.send(self.biz, job["id"], DANA, HUMAN, passphrase=PASS)
        self.assertEqual(sent["state"], jobs.SENT)
        manifest = read_json(self.biz.outbox_dir / job["id"] / "manifest.json")
        self.assertEqual(manifest["approved_by"], DANA)
        self.assertEqual(manifest["sha256"], sent["approval"]["sha256"])

    def test_simulated_human_only_works_on_demo_businesses(self):
        job = self.to_approval()
        self.set_config(demo=False)
        with self.assertRaises(HumanOnlyError):
            jobs.approve(self.ws, self.biz, job["id"], DANA, ExecutionContext.simulated_demo())

    def test_only_named_approvers(self):
        job = self.to_approval()
        with self.assertRaises(HumanOnlyError):
            jobs.approve(self.ws, self.biz, job["id"], "Random Person", HUMAN)
        with self.assertRaises(HumanOnlyError):
            jobs.approve(self.ws, self.biz, job["id"], "  ", HUMAN)

    def test_tampering_after_approval_blocks_the_send(self):
        job = self.to_approval()
        jobs.approve(self.ws, self.biz, job["id"], DANA, HUMAN, passphrase=PASS)
        path = jobs.job_dir(self.biz, job["id"]) / "approved.json"
        approved = read_json(path)
        write_json(path, set_path(approved, "client_message.subject", "Changed after approval"))
        with self.assertRaises(HoldcoError):
            jobs.send(self.biz, job["id"], DANA, HUMAN, passphrase=PASS)
        self.assertEqual(self.job(job["id"])["state"], jobs.APPROVED)
        self.assertFalse((self.biz.outbox_dir / job["id"]).exists())

    def test_drafts_are_immutable_once_recorded(self):
        job = self.new_job()
        jobs.record_intake(self.ws, self.biz, job["id"], {"status": "complete"})
        draft = self.runner().prepare("monthly-close", "acme", self.inbox / "2026-08-acme", "2026-08", [], {})
        jobs.record_draft(self.ws, self.biz, job["id"], draft)
        path = jobs.job_dir(self.biz, job["id"]) / "drafts" / "v1.json"
        write_json(path, set_path(read_json(path), "client_message.subject", "edited in place"))
        with self.assertRaises(HoldcoError):
            jobs.record_review(self.ws, self.biz, job["id"], {"verdict": "PASS", "score": 100})

    def test_machine_checks_veto_a_reviewer_pass(self):
        job = self.new_job()
        jobs.record_intake(self.ws, self.biz, job["id"], {"status": "complete"})
        draft = self.runner().prepare("monthly-close", "acme", self.inbox / "2026-08-acme", "2026-08", [], {})
        leaky = set_path(draft, "client_message.body_markdown",
                         draft["client_message"]["body_markdown"] + "\nAccount 123456789012 is all set.")
        jobs.record_draft(self.ws, self.biz, job["id"], leaky)
        job = jobs.record_review(self.ws, self.biz, job["id"], {"verdict": "PASS", "score": 99, "findings": []})
        self.assertEqual(job["state"], jobs.BLOCKED)
        self.assertTrue(any(f.get("rule") == "G-004" for f in job["reviews"][-1]["findings"]))
        self.assertIn("downgraded", job["reviews"][-1]["note"])

    def test_three_blocked_drafts_go_to_a_person(self):
        job = self.new_job()
        jobs.record_intake(self.ws, self.biz, job["id"], {"status": "complete"})
        draft = self.runner().prepare("monthly-close", "acme", self.inbox / "2026-08-acme", "2026-08", [], {})
        for _ in range(3):
            jobs.record_draft(self.ws, self.biz, job["id"], draft)
            job = jobs.record_review(self.ws, self.biz, job["id"], {"verdict": "BLOCK", "score": 50, "findings": [
                {"severity": "blocker", "rule": "G-002", "location": "data", "issue": "test", "fix": "test"}]})
        self.assertEqual(job["state"], jobs.NEEDS_HUMAN)
        self.assertEqual(job["resume_state"], jobs.BLOCKED)
        job = jobs.answer(self.biz, job["id"], "Recheck the export; it is fine.", DANA, HUMAN)
        self.assertEqual(job["state"], jobs.BLOCKED)

    def test_human_edits_that_break_a_blocker_rule_need_an_override(self):
        job = self.to_approval()
        draft = jobs.latest_draft(self.biz, job)
        broken = set_path(draft, "data.transactions[T-0801].amount", 4000.0)
        with self.assertRaises(HoldcoError):
            jobs.approve(self.ws, self.biz, job["id"], DANA, HUMAN, passphrase=PASS, final=broken, default_reason="factual_error")
        job = jobs.approve(self.ws, self.biz, job["id"], DANA, HUMAN, passphrase=PASS, final=broken, default_reason="factual_error",
                           override_checks="Bank confirmed a reversal posting on the 3rd")
        self.assertEqual(job["approval"]["overrode_checks"]["reason"], "Bank confirmed a reversal posting on the 3rd")

    def test_one_category_fix_is_one_correction_not_one_per_total(self):
        job = self.to_approval()
        draft = jobs.latest_draft(self.biz, job)
        final = set_path(draft, "data.transactions[T-0803].category", "Vehicle")
        job = jobs.approve(self.ws, self.biz, job["id"], DANA, HUMAN, passphrase=PASS, final=final, default_reason="client_preference")
        logged = corrections.load_corrections(self.biz)
        self.assertEqual(len(logged), 1)
        self.assertEqual(logged[0]["path"], "data.transactions[T-0803].category")
        approved = read_json(jobs.job_dir(self.biz, job["id"]) / "approved.json")
        self.assertIn("Vehicle", approved["data"]["summary"]["expenses_by_category"])

    def test_every_edit_needs_a_category(self):
        job = self.to_approval()
        final = set_path(jobs.latest_draft(self.biz, job), "data.transactions[T-0803].category", "Vehicle")
        with self.assertRaises(HoldcoError):
            jobs.approve(self.ws, self.biz, job["id"], DANA, HUMAN, passphrase=PASS, final=final)
        with self.assertRaises(HoldcoError):
            jobs.approve(self.ws, self.biz, job["id"], DANA, HUMAN, passphrase=PASS, final=final, default_reason="because")

    def test_send_back_returns_work_to_the_preparer_and_logs_it(self):
        job = self.to_approval()
        with self.assertRaises(HumanOnlyError):
            jobs.send_back(self.biz, job["id"], DANA, AGENT, "Shorter please", "style")
        job = jobs.send_back(self.biz, job["id"], DANA, HUMAN, "Shorter please", "style")
        self.assertEqual(job["state"], jobs.BLOCKED)
        self.assertEqual(corrections.load_corrections(self.biz)[-1]["kind"], "send_back")

    def test_missing_documents_create_a_chase_that_needs_approval(self):
        job = self.new_job("2026-06")
        result = self.runner().process(job["id"])
        parent = result["job"]
        chase = self.job(parent["children"][-1])
        self.assertEqual(parent["state"], jobs.WAITING_ON_CLIENT)
        self.assertEqual(chase["state"], jobs.AWAITING_APPROVAL)
        body = jobs.latest_draft(self.biz, chase)["client_message"]["body_markdown"]
        self.assertIn("SHELL OIL", body)
        self.assertIn("GREENLEAF NURSERY", body)
        jobs.add_inputs(self.biz, parent["id"], self.inbox / "2026-06-acme-late-receipts")
        self.assertEqual(self.job(parent["id"])["state"], jobs.RECEIVED)

    def test_reviewer_blocks_the_duplicate_and_preparer_fixes_it(self):
        job = self.new_job("2026-06")
        jobs.add_inputs(self.biz, job["id"], self.inbox / "2026-06-acme-late-receipts")
        job = self.runner().process(job["id"])["job"]
        self.assertEqual([r["verdict"] for r in job["reviews"]], ["BLOCK", "PASS"])
        first = job["reviews"][0]["findings"][0]
        self.assertEqual(first["rule"], "BK-003")
        self.assertEqual(first["data"]["duplicate_ids"], ["T-0611"])
        final = jobs.latest_draft(self.biz, job)
        self.assertEqual([e["id"] for e in final["data"]["excluded"]], ["T-0611"])
        self.assertEqual(final["data"]["reconciliation"]["status"], "tied")

    def test_large_unknown_is_escalated_and_the_answer_is_used(self):
        job = self.new_job("2026-07")
        job = self.runner().process(job["id"])["job"]
        self.assertEqual(job["state"], jobs.NEEDS_HUMAN)
        with self.assertRaises(HumanOnlyError):
            jobs.answer(self.biz, job["id"], "Owner's Draw", DANA, AGENT)
        jobs.answer(self.biz, job["id"], "Owner's Draw", DANA, HUMAN)
        job = self.runner().process(job["id"])["job"]
        self.assertEqual(job["state"], jobs.AWAITING_APPROVAL)
        txn = next(t for t in jobs.latest_draft(self.biz, job)["data"]["transactions"] if t["id"] == "T-0706")
        self.assertEqual(txn["category"], "Owner's Draw")
        answer = corrections.load_corrections(self.biz)[-1]
        self.assertEqual((answer["kind"], answer["category"]), ("escalation_answer", "missing_information"))

    def test_a_guessed_category_for_a_big_unknown_is_blocked(self):
        job = self.new_job("2026-07")
        jobs.record_intake(self.ws, self.biz, job["id"], {"status": "complete"})
        draft = self.runner().prepare("monthly-close", "acme", self.inbox / "2026-07-acme", "2026-07", [],
                                      {"T-0706": "Contractor"})
        jobs.record_draft(self.ws, self.biz, job["id"], draft)  # an LLM guessed without asking anyone
        job = jobs.record_review(self.ws, self.biz, job["id"], {"verdict": "PASS", "score": 95, "findings": []})
        self.assertEqual(job["state"], jobs.BLOCKED)
        self.assertTrue(any(f.get("rule") == "BK-006" for f in job["reviews"][-1]["findings"]))

    def test_cancel_is_human_only(self):
        job = self.to_approval()
        with self.assertRaises(HumanOnlyError):
            jobs.cancel(self.biz, job["id"], DANA, AGENT, "no")
        self.assertEqual(jobs.cancel(self.biz, job["id"], DANA, HUMAN, "client left")["state"], jobs.CANCELLED)

    def test_job_json_history_is_an_audit_trail(self):
        job = self.to_approval()
        jobs.approve(self.ws, self.biz, job["id"], DANA, HUMAN, passphrase=PASS)
        job = jobs.send(self.biz, job["id"], DANA, HUMAN, passphrase=PASS)
        actors = [h["actor"].split(":")[0] for h in job["history"]]
        self.assertEqual(actors, ["system", "intake", "preparer", "reviewer", "human", "human"])
        self.assertTrue(json.dumps(job))


if __name__ == "__main__":
    unittest.main()
