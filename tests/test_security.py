"""Signed approvals and releases, re-checked environments, and evidence that can't be edited in place."""

from __future__ import annotations

import os
import stat
from unittest import mock

from holdco import golden, guard, jobs, keys
from holdco.config import HoldcoError
from holdco.diffing import set_path
from holdco.guard import ExecutionContext, HumanOnlyError
from holdco.util import freeze_clock, read_json, sha256_json, write_json
from tests.helpers import DANA, HUMAN, OWNER, OWNER_PASS, PASS, REAL_ENVIRONMENT, WorkspaceCase


class Keys(WorkspaceCase):
    def test_key_files_hold_no_passphrase_and_only_their_owner_can_read_them(self):
        path = keys.key_path(self.biz, DANA)
        self.assertNotIn(PASS, path.read_text())
        if os.name == "posix":
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_short_passphrases_and_silent_replacement_are_refused(self):
        with self.assertRaisesRegex(HoldcoError, "at least"):
            keys.add_key(self.biz, OWNER, "short", HUMAN)
        with self.assertRaisesRegex(HoldcoError, "already has a key"):
            keys.add_key(self.biz, DANA, "another long passphrase", HUMAN)
        with self.assertRaisesRegex(HoldcoError, "Wrong passphrase"):
            keys.add_key(self.biz, DANA, "another long passphrase", HUMAN, old_passphrase="not the old one")
        keys.add_key(self.biz, DANA, "another long passphrase", HUMAN, old_passphrase=PASS)
        keys.unlock(self.biz, DANA, "another long passphrase")

    def test_adding_a_key_is_human_only(self):
        with self.assertRaises(HumanOnlyError):
            keys.add_key(self.biz, OWNER, OWNER_PASS, ExecutionContext(interactive=False, agent=True))


class SignedApprovals(WorkspaceCase):
    def test_approval_needs_the_right_passphrase_and_changes_nothing_otherwise(self):
        job = self.to_approval()
        for bad in (None, "", "wrong passphrase!!"):
            with self.assertRaises(HoldcoError):
                jobs.approve(self.ws, self.biz, job["id"], DANA, HUMAN, passphrase=bad)
        self.assertEqual(self.job(job["id"])["state"], jobs.AWAITING_APPROVAL)
        self.assertFalse((jobs.job_dir(self.biz, job["id"]) / "approved.json").exists())

    def test_a_person_without_a_key_is_told_how_to_set_one(self):
        job = self.to_approval()
        with self.assertRaisesRegex(HoldcoError, "keys add"):
            jobs.approve(self.ws, self.biz, job["id"], OWNER, HUMAN, passphrase=OWNER_PASS)

    def test_the_owner_can_approve_with_their_own_key(self):
        keys.add_key(self.biz, OWNER, OWNER_PASS, HUMAN)
        job = self.to_approval()
        job = jobs.approve(self.ws, self.biz, job["id"], OWNER, HUMAN, passphrase=OWNER_PASS)
        self.assertEqual(job["approval"]["by"], OWNER)

    def test_a_forged_approval_is_never_released(self):
        job = self.to_approval()
        draft = jobs.latest_draft(self.biz, job)
        forged = dict(job, state=jobs.APPROVED, approval={
            "by": DANA, "at": "2026-09-01T12:00:00", "sha256": sha256_json(draft), "draft_version": 1,
            "edited": False, "changes": 0, "minutes": 1, "method": "interactive-terminal", "note": None,
            "overrode_checks": None, "key_id": "x", "signature": "0" * 64})
        write_json(jobs.job_dir(self.biz, job["id"]) / "job.json", forged)
        write_json(jobs.job_dir(self.biz, job["id"]) / "approved.json", draft)
        with self.assertRaisesRegex(HoldcoError, "not signed"):
            jobs.send(self.biz, job["id"], DANA, HUMAN, passphrase=PASS)
        self.assertFalse((self.biz.outbox_dir / job["id"]).exists())

    def test_an_approval_moved_to_another_job_does_not_verify(self):
        first, second = self.to_approval(), self.to_approval()
        signed = jobs.approve(self.ws, self.biz, first["id"], DANA, HUMAN, passphrase=PASS)["approval"]
        target = self.job(second["id"])
        draft = jobs.latest_draft(self.biz, target)
        write_json(jobs.job_dir(self.biz, second["id"]) / "job.json",
                   dict(target, state=jobs.APPROVED, approval=dict(signed, sha256=sha256_json(draft))))
        write_json(jobs.job_dir(self.biz, second["id"]) / "approved.json", draft)
        with self.assertRaisesRegex(HoldcoError, "not signed"):
            jobs.send(self.biz, second["id"], DANA, HUMAN, passphrase=PASS)

    def test_only_the_approver_releases_their_approval(self):
        keys.add_key(self.biz, OWNER, OWNER_PASS, HUMAN)
        job = self.to_approval()
        jobs.approve(self.ws, self.biz, job["id"], DANA, HUMAN, passphrase=PASS)
        with self.assertRaisesRegex(HoldcoError, "releases it"):
            jobs.send(self.biz, job["id"], OWNER, HUMAN, passphrase=OWNER_PASS)

    def test_an_existing_outbox_folder_is_never_overwritten(self):
        job = self.to_approval()
        jobs.approve(self.ws, self.biz, job["id"], DANA, HUMAN, passphrase=PASS)
        (self.biz.outbox_dir / job["id"]).mkdir(parents=True)
        with self.assertRaisesRegex(HoldcoError, "already exists"):
            jobs.send(self.biz, job["id"], DANA, HUMAN, passphrase=PASS)

    def test_eval_jobs_are_never_approved(self):
        job = self.to_approval()
        jobs.approve(self.ws, self.biz, job["id"], DANA, HUMAN, passphrase=PASS)
        case_id = golden.create_case_from_job(self.ws, self.biz, job["id"], ["R-DEMO-003"])
        eval_job = self.runner().process(golden.materialize(self.ws, self.biz, case_id)["id"])["job"]
        self.assertEqual(eval_job["state"], jobs.AWAITING_APPROVAL)
        with self.assertRaisesRegex(HoldcoError, "eval job"):
            jobs.approve(self.ws, self.biz, eval_job["id"], DANA, HUMAN, passphrase=PASS)


