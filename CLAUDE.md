# TMA Holdings — notes for Claude

This repo is the operating system for TMA Holdings, a one-person AI roll-up holding company.
Start with the `ai-rollup-holdco` skill (`.claude/skills/ai-rollup-holdco/SKILL.md`): it routes
every request to the right phase, runbook, command or workflow.

## Non-negotiables

- **Never run human-only commands**: `approve`, `send`, `send-back`, `answer`, `cancel`, `shadow`,
  `rollout`, `rules accept`, `rules reject`. Never build a human `ExecutionContext` in Python. They
  refuse inside Claude Code anyway (`CLAUDECODE=1`), and `.claude/hooks/human_only_guard.py` blocks
  them. When a person needs to act, give them the exact command with their name, and stop.
- **Never write protected state directly**: `job.json`, `approved.json`, outboxes, corrections and
  rollout logs, `proposals/`, `golden/`, `business.json`. The CLI writes those. Agents write drafts
  only to a job's `work/` folder.
- **Never commit real client or deal data.** Only `businesses/_template/`, `businesses/demo-*/` and
  `thesis/deals/example-*` are tracked; keep it that way.
- Legal, tax, licensing and lending statements are planning research: say so and point to advisors.

## Commands

```bash
python3 -m holdco demo --quiet               # the proof: must print "PROOF SUMMARY: 20/20 held"
python3 -m unittest discover -s tests -t .    # all tests (the workflow tests need node)
python3 -m holdco status                      # every business and what waits on a person
python3 -m holdco --help                      # everything else
python3 scripts/package_skill.py              # build dist/ai-rollup-holdco.skill for claude.ai
```

Use `--root <path>` (or `HOLDCO_ROOT`) to work in another workspace, for example a sandbox from
`python3 -m holdco sandbox .sandbox`.

## Workflows (`.claude/workflows/`)

| Workflow | Args | Does |
|---|---|---|
| `holdco-process-job` | `{root, jobs: [{business, job, state, drafts}]}` | intake → preparer → reviewer, records each round, stops at the approval queue |
| `holdco-weekly-review` | `{root, business, asOf?}` | curator + skeptic; records proposals for a person |
| `holdco-eval` | `{root, business, cases}` | re-runs the agents on golden cases and compares |
| `holdco-deal-screen` | `{root, deal, docs?}` | deal math, four lenses, red team, memo |

`root` must be an absolute path. Get `jobs` from `python3 -m holdco job list --json`.

## Code conventions

- Python 3.9+, standard library only. Data is JSON, CSV and Markdown so people and agents read the same files.
- The job state machine in `holdco/jobs.py` (`TRANSITIONS`) is the whole policy. No agent role may
  ever reach `approved` or `sent`; `tests/test_pipeline.py` checks this.
- Rules are Markdown with optional JSON checks (`shared/rules/README.md`); new check types go in `holdco/checks.py` with tests.
- After changing an agent file, a rule, or engine code: run the tests and the demo. After changing a
  workflow script: run `tests/test_workflows.py`.
