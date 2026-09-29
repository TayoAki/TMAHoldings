"""The proof: three months at a fictional bookkeeping firm, end to end.

Runs in a throwaway copy of the repo's shared layer and demo business, with a
scripted clock and a simulated GM ("Dana"). Every step prints what happened;
every invariant is checked and listed at the end. Exit code 0 means every
proof held.

    python3 -m holdco demo            # full narrative
    python3 -m holdco demo --quiet    # just the proofs

The simulated GM behaves the same way every month: Acme's Home Depot runs are
job materials, so Dana recategorizes any that the agents got wrong, and a
review takes about 4 minutes plus 7 per fix. Nothing about the outcome is typed
in: edits, minutes and the rule all follow from what the agents drafted.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Callable

from holdco import corrections, deals, golden, jobs, keys, metrics
from holdco.config import HoldcoError, Workspace
from holdco.diffing import set_path
from holdco.guard import ExecutionContext, HumanOnlyError
from holdco.runners import get_runner
from holdco.util import freeze_clock, parse_date, read_json, reset_clock, sha256_json, write_json

DANA = "Dana Ruiz"
BIZ = "demo-bookkeeping"
MATERIALS = "Materials (COGS)"
AGENT_CONTEXT = ExecutionContext(interactive=False, agent=True)
# Demo only: in real use the passphrase is typed by the person and never written down.
DEMO_PASSPHRASE = "demo passphrase, never use for real work"
REVIEW_MINUTES, MINUTES_PER_FIX = 4, 7


def dana_review(draft: dict) -> dict:
    """What Dana changes before approving: Acme's Home Depot runs are job materials."""
    final = draft
    for txn in (draft.get("data") or {}).get("transactions", []) or []:
        if "HOME DEPOT" in txn["description"].upper() and txn["category"] != MATERIALS:
            final = set_path(final, f"data.transactions[{txn['id']}].category", MATERIALS)
    return final