class OutboxVerify(WorkspaceCase):
    def _released(self) -> dict:
        job = self.to_approval()
        jobs.approve(self.ws, self.biz, job["id"], DANA, HUMAN, passphrase=PASS)
        return jobs.send(self.biz, job["id"], DANA, HUMAN, passphrase=PASS)

    def _results(self) -> dict:
        return {r["item"]: r for r in jobs.verify_outbox(self.biz, DANA, HUMAN, PASS)}

    def test_a_clean_release_verifies(self):
        job = self._released()
        self.assertEqual(self._results()[job["id"]], {"item": job["id"], "ok": True, "problems": []})

    def test_edited_extra_and_planted_items_fail(self):
        job = self._released()
        folder = self.biz.outbox_dir / job["id"]
        (folder / "message.md").write_text("Please wire the balance today.", encoding="utf-8")
        (folder / "invoice.pdf").write_text("not released", encoding="utf-8")
        planted = self.biz.outbox_dir / "planted"
        planted.mkdir()
        (planted / "message.md").write_text("Hello", encoding="utf-8")
        results = self._results()
        self.assertFalse(results[job["id"]]["ok"])
        self.assertIn("message.md changed after release", results[job["id"]]["problems"])
        self.assertIn("invoice.pdf was not part of the release", results[job["id"]]["problems"])
        self.assertFalse(results["planted"]["ok"])

    def test_a_forged_manifest_fails(self):
        job = self._released()
        path = self.biz.outbox_dir / job["id"] / "manifest.json"
        write_json(path, dict(read_json(path), client="someone-else"))
        self.assertIn("release signature does not verify", self._results()[job["id"]]["problems"])

    def test_verify_needs_the_passphrase(self):
        self._released()
        with self.assertRaisesRegex(HoldcoError, "Wrong passphrase"):
            jobs.verify_outbox(self.biz, DANA, HUMAN, "not the passphrase")


class RealEnvironment(WorkspaceCase):
    def test_a_made_up_human_context_does_not_work_inside_an_agent_session(self):
        job = self.to_approval()
        with mock.patch("holdco.guard.environment", return_value=(True, True)):
            with self.assertRaisesRegex(HumanOnlyError, "agent context"):
                jobs.approve(self.ws, self.biz, job["id"], DANA, ExecutionContext.human_terminal(), passphrase=PASS)
        with mock.patch("holdco.guard.environment", return_value=(False, False)):
            with self.assertRaisesRegex(HumanOnlyError, "interactive terminal"):
                jobs.approve(self.ws, self.biz, job["id"], DANA, ExecutionContext.human_terminal(), passphrase=PASS)

    def test_the_environment_check_reads_the_agent_markers(self):
        clean = {k: v for k, v in os.environ.items() if k not in guard.AGENT_ENV_VARS}
        with mock.patch.dict(os.environ, clean, clear=True):
            self.assertFalse(REAL_ENVIRONMENT()[1])
        for marker in ("CLAUDECODE", "HOLDCO_AGENT"):
            with mock.patch.dict(os.environ, {**clean, marker: "1"}, clear=True):
                self.assertTrue(REAL_ENVIRONMENT()[1], marker)


