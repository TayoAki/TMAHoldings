---
name: ai-rollup-holdco
description: Operating system for TMA Holdings, a one-person AI roll-up holding company. Covers choosing an industry, selling a wedge service first, sourcing and screening small service businesses (bookkeeping, tax prep, insurance agencies, property management), deal math and SBA financing, LOIs, choosing a GM, day one and shadow mode after closing, running intake, preparer and reviewer agents with a named person approving everything before it reaches a client, the corrections log, the Wednesday rules review, golden-case evals, and the Monday numbers. Use whenever the user mentions TMA Holdings, the holdco, an AI roll-up, buying, screening or valuing a business, a GM, onboarding an acquired firm, the approval queue, corrections, rules, runbooks, agent job files, metrics, or asks what is next on the roll-up, even if they never name this skill.
---

# AI Roll-Up Holdco OS (TMA Holdings)

TMA Holdings buys small, trusted service businesses from retiring owners, keeps the people
clients are loyal to, runs agents in the background to do the typing, chasing and first
drafts, and keeps a named person accountable for everything a client sees. A GM with real
upside runs each business; the holdco supplies a shared layer of agents, rules, back office
and dashboards that gets better every week.

Everything below points at files in the TMAHoldings repo. In a packaged copy of this skill
the same files are bundled under `references/` with the same paths (for example
`references/docs/PLAYBOOK.md`).

## Non-negotiables

1. **A named person approves everything before it reaches a client.** Agents draft, check and
   ask; they never approve or send. In the repo this is enforced by code (the CLI refuses
   inside agent sessions; a guard hook blocks attempts; a content hash is checked at send).
   Never try to get around it. When a person needs to act, give them the exact command.
2. **Price on what the business makes today.** The AI upside is yours to create, not the
   seller's to charge for. Coverage must work on today's earnings.
3. **The first 30 days change nothing a client can see.** New job types start in shadow mode.
4. **Every human fix is logged; repeats become rules; every accepted rule becomes a test.**
5. **Buy slowly.** The next deal waits until every business has had 8 stable Mondays.
6. **Evidence before claims.** Fund results (Thrive Holdings, General Catalyst) are
   self-reported signals, not proof. Legal, tax, licensing and lending points go to a
   professional before anyone relies on them; say so plainly and move on.

## Where are we? Route by phase

Diagnose from the repo before asking: run `python3 -m holdco status`, read `TODO.md`, and
check `thesis/THESIS.md`. Ask only for what those don't answer.

| Phase | You're here if | Do | Use | Leave when |
|---|---|---|---|---|
| 0 Foundation | no industry or thesis chosen | pick the industry, fill in the thesis and buy box, line up a lawyer, CPA and SBA lender | `thesis/THESIS.md`, `niche-validator` skill | thesis + buy box signed off |
| 1 Wedge service | no paying firms yet | sell one annoying job, done with agents, to firms in the industry | runbook 10; `offer-architect`, `icp-canvas`, `lead-source-planner`, `demand-first-os` | 3 paying firms, drafts needing fixes under 20%, 2+ owners talking succession |
| 2 Deal flow | owners are open to selling | source and screen; price on today's earnings | runbook 08, `holdco deal score`, the deal-screen workflow, `clear-thinking-os` | LOI signed |
| 3 Close | LOI signed | diligence, financing, GM agreement, security | runbooks 08, 09, 11 | closed |
| 4 First 30 days | just closed | day one, then shadow mode | runbooks 01, 02 | graduation report ready and the GM agrees |
| 5 Operate | a job type is in assisted mode | the weekly rhythm | runbooks 03, 04, 05, 06 | 8 stable Mondays |
| 6 Next business | stable everywhere | repeat, reusing the shared layer | runbook 07 | — |

The full step-by-step guide, with exit criteria and how each step was proven, is
`docs/PLAYBOOK.md`. The review of the source episode and its fact-check is `docs/VIDEO-REVIEW.md`.

## Task recipes

**Process client work** (the agent pipeline)
1. `python3 -m holdco job list --json` and pick jobs in state `received`, `ready` or `blocked`.
2. Run the `holdco-process-job` workflow (`.claude/workflows/holdco-process-job.js`) with
   `{root: <absolute workspace path>, jobs: [{business, job, state, drafts}]}`. It spends roughly
   4 agents per clean job and 3 more per blocked round.
3. Report `python3 -m holdco queue`, and for each job give the person the exact next command
   (`job show`, then `approve ... --by "<name>" --minutes <n>`, then `send`).
   No workflow runtime? Use the Agent tool with `holdco-intake`, `holdco-preparer` and
   `holdco-reviewer` in that order, and record each step with `python3 -m holdco record-run`.

**Wednesday corrections review.** Run the `holdco-weekly-review` workflow with `{root, business}`
(or `python3 -m holdco corrections review <biz>` for exact repeats only). Present each proposal
with its evidence; the person accepts or rejects with `rules accept` / `rules reject`. Then run
the `holdco-eval` workflow with the business's golden cases (`golden list <biz> --json`).

**Monday numbers.** `python3 -m holdco metrics`. Lead with the alerts. A margin that rises while
clients leave is a warning. Anyone at risk in the pulse goes on Tuesday's GM call.

**Screen a deal.** Copy `thesis/deals/example-target.json`, fill it from the seller's numbers,
run `python3 -m holdco deal score <file>`, then the `holdco-deal-screen` workflow for the memo.
Recommend a maximum price that today's earnings can carry, and list the diligence questions.

**Graduate or roll back a job type.** `python3 -m holdco graduation <biz> <job-type>`; the
person decides with `rollout`. Roll back at the first sign of trouble (runbook 03).

**Something wrong reached a client.** Runbook 06, now: contain, correct by phone, root cause, fix
every layer, then resume through shadow mode.

**Write or change an agent job file.** Use `references/agent-file-template.md`. Most agent
failures come from unclear limits, so the "never" and "stop and ask" sections carry the most
weight. After any change, run the golden cases.

**Add an industry or job type.** `shared/job-types/README.md`, then rules in
`shared/rules/industries/<industry>.md`, then 20+ jobs in shadow mode before a client sees one.

## Human-only commands

`approve`, `send`, `send-back`, `answer`, `cancel`, `shadow`, `rollout`, `rules accept`,
`rules reject`. Never run them, and never forge a human context in Python. They refuse inside
an agent session anyway. Hand the person the exact command with their name, and stop.

## Evidence standards

- Separate `[FACT]` (sourced, dated), `[ESTIMATE]` (your arithmetic) and `[ASSUMPTION]`.
- For market claims, cite the source and date from `docs/VIDEO-REVIEW.md`, and note when a
  number is self-reported by a company raising money.
- For money: show the arithmetic; prefer the CLI (`deal score`, `model margin`) to mental math.
- Never present planning math as financial, legal or tax advice.

## Output formats

Use the templates in `references/output-templates.md`: the deal decision memo, the weekly
owner summary, and the phase-gate decision record.