class Demo:
    def __init__(self, repo: Path, workspace: Path | None, quiet: bool):
        self.repo = repo
        self.dir = workspace or Path(tempfile.mkdtemp(prefix="holdco-demo-"))
        self.quiet = quiet
        self.proofs: list[tuple[str, bool, str]] = []
        self.human = ExecutionContext.simulated_demo()

    # ------------------------------------------------------------ output

    def say(self, text: str = "") -> None:
        if not self.quiet:
            print(text)

    def step(self, title: str) -> None:
        self.say()
        self.say("=" * 78)
        self.say(title)
        self.say("=" * 78)

    def prove(self, label: str, ok: bool, detail: str = "") -> None:
        self.proofs.append((label, ok, detail))
        self.say(f"  {'PROOF OK ' if ok else 'PROOF FAILED'} {label}{f' ({detail})' if detail else ''}")

    def refused(self, label: str, action: Callable[[], object], errors: tuple = (PermissionError, HoldcoError)) -> None:
        try:
            action()
        except errors as exc:
            self.prove(label, True, f"refused: {str(exc).splitlines()[0][:110]}")
            return
        self.prove(label, False, "it was allowed")

    # ------------------------------------------------------------- setup

    def setup(self) -> None:
        if self.dir.exists() and any(self.dir.iterdir()):
            raise HoldcoError(f"Demo workspace {self.dir} is not empty.")
        self.dir.mkdir(parents=True, exist_ok=True)
        shutil.copytree(self.repo / "shared", self.dir / "shared")
        shutil.copytree(self.repo / "businesses" / BIZ, self.dir / "businesses" / BIZ)
        if (self.repo / "thesis").is_dir():
            shutil.copytree(self.repo / "thesis", self.dir / "thesis")
        self.ws = Workspace(self.dir)
        self.biz = self.ws.business(BIZ)
        self.inbox = self.biz.dir / "inbox"
        record = keys.add_key(self.biz, DANA, DEMO_PASSPHRASE, self.human)
        self.say(f"  setup  {DANA} set an approval passphrase (key {record['key_id']}, kept in the demo "
                 "workspace's own key store)")

    def runner(self, exclude: set[str] | None = None):
        return get_runner(self.ws, self.biz, "demo", exclude)

    def process(self, job_id: str) -> dict:
        result = self.runner().process(job_id)
        for line in result["steps"]:
            self.say(f"  agent  {line}")
        return result["job"]

    def job(self, job_id: str) -> dict:
        return jobs.load_job(self.biz, job_id)

    def approve(self, job_id: str, note: str = "", minutes: float | None = None) -> dict:
        job = self.job(job_id)
        draft = jobs.latest_draft(self.biz, job)
        final = dana_review(draft)
        changes = jobs.pending_changes(job["type"], draft, final)
        if minutes is None:
            minutes = REVIEW_MINUTES + MINUTES_PER_FIX * len(changes)
        job = jobs.approve(self.ws, self.biz, job_id, DANA, self.human, final=final,
                           default_reason="client_preference" if changes else None,
                           notes={c.path: note for c in changes} if note else None, minutes=minutes,
                           passphrase=DEMO_PASSPHRASE)
        what = f"{len(changes)} fix(es): " + ", ".join(c.path for c in changes) if changes else "no fixes needed"
        self.say(f"  human  {DANA} approved {job_id} ({what}; {minutes:g} min)")
        return job

    def send(self, job_id: str) -> dict:
        job = jobs.send(self.biz, job_id, DANA, self.human, passphrase=DEMO_PASSPHRASE)
        self.say(f"  human  {DANA} released it -> {job['sent']['outbox']} (signed)")
        return job

    # ------------------------------------------------------------- story

    def run(self) -> int:
        previous = os.environ.get("HOLDCO_KEYS_DIR")
        os.environ["HOLDCO_KEYS_DIR"] = str(self.dir / ".keys")
        try:
            self.setup()
            self.june()
            self.first_review()
            self.july()
            self.second_review()
            self.august()
            self.monday()
            self.thursday()
        finally:
            reset_clock()
            if previous is None:
                os.environ.pop("HOLDCO_KEYS_DIR", None)
            else:
                os.environ["HOLDCO_KEYS_DIR"] = previous
        return self.summary()

    def june(self) -> None:
        self.step("1. June close for Acme Landscaping (2026-07-01) - receipts missing")
        freeze_clock("2026-07-01T16:00:00")
        job = jobs.create_job(self.ws, self.biz, "monthly-close", "acme", self.inbox / "2026-06-acme", period="2026-06")
        self.june_id = job["id"]
        self.say(f"  system created job {job['id']} from the client's bank export, statement and receipts")
        job = self.process(job["id"])
        chase_id = job["children"][-1]
        chase = self.job(chase_id)
        self.prove("Missing receipts stop the work and create a chase for a person to approve",
                   job["state"] == jobs.WAITING_ON_CLIENT and chase["state"] == jobs.AWAITING_APPROVAL,
                   f"{job['id']}: {job['state']}, {chase_id}: {chase['state']}")
        message = jobs.latest_draft(self.biz, chase)["client_message"]
        self.say(f"\n  Draft chase email (not sent):\n  Subject: {message['subject']}")
        for line in message["body_markdown"].splitlines():
            self.say(f"  | {line}")
        self.say()
        self.refused("The reviewer agent cannot approve anything",
                     lambda: jobs.check_transition(self.job(chase_id), jobs.APPROVED, jobs.REVIEWER))
        self.refused("The preparer agent cannot approve anything",
                     lambda: jobs.check_transition(self.job(chase_id), jobs.APPROVED, jobs.PREPARER))
        self.refused("Approving from inside an agent session is refused",
                     lambda: jobs.approve(self.ws, self.biz, chase_id, DANA, AGENT_CONTEXT), (HumanOnlyError,))
        self.refused("Nothing can be sent before a person approves it",
                     lambda: jobs.send(self.biz, chase_id, DANA, self.human, passphrase=DEMO_PASSPHRASE))
        self.refused("Only named approvers can approve",
                     lambda: jobs.approve(self.ws, self.biz, chase_id, "Someone Else", self.human), (HumanOnlyError,))
        self.forged_approval(chase_id)
        freeze_clock("2026-07-01T16:20:00")
        self.approve(chase_id, minutes=2)
        self.send(chase_id)

        self.step("2. Client sends the receipts (2026-07-02) - agents draft, reviewer blocks, preparer fixes")
        freeze_clock("2026-07-02T10:15:00")
        jobs.add_inputs(self.biz, self.june_id, self.inbox / "2026-06-acme-late-receipts")
        self.say("  system receipts added; job back to 'received'")
        job = self.process(self.june_id)
        reviews = job["reviews"]
        self.prove("The reviewer blocked a draft that did not tie to the bank, and the fixed draft passed",
                   len(reviews) >= 2 and reviews[0]["verdict"] == "BLOCK" and reviews[-1]["verdict"] == "PASS"
                   and job["state"] == jobs.AWAITING_APPROVAL,
                   " -> ".join(f"v{r['version']} {r['verdict']}" for r in reviews))
        draft = jobs.latest_draft(self.biz, job)
        categories = {t["id"]: t["category"] for t in draft["data"]["transactions"]}
        self.say(f"  draft  Home Depot T-0602 and T-0610 came out as '{categories['T-0602']}' (industry default)")

        self.step("3. Dana reviews the June close (2026-07-03) - fixes, then approval")
        freeze_clock("2026-07-03T08:40:00")
        self.approve(self.june_id, note="Acme resells materials; Home Depot runs are job materials")
        approved_path = jobs.job_dir(self.biz, self.june_id) / "approved.json"
        original = read_json(approved_path)
        tampered = set_path(original, "data.transactions[T-0603].category", "Meals")
        write_json(approved_path, tampered)
        self.refused("Changing the work after approval blocks the send (hash check)",
                     lambda: jobs.send(self.biz, self.june_id, DANA, self.human, passphrase=DEMO_PASSPHRASE))
        write_json(approved_path, original)
        self.send(self.june_id)
        logged = corrections.load_corrections(self.biz)
        edits = [e for e in logged if e["kind"] == "edit"]
        self.prove("Every human edit was logged as a categorized correction",
                   len(edits) == 2 and all(e["category"] == "client_preference" for e in edits),
                   ", ".join(f"{e['id']} {e['path']} -> {e['after']} [{e['category']}]" for e in edits))
        self.tampered_outbox()

    def forged_approval(self, job_id: str) -> None:
        """An agent that writes an approval straight into the job files still can't get it released."""
        folder = jobs.job_dir(self.biz, job_id)
        before = {name: (folder / name).read_bytes() for name in ("job.json",)}
        job = self.job(job_id)
        draft = jobs.latest_draft(self.biz, job)
        forged = dict(job, state=jobs.APPROVED, approval={
            "by": DANA, "at": "2026-07-01T16:05:00", "sha256": sha256_json(draft),
            "draft_version": job["drafts"][-1]["version"], "edited": False, "changes": 0, "minutes": 1,
            "method": "interactive-terminal", "note": None, "overrode_checks": None, "key_id": "forged",
            "signature": "0" * 64})
        write_json(folder / "job.json", forged)
        write_json(folder / "approved.json", draft)
        self.refused("An approval written straight into the job files (no passphrase) cannot be released",
                     lambda: jobs.send(self.biz, job_id, DANA, self.human, passphrase=DEMO_PASSPHRASE))
        for name, data in before.items():
            (folder / name).write_bytes(data)
        (folder / "approved.json").unlink()

    def tampered_outbox(self) -> None:
        """What reaches the outbox is checked before anyone emails it."""
        clean = jobs.verify_outbox(self.biz, DANA, self.human, DEMO_PASSPHRASE)
        message = self.biz.outbox_dir / self.june_id / "message.md"
        original = message.read_text(encoding="utf-8")
        message.write_text(original.replace("Here's the short version.", "Please wire the balance today."),
                           encoding="utf-8")
        planted = self.biz.outbox_dir / "2026-06-acme-invoice"
        planted.mkdir()
        (planted / "message.md").write_text("Pay this invoice.", encoding="utf-8")
        results = {r["item"]: r for r in jobs.verify_outbox(self.biz, DANA, self.human, DEMO_PASSPHRASE)}
        self.prove("`outbox verify` passes what Dana released and flags an edited message and a planted item",
                   all(r["ok"] for r in clean) and len(clean) == 2
                   and results[self.june_id]["ok"] is False and results[planted.name]["ok"] is False,
                   f"{self.june_id}: {results[self.june_id]['problems'][0]}; "
                   f"{planted.name}: {results[planted.name]['problems'][0]}")
        message.write_text(original, encoding="utf-8")
        shutil.rmtree(planted)

    def first_review(self) -> None:
        self.step("4. Wednesday corrections review (2026-07-08)")
        freeze_clock("2026-07-08T09:00:00")
        report = corrections.review(self.ws, self.biz, as_of=parse_date("2026-07-08"))
        self.say(f"  review {report['this_week']} correction(s) this week: {report['by_category']}")
        for item in report["watch"]:
            self.say(f"  watch  {item['signature'][3]} -> {item['signature'][4]}: seen in {len(item['jobs'])} job, "
                     "needs a second job before it becomes a rule")
        self.prove("One job's corrections alone do not create a rule", not report["new_proposals"],
                   f"{len(report['watch'])} item(s) on the watch list")

    def july(self) -> None:
        self.step("5. July close (2026-08-03) - the preparer stops and asks about a $6,200 transfer")
        freeze_clock("2026-08-03T15:00:00")
        job = jobs.create_job(self.ws, self.biz, "monthly-close", "acme", self.inbox / "2026-07-acme", period="2026-07")
        self.july_id = job["id"]
        job = self.process(job["id"])
        self.prove("A large unknown transaction is escalated to a person, not guessed",
                   job["state"] == jobs.NEEDS_HUMAN and job["questions"][-1]["key"] == "T-0706",
                   job["questions"][-1]["question"][:80] + "...")
        self.refused("An agent cannot answer its own question",
                     lambda: jobs.answer(self.biz, self.july_id, "Owner's Draw", DANA, AGENT_CONTEXT),
                     (HumanOnlyError,))
        freeze_clock("2026-08-03T15:30:00")
        jobs.answer(self.biz, self.july_id, "Owner's Draw", DANA, self.human)
        self.say(f"  human  {DANA} answered: Owner's Draw (logged as missing_information)")
        self.process(self.july_id)
        freeze_clock("2026-08-04T09:30:00")
        self.approve(self.july_id, note="Same as June: Home Depot is job materials for Acme")
        self.send(self.july_id)

    def second_review(self) -> None:
        self.step("6. Wednesday corrections review (2026-08-05) - a repeated fix becomes a rule and two tests")
        freeze_clock("2026-08-05T09:00:00")
        report = corrections.review(self.ws, self.biz, as_of=parse_date("2026-08-05"))
        self.say(f"  review {report['this_week']} correction(s) this week: {report['by_category']}")
        proposals = report["new_proposals"]
        for p in proposals:
            self.say(f"  PROPOSAL {p['id']}: {p['title']}\n           {p['rule_text']}\n           {p['why']}")
        for item in report["watch"]:
            self.say(f"  watch  {item['signature'][3]} -> {item['signature'][4]} (1 job so far)")
        self.prove("The same fix in two separate jobs produced exactly one proposed rule",
                   len(proposals) == 1 and proposals[0]["check"]["category"] == MATERIALS,
                   proposals[0]["id"] if proposals else "none")
        proposal_id = proposals[0]["id"]
        self.refused("Only a person can accept a rule",
                     lambda: corrections.accept_proposal(self.ws, self.biz, proposal_id, DANA, AGENT_CONTEXT),
                     (HumanOnlyError,))
        accepted = corrections.accept_proposal(self.ws, self.biz, proposal_id, DANA, self.human)
        self.new_rule = accepted["rule_id"]
        self.say(f"  human  {DANA} accepted {proposal_id} -> rule {self.new_rule} added to rules.md, "
                 f"golden cases {', '.join(accepted['golden_cases'])} created from the June and July jobs")
        with_rule = golden.run_eval(self.ws, self.biz, self.runner())
        without = golden.run_eval(self.ws, self.biz, self.runner(exclude={self.new_rule}))
        self.say(f"  eval   with {self.new_rule}: {with_rule['passed']}/{len(with_rule['cases'])} pass;"
                 f" with it removed: {without['passed']}/{len(without['cases'])} pass")
        self.prove("The regression tests pass with the new rule and catch its removal",
                   with_rule["failed"] == 0 and without["passed"] == 0 and len(with_rule["cases"]) == 2)

    def august(self) -> None:
        self.step("7. August close (2026-09-01) - the rule does the work")
        freeze_clock("2026-09-01T15:00:00")
        job = jobs.create_job(self.ws, self.biz, "monthly-close", "acme", self.inbox / "2026-08-acme", period="2026-08")
        job = self.process(job["id"])
        draft = jobs.latest_draft(self.biz, job)
        home_depot = next(t for t in draft["data"]["transactions"] if t["id"] == "T-0802")
        self.prove("The preparer now applies the learned rule on its own",
                   home_depot["category"] == MATERIALS and self.new_rule in draft["rules_applied"],
                   f"T-0802 -> {home_depot['category']} via {self.new_rule}")
        freeze_clock("2026-09-02T09:00:00")
        wanted = jobs.pending_changes(job["type"], draft, dana_review(draft))
        job = self.approve(job["id"])
        self.send(job["id"])
        self.prove("Dana's usual review finds nothing left to fix in the August draft",
                   not wanted and job["approval"]["changes"] == 0,
                   f"{len(wanted)} fix(es) needed, {job['approval']['minutes']:g} min")

    def monday(self) -> None:
        self.step("8. Monday numbers (2026-09-28)")
        freeze_clock("2026-09-28T08:00:00")
        report = metrics.business_metrics(self.biz, as_of=parse_date("2026-09-28"))
        for line in metrics.format_report(report).splitlines():
            self.say(f"  {line}")
        self.prove("The dashboard flags profit rising while a client left",
                   any("while clients left" in a for a in report["alerts"]))
        now, before = report["current"]["minutes_per_job"], report["previous"]["minutes_per_job"]
        self.prove(f"Human minutes per job fell as the rule removed fixes (modeled: {REVIEW_MINUTES} min + "
                   f"{MINUTES_PER_FIX} per fix)", now is not None and before is not None and now < before,
                   f"{before} -> {now} min")

    def thursday(self) -> None:
        self.step("9. Thursday: screen the next business (thesis/deals/example-target.json)")
        deal_file = self.dir / "thesis" / "deals" / "example-target.json"
        buy_box_file = self.dir / "thesis" / "buy-box.json"
        if not deal_file.exists() or not buy_box_file.exists():
            self.say("  (no example deal in this workspace; skipped)")
            return
        deal, buy_box = read_json(deal_file), read_json(buy_box_file)
        report = deals.score_deal(deal, buy_box)
        for line in deals.format_deal(report).splitlines()[:8]:
            self.say(f"  {line}")
        self.say("  ... full screen: python3 -m holdco deal score thesis/deals/example-target.json")
        # The same firm if replacing the owner cost $150k: now coverage is what limits the price.
        thinner = deals.score_deal({**deal, "replacement_comp": 150000}, buy_box)
        floor = float(buy_box.get("min_dscr_today", 1.25))

        def coverage_at(result: dict) -> float:
            structure = result["assumptions"]["structure"]
            return result["ebitda_today"] / deals.financing(result["max_price"], structure)["debt_service_peak"]

        self.say(f"  if replacing the owner cost $150,000: most you should pay {thinner['max_price']:,.0f} "
                 f"(binding: {thinner['binding_cap']}), coverage there {coverage_at(thinner):.3f}x")
        self.prove(f"At the most you should pay, today's earnings still cover the debt {floor}x",
                   coverage_at(report) >= floor - 1e-6 and thinner["binding_cap"] == "DSCR on today's earnings"
                   and abs(coverage_at(thinner) - floor) < 1e-6,
                   f"{coverage_at(report):.2f}x at {report['max_price']:,.0f}; exactly {coverage_at(thinner):.2f}x "
                   "when coverage binds")

    def summary(self) -> int:
        failed = [p for p in self.proofs if not p[1]]
        print()
        print("=" * 78)
        print(f"PROOF SUMMARY: {len(self.proofs) - len(failed)}/{len(self.proofs)} held")
        print("=" * 78)
        for label, ok, _ in self.proofs:
            print(f"  [{'x' if ok else ' '}] {label}")
        print(f"\nWorkspace kept for inspection: {self.dir}")
        return 1 if failed else 0


def run_demo(repo: Path, workspace: Path | None = None, quiet: bool = False) -> int:
    return Demo(repo, workspace, quiet).run()
