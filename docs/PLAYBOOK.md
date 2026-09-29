# The TMA Holdings playbook, step by step

From zero to a one-person holding company that owns a few small service businesses, each run by
a GM with real upside, with agents doing the typing, chasing and first drafts, and a named person
approving everything before it reaches a client.

Every step says what to do, what it produces, how you know it's done, and how it is proven:

- ✅ **Tested here.** The mechanics are exercised by `python3 -m holdco demo` (22 proofs) and
  the test suite (`python3 -m unittest discover -s tests -t .`). You can re-run both in two minutes.
  That tests the machinery, not market results or the quality of Claude's drafts on your work.
- 📚 **Proven elsewhere.** Sourced precedent or rules, with dates, in `docs/VIDEO-REVIEW.md`.
  Company results there are self-reported.
- 🧪 **You prove it.** Only the market can. Each one has a gate with a pass bar and a
  kill-or-pivot rule, so you find out cheaply.

## Timeline at a glance

| Phase | When | You end with | Gate to move on |
|---|---|---|---|
| 0 Foundation | weeks 0–2 | industry, thesis, buy box, advisors | thesis and buy box signed off |
| 1 Wedge service | months 1–6 | paying firms, a rules file, owner relationships | 3 paying firms; drafts needing fixes under 20%; 2+ owners discussing succession; deal ready (lender-confirmed financing plan, final buy box, one target screened) |
| 2 Deal flow | months 3–12 (overlaps) | screened targets, a signed LOI | LOI at or below the maximum justified price |
| 3 Diligence and close | 60–120 days | financing, GM agreement, a closed deal | closed, GM signed, access and security in place |
| 4 Shadow mode | from closing until the first job type graduates (weeks for a high-volume job type) | shadow-mode data, a graduation decision | graduation criteria met and the GM agrees |
| 5 Operate | month 2 onward | the weekly rhythm, compounding rules | 8 stable Mondays |
| 6 Next business | when stable | business #2 on the same shared layer | the same gates, faster |

---

## Phase 0 — Foundation (weeks 0–2)

**0.1 See the whole machine work (1 hour).** ✅
Read `docs/VIDEO-REVIEW.md`. Then run the proof:
```bash
python3 -m holdco demo                     # three months at a fictional firm, 22 proofs
python3 -m unittest discover -s tests -t .  # the full test suite
```
Done when: you've watched a chase email wait for approval, a reviewer block a draft that didn't
tie to the bank, a repeated fix become a rule and two tests, and the next month need no edits.

**0.2 Choose the industry.** 🧪
Use the industry table in `thesis/THESIS.md` (recommended: bookkeeping). Validate the wedge offer
in your region with the `niche-validator` skill (Gate 0: real buyers, priced competitors, 50%+
gross margin, named places where owners gather).
Done when: `thesis/THESIS.md` says which industry and why, and the Gate 0 scorecard passes.
Kill/pivot: if Gate 0 fails, try the next industry on the list; the operating system doesn't change.

**0.3 Set the buy box.** ✅ mechanics / 🧪 numbers
Edit `thesis/buy-box.json` (revenue range, years, clients, maximum multiples, coverage floor,
top-client cap, billing models, GM required, and the walk-away rules under `hard_fail`).
`holdco deal score` reads it; the tests check that the maximum price it computes meets the coverage
floor exactly, that each walk-away rule means walk away, and that soft misses only mean negotiate.

**0.4 Line up three advisors.** 📚
A lawyer (entity, licensing, contracts, data), a CPA (structure, tax, IRC §7216 if you touch tax
work) and an SBA lender (pre-qualification). The SBA rules change for loans numbered on or after
Oct 1, 2026. What to ask each one is in runbooks 08 and 09.

**0.5 Set up the holdco.** 🧪 with advisors
A common shape is a holding company plus one operating company per business, so each business can
give its GM equity and carry its own loan; confirm with your lawyer and CPA. Open the bank accounts.
Remember: SBA lending requires every owner to be a US citizen or national living in the US.

**0.6 Set up data security before any client data exists.** 📚 rules / ✅ repo guardrails
Runbook 09: approved-tools list, a written information security plan, MFA. The repo already
keeps real business folders and deal files out of git (`.gitignore`).

