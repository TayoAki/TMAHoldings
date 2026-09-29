# TMA Holdings — TODO

Your action list, in order. Each item names who does it (**You**, **Claude**, or an **Advisor**)
and when it's done. Step numbers point into `docs/PLAYBOOK.md`; runbooks are in `shared/runbooks/`.
Tick items off here and add a dated line to "Decisions" at every gate.

## This week (Phase 0: foundation)

- [ ] **You · 1 hr** — Read `docs/VIDEO-REVIEW.md`, then run `python3 -m holdco demo` and skim the
      output. *Done when* you've seen all 22 proofs hold. (Step 0.1)
- [ ] **You + Claude** — Choose the industry. Ask Claude: *"Run niche-validator on an AI month-end
      cleanup service for bookkeeping firms in <your metro>."* Update `thesis/THESIS.md`.
      *Done when* Gate 0 passes, or you've picked the next industry to test. (Step 0.2)
- [ ] **You** — Fill in the DECIDE items in `thesis/THESIS.md`: geography, capital you can put in,
      hours per week. (Step 0.2)
- [ ] **You** — Book three calls: a lawyer (entity, licensing, contracts, data), a CPA (structure,
      tax, IRC §7216 if tax work is involved), an SBA lender (pre-qualification). Bring runbooks 08
      and 09. *New SBA rules (SOP 50 10 8.1) apply to loans numbered from Oct 1, 2026.* (Step 0.4)
- [ ] **You + Advisors** — Check the numbers in `thesis/buy-box.json` (multiples, coverage floor)
      with the lender and a broker. (Step 0.3)
- [ ] **You + Advisors** — Form the holdco entity and open bank accounts. (Step 0.5)
- [ ] **You** — Fill in the approved-tools table and start the written security plan (runbook 09). (Step 0.6)

## Phase 1: wedge service (months 1–6)

- [ ] **Claude** — Draft the wedge offer one-pager with `offer-architect` (one annoying job, fixed
      price, human-reviewed). (Step 1.1)
- [ ] **Claude** — Build the ICP canvas (`icp-canvas`) and the owner outreach plan (`lead-source-planner`). (Step 1.2)
- [ ] **You** — Start outreach, and book the first 10 owner conversations.
- [ ] **You + Claude** — Set up each paying firm as a business folder
      (`python3 -m holdco new-business <slug> --name ... --industry bookkeeping --gm "<their approver>" --owner "<you>"`),
      then switch the wedge job type to assisted, **You**: `holdco rollout <slug> monthly-close assisted`
      (runbook 10 explains why the wedge skips shadow mode). (Step 1.3)
- [ ] **You, and each approver** — Set an approval passphrase once per business, in your own terminal:
      `python3 -m holdco keys add <slug> --by "<name>"`. Approve with `approve ... --send`, and run
      `outbox verify` before emailing anything. (Step 5.1)
- [ ] **Claude, weekly** — Process client jobs (`holdco-process-job` workflow) and run the Wednesday
      review (`holdco-weekly-review`). **You** accept or reject the proposed rules. (Step 1.4)
- [ ] **You, quarterly** — A succession conversation with every owner. Keep notes. (Step 1.5)
- [ ] **Gate W1** — 3 paying firms within 90 days.
- [ ] **Gate W2** — drafts needing fixes (edited or sent back) under 20% for 8 weeks (`holdco metrics`).
- [ ] **Gate W3** — 2+ owners discussing succession.
- [ ] **Gate W4** — deal ready: a financing plan confirmed with a lender, the buy box final, one target screened.

## Phase 2: deal flow (months 3–12)

- [ ] **You** — Source: wedge clients, referrals, direct outreach (runbook 08).
- [ ] **Claude** — For each serious target: fill a deal file from the seller's numbers, run
      `python3 -m holdco deal score`, then the `holdco-deal-screen` workflow for the memo. (Step 2.3)
- [ ] **You** — Decide (use `clear-thinking-os` if it's close), and record the decision. (Step 2.4)
- [ ] **You + Lawyer** — Sign an LOI at or below the maximum justified price, with SBA-compatible terms. (Step 2.5)

## Phase 3: diligence and close

- [ ] **You + Advisors** — The diligence checklist in runbook 08 (independent valuation above $350k; QoE at $3M+).
- [ ] **You** — GM agreement signed as a closing condition (runbook 11).
- [ ] **You** — Licensing pre-work: new EFIN if there's tax work; producer and carrier consents for insurance.
- [ ] **You** — Insurance bound (E&O that covers AI-assisted work, cyber); MFA on everything.

## Phase 4: shadow mode, until the first job type graduates

- [ ] **You + GM** — Day one (runbook 01): the folder (`new-business ... --gm ... --owner`), both of
      you run `holdco keys add`, the GM interview, baselines.
- [ ] **GM** — Shadow mode for one high-volume job type (runbook 02): `holdco shadow` after every job,
      until the graduation report is ready (20+ shadow jobs by default).
- [ ] **You + GM** — Graduation decision (runbook 03): `holdco graduation`, then `holdco rollout` if ready.

## Phase 5: operate

- [ ] **GM, daily** — Clear the queue (`holdco queue`).
- [ ] **You, Monday** — `holdco metrics`; act on the alerts.
- [ ] **You, Tuesday** — One call per GM; update `pulse.csv`.
- [ ] **You + GM, Wednesday** — Corrections review, then eval.
- [ ] **Gate** — 8 stable Mondays before the next deal.

## System backlog (build when needed)

- [ ] **Claude** — Converter from QuickBooks/Xero exports to `holdco shadow --human-csv`, so shadow mode costs the GM minutes, not an hour.
- [ ] **Claude** — Email handoff: turn an approved outbox item into a *draft* in the approver's
      mailbox, with the approval hash in the footer. Never auto-send.
- [ ] **Claude** — Headless scheduled intake via the Claude API (for example nightly), with approvals still human-only.
- [ ] **Claude** — Industry pack #2 (tax prep): job types, rules, IRC §7216 consent handling, anonymized golden cases.
- [ ] **Claude** — A Monday dashboard page that reads `holdco metrics --json`.
- [ ] **Claude** — CI: run the test suite on every push (GitHub Actions).
- [ ] **You** — Encrypted, backed-up storage for real business folders (they never go in git).
- [ ] **You** — Before real client data: run agents as a separate OS user (or container) with no
      write access to business state and no access to `~/.holdco` (runbook 09). The repo's guard
      is layered, but it all runs under your account until you do this.
- [ ] **You** — Upload the skill to claude.ai: run `python3 scripts/package_skill.py`, then upload
      `dist/ai-rollup-holdco.skill` under Settings → Capabilities → Skills.

## Decisions

Add one dated line per gate (template: the skill's `references/output-templates.md`).

- 2026-09-29 · Repo set up: operating system, playbook and review in place; industry not yet chosen.
