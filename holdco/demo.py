"""The proof: three months at a fictional bookkeeping firm, end to end.

Runs in a throwaway copy of the repo's shared layer and demo business, with a
scripted clock and a simulated GM ("Dana"). Every step prints what happened;
every invariant is checked and listed at the end. Exit code 0 means every
proof held.

    python3 -m holdco demo            # full narrative
    python3 -m holdco demo --quiet    # just the proofs
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Callable

from holdco import corrections, deals, golden, jobs, metrics
from holdco.config import HoldcoError, Workspace
from holdco.diffing import set_path
from holdco.guard import ExecutionContext, HumanOnlyError
from holdco.runners import get_runner
from holdco.util import freeze_clock, parse_date, read_json, reset_clock, write_json

DANA = "Dana Ruiz"
BIZ = "demo-bookkeeping"
MATERIALS = "Materials (COGS)"
AGENT_CONTEXT = ExecutionContext(interactive=False, agent=True)


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

    def runner(self, exclude: set[str] | None = None):
        return get_runner(self.ws, self.biz, "demo", exclude)

    def process(self, job_id: str) -> dict:
        result = self.runner().process(job_id)
        for line in result["steps"]:
            self.say(f"  agent  {line}")
        return result["job"]

    def job(self, job_id: str) -> dict:
        return jobs.load_job(self.biz, job_id)

    def approve(self, job_id: str, edits: dict[str, str], reason: str | None, minutes: float, note: str = "") -> dict:
        draft = jobs.latest_draft(self.biz, self.job(job_id))
        final = draft
        for path, value in edits.items():
            final = set_path(final, path, value)
        notes = {path: note for path in edits} if note else None
        job = jobs.approve(self.ws, self.biz, job_id, DANA, self.human, final=final, default_reason=reason,
                           notes=notes, minutes=minutes)
        what = f"{len(edits)} edit(s), categorized {reason}" if edits else "no edits"
        self.say(f"  human  {DANA} approved {job_id} ({what}, {minutes:g} min)")
        return job

    def send(self, job_id: str) -> dict:
        job = jobs.send(self.biz, job_id, DANA, self.human)
        self.say(f"  human  {DANA} sent it -> {job['sent']['outbox']}")
        return job

    # ------------------------------------------------------------- story

    def run(self) -> int:
        self.setup()
        try:
            self.june()
            self.first_review()
            self.july()
            self.second_review()
            self.august()
            self.monday()
            self.thursday()
        finally:
            reset_clock()
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
                     lambda: jobs.send(self.biz, chase_id, DANA, self.human))
        self.refused("Only named approvers can approve",
                     lambda: jobs.approve(self.ws, self.biz, chase_id, "Someone Else", self.human), (HumanOnlyError,))
        freeze_clock("2026-07-01T16:20:00")
        self.approve(chase_id, {}, None, minutes=2)
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

        self.step("3. Dana reviews the June close (2026-07-03) - two corrections, then approval")
        freeze_clock("2026-07-03T08:40:00")
        self.approve(self.june_id, {
            "data.transactions[T-0602].category": MATERIALS,
            "data.transactions[T-0610].category": MATERIALS,
        }, "client_preference", minutes=18, note="Acme resells materials; Home Depot runs are job materials")
        approved_path = jobs.job_dir(self.biz, self.june_id) / "approved.json"
        original = read_json(approved_path)
        tampered = set_path(original, "data.transactions[T-0603].category", "Meals")
        write_json(approved_path, tampered)
        self.refused("Changing the work after approval blocks the send (hash check)",
                     lambda: jobs.send(self.biz, self.june_id, DANA, self.human))
        write_json(approved_path, original)
        self.send(self.june_id)
        logged = corrections.load_corrections(self.biz)
        self.prove("Every human edit was logged as a categorized correction",
                   sum(e["kind"] == "edit" for e in logged) == 2,
                   ", ".join(f"{e['id']} {e['path']} -> {e['after']} [{e['category']}]"
                             for e in logged if e["kind"] == "edit"))

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
        job = self.process(self.july_id)
        freeze_clock("2026-08-04T09:30:00")
        self.approve(self.july_id, {"data.transactions[T-0702].category": MATERIALS}, "client_preference",
                     minutes=11, note="Same as June: Home Depot is job materials for Acme")
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
        self.step("7. August close (2026-09-01) - the rule does the work; zero edits")
        freeze_clock("2026-09-01T15:00:00")
        job = jobs.create_job(self.ws, self.biz, "monthly-close", "acme", self.inbox / "2026-08-acme", period="2026-08")
        job = self.process(job["id"])
        draft = jobs.latest_draft(self.biz, job)
        home_depot = next(t for t in draft["data"]["transactions"] if t["id"] == "T-0802")
        self.prove("The preparer now applies the learned rule on its own",
                   home_depot["category"] == MATERIALS and self.new_rule in draft["rules_applied"],
                   f"T-0802 -> {home_depot['category']} via {self.new_rule}")
        freeze_clock("2026-09-02T09:00:00")
        job = self.approve(job["id"], {}, None, minutes=4)
        self.send(job["id"])
        self.prove("Dana approved August with no corrections", job["approval"]["changes"] == 0)

    def monday(self) -> None:
        self.step("8. Monday numbers (2026-09-28)")
        freeze_clock("2026-09-28T08:00:00")
        report = metrics.business_metrics(self.biz, as_of=parse_date("2026-09-28"))
        for line in metrics.format_report(report).splitlines():
            self.say(f"  {line}")
        self.prove("The dashboard flags profit rising while a client left",
                   any("while clients left" in a for a in report["alerts"]))
        self.prove("Human minutes per job fell as rules accumulated (18 -> 11 -> 4)",
                   report["current"]["minutes_per_job"] == 4 and report["previous"]["minutes_per_job"] == 11)

    def thursday(self) -> None:
        self.step("9. Thursday: screen the next business (thesis/deals/example-target.json)")
        deal_file = self.dir / "thesis" / "deals" / "example-target.json"
        buy_box_file = self.dir / "thesis" / "buy-box.json"
        if not deal_file.exists() or not buy_box_file.exists():
            self.say("  (no example deal in this workspace; skipped)")
            return
        report = deals.score_deal(read_json(deal_file), read_json(buy_box_file))
        for line in deals.format_deal(report).splitlines()[:8]:
            self.say(f"  {line}")
        self.say("  ... full screen: python3 -m holdco deal score thesis/deals/example-target.json")
        self.prove("The deal screen caps the price at what today's earnings can carry",
                   report["max_price"] <= report["max_price_caps"]["DSCR on today's earnings"] + 0.01)

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