**Gate 0:** thesis and buy box written; advisors engaged; decision recorded (template in the
skill's `references/output-templates.md`).

---

## Phase 1 — Sell a wedge service first (months 1–6)

The episode's advice for the first business, which is also the demand-first method: serve
them, earn their trust, and one day own one. Runbook 10 has the details.

**1.1 Design one offer.** 🧪
One annoying job, done with agents and checked by a person: for example, month-end cleanup for a
firm's five messiest clients, or chasing missing documents before tax season. Use `offer-architect`:
fixed scope, fixed price, fast turnaround, a real guarantee.

**1.2 Find the first firms.** 🧪
`icp-canvas` (owners of $500k–$3M firms nearby, especially owners 55+), then `lead-source-planner`
(association directories, CPA and banker referrals, direct email from you).

**1.3 Deliver on this repo's pipeline.** ✅
Each client firm is a business folder (`python3 -m holdco new-business <slug> --name ... --industry
... --gm "<their lead>" --owner "<you>"`); their staff (or you) are the approvers, and each sets an
approval passphrase once in their own terminal (`python3 -m holdco keys add <slug> --by "<name>"`).
The wedge job type runs in assisted mode from the start (runbook 10 says why and how). Work flows
through intake → preparer → reviewer → person. Tested by the demo and the workflow tests: missing
documents create a chase that waits for approval; a draft that doesn't reconcile, or whose email
states totals that don't match the books, is blocked; large unknowns are escalated, not guessed;
nothing is sent without a signed approval from a named approver; nothing changes after approval
without blocking the send.

**1.4 Improve the agents every Wednesday.** ✅
`holdco corrections review` (or the `holdco-weekly-review` workflow), then a person accepts rules
and `holdco eval` re-runs the golden cases. Proven in the demo: the same Home Depot fix in two
separate months becomes one proposed rule; accepting it creates two golden cases; both pass with the
rule and both fail if it is removed; the next month needs no edits.

**1.5 Build owner relationships.** 🧪
Quarterly check-ins; ask about their team, their plans, and succession. That's your deal pipeline.

**Gates (runbook 10):** W1 three paying firms within 90 days · W2 drafts needing fixes (edited or sent
back by a person) under 20% for 8 weeks · W3 two or more owners discussing succession · W4 deal ready:
a financing plan confirmed with a lender, the buy box final, one target screened.
Kill/pivot: under 2% replies after fixing deliverability, list and copy, and no paid pilots → change
the offer or the industry (demand-first Gate 2).

---

## Phase 2 — Deal flow (months 3–12, overlapping)

**2.1 Source.** 🧪 Your wedge clients first, then direct outreach to owners and referrals from
CPAs, bankers and attorneys. Curated sources only; open marketplaces are mostly picked over. Runbook 08.

**2.2 Listen first.** 🧪 The owner's goals (legacy, staff, clients, timing, money) decide the deal
more than price. Identify the likely GM in the first two meetings.

**2.3 Screen.** ✅
Copy `thesis/deals/example-target.json`, fill it in from the seller's numbers, and run:
```bash
python3 -m holdco deal score thesis/deals/<target>.json
```
It works out today's earnings (SDE minus the cost of replacing the owner), sources and uses, debt
service and coverage in year 1 and at peak, the most you should pay and which limit binds, SBA
pitfalls, and AI scenarios clearly labeled as upside you'd create. For a full memo, run the
`holdco-deal-screen` workflow (four lenses, a red team, a decision memo). Tested: the price cap meets
the coverage floor exactly; the walk-away rules mean walk away (industry outside the thesis,
licensing that would make you a passive owner of regulated work, coverage under 1.0x on today's
earnings, one client over 30% of revenue, no GM candidate, an owner who leaves at closing, a seller
who wants to be paid for the AI upside); seller rollover (not available with SBA money when you buy
control) and short-standby seller notes trigger SBA warnings.

**2.4 Decide.** 🧪 If it's close, use `clear-thinking-os`: the decision, your confidence, and what
would change your mind. Record it.

**2.5 Sign an LOI** 📚 at or below the maximum justified price, with SBA-compatible terms: at least
10% equity, the seller note on standby (or not counted as equity), no earnout (a retention rebate
instead), the seller as consultant only, the GM agreement as a closing condition, 60–90 days' exclusivity.

**Gate:** a signed LOI priced on today's earnings.

---

## Phase 3 — Diligence and close (60–120 days)

**3.1 Diligence** 📚/🧪: the checklist in runbook 08 (revenue and earnings quality, people,
licensing, contracts, data, agent-readiness, claims). The SBA requires an independent valuation
above a $350k price, and a quality-of-earnings report at $3M or more.
**3.2 Financing** 📚: the lender's terms; remember the $3.75M SBA guaranty cap is shared by every business you control.
**3.3 The GM deal** 🧪: runbook 11. A real raise, equity with vesting, a bonus on all five Monday numbers.
**3.4 Licensing and security pre-work** 📚: a new EFIN (tax), producer and carrier consents
(insurance), the designated broker (property management), MFA and insurance (runbooks 01, 09).

**Gate:** closed; GM agreement signed; access list complete; insurance bound.

---

## Phase 4 — Shadow mode: change nothing clients can see until the evidence says so

**4.1 Day one.** ✅ mechanics / 🧪 people
Runbook 01: tell the staff the truth, create the folder (`holdco new-business ... --gm ... --owner
"<you>"`, tested), have the GM and you each set an approval passphrase (`holdco keys add`), interview
the GM into `clients.md`, `people.md` and `rules.md`, and record baselines.

**4.2 Shadow mode.** ✅
Runbook 02. Agents draft in the background; staff do the work as always; the GM records what they
actually did (`holdco shadow`). Tested: a job type in shadow mode cannot be approved or sent;
differences are logged as corrections and feed the Wednesday review; rules learned in shadow mode are
tested against the person's own version; the person's minutes become the manual baseline in the
Monday numbers.
How long: until the graduation criteria are met, by default 20+ shadow jobs of that job type. Start
with a high-volume job type (at a bookkeeping firm, the monthly close across all clients rather than
the five messiest), so that takes weeks, not months. With the GM, you can lower `min_jobs` in
`business.json` → `graduation` for a low-volume job type, but keep it at 10 or more.

**4.3 Graduate one job type.** ✅
Runbook 03. `holdco graduation` reports the evidence (default: 20+ shadow jobs, 25% or fewer with
differences, no factual errors in the last 10); the person decides with `holdco rollout` (human-only,
tested, logged). Roll back at the first sign of trouble; after a rollback the evidence starts over.

**Gate:** the graduation criteria are met and the GM agrees.

---

## Phase 5 — Operate: the weekly rhythm

**5.1 Daily: the approval queue** ✅ `holdco queue`, `job show`, then `approve --send` in your own
terminal (it asks for your passphrase), and `holdco outbox verify` before you email anything.
Tested: only named approvers can approve; agents can't approve, answer their own questions or send;
an approval written without the passphrase is never released; an edited or planted outbox item fails
verification; edits are categorized corrections; human edits that break a blocker rule need an
explicit, logged override.
**5.2 Monday: the numbers** ✅ `holdco metrics`: margin, minutes per job, share of drafts needing
fixes, client retention, key people. Tested: it flags margin rising while a client leaves, and anyone at risk.
**5.3 Tuesday: one call per GM** 🧪 What's working, what's annoying, which clients need attention, how can I help.
**5.4 Wednesday: the corrections review** ✅ runbook 05. The most important hour of the week.
**5.5 Thursday–Friday: the next business** 🧪 runbook 08.
**5.6 When something goes wrong** ✅ runbook 06: stop the job type (`holdco rollout ... shadow`),
run `holdco outbox verify`, correct with the client by phone, fix every layer, resume through shadow
mode. A passphrase you know is right that suddenly fails is an incident too: the key file may have
been replaced.

**Gate:** 8 stable Mondays: margin steady or rising with retention steady, key people OK, no open incidents.

---

## Phase 6 — The next business

Runbook 07. Same industry: reuse almost everything; only business and client rules are new. New
industry: write the industry rules and job-type specs first, and plan a longer shadow period. Check
the financing against the shared SBA guaranty cap before signing.

---

## How this was proven

### 1. The end-to-end demo (`python3 -m holdco demo`)
Three months of work at a fictional bookkeeping firm, run with deterministic stand-in agents that
read the same rule files as the Claude agents. The simulated GM behaves the same way every month
(Acme's Home Depot runs are job materials; a review takes about 4 minutes plus 7 per fix), so the
edits, the minutes and the rule all follow from what the agents drafted rather than being typed in.
Every step asserts an invariant; all 22 held:

1. Missing receipts stop the work and create a chase for a person to approve.
2. The reviewer agent cannot approve anything.
3. The preparer agent cannot approve anything.
4. Approving from inside an agent session is refused.
5. Nothing can be sent before a person approves it.
6. Only named approvers can approve.
7. An approval written straight into the job files (no passphrase) cannot be released.
8. The reviewer blocked a draft that did not tie to the bank, and the fixed draft passed.
9. Changing the work after approval blocks the send (hash check).
10. Every human edit was logged as a categorized correction.
11. `outbox verify` passes what the GM released and flags an edited message and a planted item.
12. One job's corrections alone do not create a rule.
13. A large unknown transaction is escalated to a person, not guessed.
14. An agent cannot answer its own question.
15. The same fix in two separate jobs produced exactly one proposed rule.
16. Only a person can accept a rule.
17. The regression tests pass with the new rule and catch its removal.
18. The preparer now applies the learned rule on its own.
19. The GM's usual review finds nothing left to fix in the August draft.
20. The dashboard flags profit rising while a client left.
21. Human minutes per job fell as the rule removed fixes (18 → 11 → 4, from the review-time model above).
22. At the most you should pay, today's earnings still cover the debt 1.25x (exactly 1.25x when
    coverage is the limit that binds).

### 2. The test suite (`python3 -m unittest discover -s tests -t .`)

| File | What it proves |
|---|---|
| `test_pipeline.py` | The transition table has no agent path to approved or sent; human-only guards; named approvers; immutable drafts; hash-checked sends; machine checks veto a reviewer pass; three blocked drafts go to a person; human edits that break rules need an override; one fix is one correction |
| `test_security.py` | Key files hold no passphrase and only their owner can read them; approvals need the right passphrase; forged or moved approvals are never released; only the approver releases; the outbox check catches edited, extra, planted and re-signed items and items naming a sender outside the business, and leaves another approver's releases to them; an approval made before a key change must be approved again; state files follow the umask and keep their mode; a made-up human context fails inside an agent session; card numbers and EINs in a message are blocked; inputs changed in place are refused; job ids can't leave the jobs folder; message totals and the job's month are checked; a second chase waits three days |
| `test_record_run.py` | The path the Claude workflow uses (`record-run`): clean runs, block-then-pass, machine veto, chases, escalations, review-only rounds, invalid drafts and draft files outside `work/` refused, failed runs record nothing, derived totals may be left out |
| `test_corrections_loop.py` | Repeats across jobs become exactly one proposal; ignored rules are reported, not duplicated; style fixes become phrase rules; agent-written proposals need two separate jobs and a person to accept; a rule waits until its evidence jobs are accepted work, and a failed accept writes nothing; tampered approved output can't become a test; eval jobs stay out of the queue |
| `test_shadow.py` | Shadow drafts can't be approved or sent; differences are logged and feed the review; rules learned in shadow mode are tested against the person's version; graduation needs evidence and a person, starts over after a rollback, and can meet a bar higher than its window; the holdco owner can make the rollout call; the manual baseline shows on Monday |
| `test_rules_metrics_deals.py` | Rule parsing and layering; unknown check types fail loudly; ids never reuse a deleted number; send-backs count as drafts needing fixes; margin stops at the as-of month; retention, people and alerts; loan math against a known value; the price cap meets the coverage floor exactly; each walk-away rule, soft misses, billing models and workable licensing (PTIN, EFIN) come from the buy box; SBA warnings; the margin model |
| `test_hook.py` | The Claude Code guard blocks human-only commands however they are wrapped, switching off the agent markers, Python that patches the guard, scripts written to do either, writes to protected state and the key store; holdco agents get allow-lists; the guard files need dev mode; documentation, help and ordinary work are allowed |
| `test_cli_and_demo.py` | The CLI refuses human-only commands inside an agent or without a terminal; `--root` works anywhere and options are never guessed; agent-safe commands work; `job list --json` feeds the workflow; shadow-mode drafts point people at `shadow`, not `approve`; eval with no golden cases is not a pass; the demo's 22 proofs hold |
| `test_workflows.py` | The four Claude Code workflow scripts, run in Node with scripted agents against a real workspace: block then pass, machine veto fed back into the next draft, chases, escalations, a reviewer's question resumed with a review-only round, an incomplete intake asked again, `job list --json` passed as is, parallel jobs, the weekly review, the eval, and the deal memo |

### 3. The Claude Code workflow with real agents (live run, Sep 29, 2026)
The `holdco-process-job` workflow ran with real Claude agents (the tool-restricted `holdco-intake`,
`holdco-preparer`, `holdco-reviewer` and `holdco-clerk`) on two jobs in a sandbox copy of the demo
firm: 7 agent calls, no errors. What they wrote and what was recorded is in
`docs/evidence/live-run-2026-09-29/`; re-checked later with today's rules, the June draft still
passes every check, including the ones added since (message totals and the job's month).

| Job | What the agents did | Result |
|---|---|---|
| June close (receipts added late; the bank export has a duplicated line) | Intake found every document. The preparer categorized all 12 lines, applied the client rule for Greenleaf and the industry defaults, and found the duplicate on its own: same date, vendor and amount, only one receipt, and the books tie only without it. It excluded the line with that reason and asked the client to confirm. It also noted that the $5,230 ADP payroll is over the $5,000 threshold but matched a rule, so no question was needed. The reviewer recomputed everything and passed it (100). Machine checks: all passed. | Waiting in the approval queue. Nothing sent. |
| July close (a $6,200 transfer to an unknown party) | Intake found every document. The preparer stopped instead of guessing: *"T-0706 on 2026-07-14: 'ONLINE TRANSFER TO J SMITH' for -$6,200.00 matches no category rule and is $5,000 or more (BK-006). What is it, and what category should it go in?"* | Waiting for a person's answer. |

**What the first attempt caught.** An earlier run of the same two jobs reached the same results,
but the preparer flagged that the job-type spec's example showed the exact category the demo
expects agents to *learn* from corrections. It refused to use it ("an example, not a rule"), but
examples like that can quietly steer agents, so every example now uses made-up clients and
values, and the run above was done after that fix. That first attempt also started before the
tool-restricted agent types were registered, and the workflow fell back to default agents as designed.

**Re-run it yourself** (the sandbox is local and gitignored):
```bash
python3 -m holdco sandbox "$PWD/.sandbox"
python3 -m holdco --root "$PWD/.sandbox" job new demo-bookkeeping --type monthly-close --client acme \
  --inputs "$PWD/.sandbox/businesses/demo-bookkeeping/inbox/2026-06-acme" --period 2026-06
python3 -m holdco --root "$PWD/.sandbox" job add-inputs demo-bookkeeping 2026-06-acme-monthly-close \
  --inputs "$PWD/.sandbox/businesses/demo-bookkeeping/inbox/2026-06-acme-late-receipts"
# then, in Claude Code: "process the received jobs in .sandbox with the holdco-process-job workflow"
python3 -m holdco --root "$PWD/.sandbox" queue
```

**What it does not prove.** Two jobs are a smoke test, not a reliability measure. Reliability on
*your* work comes from shadow mode: 20+ real jobs per job type and the graduation criteria (runbook 03).

### 4. The facts
Every market, legal and financing claim used here is sourced and dated in `docs/VIDEO-REVIEW.md`,
including the ones that turned out weaker than the episode suggested.

### 5. What is not proven (and can't be from a repo)
That firms will pay for your wedge service; that an owner will sell to you at a price today's
earnings can carry; that your agents save a meaningful share of hours on *your* firm's work; that
clients and key staff stay through the change. Each is a 🧪 step above, with a gate that tells you
cheaply whether it's true.
