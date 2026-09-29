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
python3 -m holdco demo                     # three months at a fictional bookkeeping firm: 20 proofs
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
approves everything**, is enforced three ways, not by asking agents nicely:

1. The `holdco` CLI refuses approve, send, answer, shadow, rollout and rules accept inside an agent
   session (Claude Code sets `CLAUDECODE=1`) or without an interactive terminal.
2. A Claude Code hook (`.claude/hooks/human_only_guard.py`) blocks those commands, and any write to
   outboxes, approvals, job state, logs or golden cases, before the tool call runs.
3. `send` checks the content hash of exactly what the person approved.

Code checks sit behind the plain-English rules, so a failing blocker check (books that don't tie,
an unmasked account number, a big transaction nobody asked about) blocks a draft even if the reviewer
agent passed it.

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
python3 -m holdco queue
python3 -m holdco job show <business> <job>
python3 -m holdco approve <business> <job> --by "Your Name" --minutes 6
python3 -m holdco send <business> <job> --by "Your Name"
```

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

- The demo's agents are deterministic stand-ins that prove the mechanics. Real work runs through the
  Claude agents and workflows in `.claude/`.
- Nothing here proves the market: that firms will buy the wedge service, that an owner will sell at a
  price today's earnings can carry, or that your clients and staff stay. The playbook gives each of
  those a gate.
- Legal, tax, licensing and lending content is planning research with sources, not advice. Confirm it
  with your lawyer, CPA and lender.
