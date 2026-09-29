# TMA Holdings

The operating system for a one-person AI roll-up holding company: buy small, trusted service
businesses from retiring owners, keep the people clients are loyal to, run agents in the
background to do the typing, chasing and first drafts, and keep a named person accountable
for everything a client sees.

Built from Greg Isenberg's episode "$5T opportunity: AI Roll Ups" (Sep 28, 2026), fact-checked,
filled in where it was thin (licensing, client-data law, SBA financing, margin math), and made
runnable.

## Start here

1. **[`TODO.md`](TODO.md)**: your action list, in order.
2. **[`docs/PLAYBOOK.md`](docs/PLAYBOOK.md)**: the step-by-step guide, with how each step is proven.
3. **[`docs/VIDEO-REVIEW.md`](docs/VIDEO-REVIEW.md)**: the detailed review, the fact-check, and the sources.
4. **[`thesis/THESIS.md`](thesis/THESIS.md)**: what we buy and why (a draft for you to decide).

## See it work (2 minutes)

Requires Python 3.9+ and nothing else. Node is optional; it only runs the workflow tests.

```bash
python3 -m holdco demo                     # three months at a fictional bookkeeping firm: 22 proofs
python3 -m unittest discover -s tests -t .  # the full test suite
python3 -m holdco deal score thesis/deals/example-target.json
python3 -m holdco model margin              # what "5–10% to 30–40% margins" actually requires
```

## How it works

```
work arrives ─► INTAKE ──► PREPARER ──► REVIEWER ──► a named PERSON approves ──► a PERSON sends
                  │           ▲             │               │
                  │           └── blocked ──┘               └─ every edit ─► corrections log
                  └─ missing documents? drafts a chase (a person approves it too)
                                                                       │
            Wednesday: fixes repeated across jobs ─► proposed rules ─► a person accepts
                       ─► the rule goes in rules.md, and the jobs it came from become regression tests
```

The rule that prevents most disasters, that **the reviewer can block but never send, and a person
approves everything**, is enforced in code, in layers, not by asking agents nicely:

1. **The library refuses.** Human-only actions (approve, send, send-back, answer, cancel, shadow,
   rollout, rules accept/reject, keys add, outbox verify) check the real process: they refuse when an
   agent marker is set (Claude Code sets `CLAUDECODE=1`) or there is no interactive terminal, whatever
   the caller claims.
2. **Approvals are signed.** Approving and sending need the approver's passphrase. Each approval and
   each release is signed with a key derived from it, so `send` refuses an approval nobody signed, and
   `holdco outbox verify` flags anything you released that was edited or added to afterwards, and any
   item that wasn't released by one of the business's approvers or owners. Keys are personal, so each
   person verifies what they released. Run it before you email anything.
3. **A Claude Code hook** (`.claude/hooks/human_only_guard.py`) blocks human-only commands, attempts to
   switch off the agent markers, and writes to job state, inputs, outboxes, logs, golden cases and the
   key store before a tool call runs. The holdco agents get allow-lists: drafts in a job's `work/`
   folder and agent-safe commands, nothing else.
4. **Evidence is hashed.** Inputs, drafts and approved output are hashed when recorded, and anything
   changed outside the CLI is refused.

Code checks also sit behind the plain-English rules, so a failing blocker check (books that don't tie,
totals in the email that don't match the books, an unmasked account number, a big transaction nobody
asked about) blocks a draft even if the reviewer agent passed it.

What this does not stop: a program running under your own OS account that is determined to cheat can
rewrite code and files. It still can't sign as you without your passphrase, and `outbox verify`
catches what it leaves in the outbox. For real client data, run agents as a separate OS user that
can write only the `jobs/` and `proposals/` folders (where they record work through the CLI) and
can't touch the outbox, golden cases, logs, `business.json` or `~/.holdco` (runbook 09 shows how).

## The folder structure is the org chart

| In the episode | Here |
|---|---|
| Thesis | `thesis/THESIS.md`, `thesis/buy-box.json`, `thesis/deals/` |
| Shared: agents | `shared/agents/*.md` (plain-English job files), wrapped by `.claude/agents/holdco-*.md` |
| Shared: global rules | `shared/rules/global-rules.md`, plus industry rules in `shared/rules/industries/` |
| Shared: accepted work used as tests | golden cases: `businesses/<biz>/golden/`, `shared/golden/` |
| Shared: runbooks | `shared/runbooks/` (day one, shadow mode, weekly rhythm, incidents, deals, data security, ...) |
| Shared: dashboards | `python3 -m holdco metrics` (the five Monday numbers, with alerts) |
| Per business: clients, people, rules, corrections log | `businesses/<biz>/clients.md` + `.csv`, `people.md` + `pulse.csv`, `rules.md`, `corrections-log.jsonl` |

## Using it with Claude Code

The `ai-rollup-holdco` skill loads automatically in this repo. Things to say:

- *"What's next for TMA Holdings?"* It reads `TODO.md` and `holdco status` and routes by phase.
- *"Process the new jobs for demo-bookkeeping."* Runs the `holdco-process-job` workflow, then tells
  you what's waiting for your approval.
- *"Run the Wednesday review for <business>."* Runs the `holdco-weekly-review` workflow (a curator,
  plus a skeptic that challenges each proposed rule).
- *"Screen the deal in thesis/deals/<target>.json."* Deal math, four diligence lenses, a red team, and a memo.

Claude never approves or sends. You do, in your own terminal:

```bash
python3 -m holdco keys add <business> --by "Your Name"       # once per business: your approval passphrase
python3 -m holdco queue
python3 -m holdco job show <business> <job>
python3 -m holdco approve <business> <job> --by "Your Name" --minutes 6 --send
python3 -m holdco outbox verify <business> --by "Your Name"  # before you email anything
```

(`approve` without `--send` leaves it approved; `send` releases it later.) To have Claude work on the
holdco itself (the guard, the engine's tests), start Claude Code with `HOLDCO_DEV=1`; in a normal
session the hook refuses changes to the guard.

To use the skill in the Claude app as well: `python3 scripts/package_skill.py`, then upload
`dist/ai-rollup-holdco.skill`.

## Layout

```
holdco/            the engine (Python standard library only): jobs, checks, corrections, golden, metrics, deals, CLI
shared/            agents, rules, job types, runbooks, shared golden cases
businesses/        _template/ and a fictional demo firm (real businesses are gitignored)
thesis/            thesis, buy box, deal files (real deals are gitignored)
docs/              PLAYBOOK.md, VIDEO-REVIEW.md
.claude/           skill, subagents, workflows, guard hook, settings
tests/             unit, CLI, demo, hook and workflow tests
```

## Limits, plainly

- The demo runs deterministic stand-ins for the agents, so it tests the pipeline, the checks and the
  rules, not the quality of Claude's drafts. The Claude workflows were run end to end on the demo firm
  (`docs/evidence/`): that shows they work, not that they are accurate on your clients' books.
  Shadow mode measures that, job by job, before anything goes live.
- Nothing here proves the market: that firms will buy the wedge service, that an owner will sell at a
  price today's earnings can carry, or that your clients and staff stay. The playbook gives each of
  those a gate.
- Legal, tax, licensing and lending content is planning research with sources, not advice. Confirm it
  with your lawyer, CPA and lender.