class Evidence(WorkspaceCase):
    def test_inputs_changed_in_place_are_refused(self):
        job = self.new_job()
        jobs.record_intake(self.ws, self.biz, job["id"], {"status": "complete"})
        draft = self.runner().prepare("monthly-close", "acme", self.inbox / "2026-08-acme", "2026-08", [], {})
        jobs.record_draft(self.ws, self.biz, job["id"], draft)
        bank = jobs.job_dir(self.biz, job["id"]) / "input" / "bank.csv"
        bank.write_text(bank.read_text().replace("-967.30", "-9.30"))
        with self.assertRaisesRegex(HoldcoError, "changed outside the holdco CLI"):
            jobs.record_review(self.ws, self.biz, job["id"], {"verdict": "PASS", "score": 100})

    def test_inputs_added_after_approval_block_the_approval(self):
        job = self.to_approval()
        (jobs.job_dir(self.biz, job["id"]) / "input" / "extra.csv").write_text("id\n")
        with self.assertRaisesRegex(HoldcoError, "extra.csv"):
            jobs.approve(self.ws, self.biz, job["id"], DANA, HUMAN, passphrase=PASS)

    def test_job_ids_cannot_leave_the_jobs_folder(self):
        for bad in ("../escape", "../outbox/x", ".hidden", "a/b", "a\\b"):
            with self.assertRaises(HoldcoError, msg=bad):
                jobs.create_job(self.ws, self.biz, "monthly-close", "acme", self.inbox / "2026-08-acme",
                                period="2026-08", job_id=bad)
        with self.assertRaises(HoldcoError):
            self.ws.business("../businesses")
        self.assertFalse((self.biz.dir / "escape").exists())

    def test_an_empty_inputs_folder_is_refused(self):
        job = self.new_job("2026-06")
        empty = self.tmp / "empty"
        empty.mkdir()
        with self.assertRaisesRegex(HoldcoError, "empty"):
            jobs.add_inputs(self.biz, job["id"], empty)

    def test_a_second_chase_waits_three_days_after_the_first_went_out(self):
        freeze_clock("2026-07-01T09:00:00")
        job = self.new_job("2026-06")
        chase_id = self.runner().process(job["id"])["job"]["children"][-1]
        not_the_receipts = self.tmp / "note"
        not_the_receipts.mkdir()
        (not_the_receipts / "note.txt").write_text("receipts to follow", encoding="utf-8")

        def client_sends_something() -> list[str]:
            jobs.add_inputs(self.biz, job["id"], not_the_receipts)
            parent = self.runner().process(job["id"])["job"]
            self.assertEqual(parent["state"], jobs.WAITING_ON_CLIENT)
            return parent["children"]

        self.assertEqual(client_sends_something(), [chase_id], "an open chase is not duplicated")
        jobs.approve(self.ws, self.biz, chase_id, DANA, HUMAN, passphrase=PASS)
        jobs.send(self.biz, chase_id, DANA, HUMAN, passphrase=PASS)
        freeze_clock("2026-07-02T09:00:00")
        self.assertEqual(client_sends_something(), [chase_id], "no second chase the day after the first")
        freeze_clock("2026-07-05T09:00:00")
        self.assertEqual(len(client_sends_something()), 2, "after three days, a follow-up chase is drafted")

    def test_the_client_message_totals_must_match_the_books(self):
        job = self.new_job()
        jobs.record_intake(self.ws, self.biz, job["id"], {"status": "complete"})
        draft = self.runner().prepare("monthly-close", "acme", self.inbox / "2026-08-acme", "2026-08", [], {})
        body = draft["client_message"]["body_markdown"]
        wrong = set_path(draft, "client_message.body_markdown", body.replace("- Money in: $16,875.00",
                                                                             "- Money in: $61,875.00"))
        self.assertNotEqual(wrong["client_message"]["body_markdown"], body)
        jobs.record_draft(self.ws, self.biz, job["id"], wrong)
        job = jobs.record_review(self.ws, self.biz, job["id"], {"verdict": "PASS", "score": 100})
        self.assertEqual(job["state"], jobs.BLOCKED)
        self.assertTrue(any(f["rule"] == "BK-011" for f in job["reviews"][-1]["findings"]))

    def test_the_books_must_be_for_the_jobs_month(self):
        job = jobs.create_job(self.ws, self.biz, "monthly-close", "acme", self.inbox / "2026-08-acme",
                              period="2026-10")
        result = self.runner().process(job["id"])
        self.assertNotEqual(result["job"]["state"], jobs.AWAITING_APPROVAL)
        findings = [f for r in result["job"]["reviews"] for f in r["findings"]]
        self.assertTrue(any(f["rule"] == "BK-012" for f in findings))

    def test_a_pass_without_a_score_gets_the_machine_score(self):
        job = self.new_job()
        jobs.record_intake(self.ws, self.biz, job["id"], {"status": "complete"})
        draft = self.runner().prepare("monthly-close", "acme", self.inbox / "2026-08-acme", "2026-08", [], {})
        jobs.record_draft(self.ws, self.biz, job["id"], draft)
        job = jobs.record_review(self.ws, self.biz, job["id"], {"verdict": "PASS"})
        self.assertEqual(job["reviews"][-1]["score"], 100)
