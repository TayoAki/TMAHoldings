# TMA Holdings — notes for Claude

This repo is the operating system for TMA Holdings, a one-person AI roll-up holding company.
Start with the `ai-rollup-holdco` skill (`.claude/skills/ai-rollup-holdco/SKILL.md`): it routes
every request to the right phase, runbook, command or workflow.

## Non-negotiables

- **Never run human-only commands**: `approve`, `send`, `send-back`, `answer`, `cancel`, `shadow`,
  `rollout`, `rules accept`, `rules reject`, `keys add`, `outbox verify`. Never patch the guard,
  strip `CLAUDECODE`/`HOLDCO_AGENT`, or fake a terminal to get around it. The library refuses these
  in an agent session, approvals and sends need the approver's passphrase, and
  `.claude/hooks/human_only_guard.py` blocks them; none of that is a reason to try. When a person
  needs to act, give them the exact command with their name, and stop.
- **Never write protected state directly**: `job.json`, `approved.json`, a job's `input/` and
  `drafts/`, outboxes, corrections and rollout logs, `proposals/`, `golden/`, `business.json`, and
  the key store (`~/.holdco`). The CLI writes those. Agents write drafts only to a job's `work/` folder.
- **Never commit real client or deal data.** Only `businesses/_template/`, `businesses/demo-*/` and
  `thesis/deals/example-*` are tracked; keep it that way.
- Legal, tax, licensing and lending statements are planning research: say so and point to advisors.

## Commands

```bash
python3 -m holdco demo --quiet               # the proof: must print "PROOF SUMMARY: 22/22 held"
python3 -m unittest discover -s tests -t .    # all tests (the workflow tests need node)
python3 -m holdco status                      # every business and what waits on a person or an agent
python3 -m holdco --help                      # everything else
python3 scripts/package_skill.py              # build dist/ai-rollup-holdco.skill for claude.ai
```

`--root <path>` (or `HOLDCO_ROOT`) works in another workspace, for example a sandbox from
`python3 -m holdco sandbox .sandbox`. It is accepted anywhere; put it last
(`python3 -m holdco queue --root /abs/path`) so commands match the permission rules in
`.claude/settings.json`.

## Workflows (`.claude/workflows/`)

| Workflow | Args | Does |
|---|---|---|
| `holdco-process-job` | `{root, jobs}` | intake → preparer → reviewer, records each round, stops at the approval queue |
| `holdco-weekly-review` | `{root, business, asOf?}` | curator + skeptic; records proposals for a person |
| `holdco-eval` | `{root, business, cases}` | re-runs the agents on golden cases and compares |
| `holdco-deal-screen` | `{root, deal, docs?}` | deal math, four lenses, red team, memo |

`root` must be an absolute path. For `jobs`, pass the output of
`python3 -m holdco job list <business> --json --root <root>` as it is; the workflow handles
jobs that are received, ready, drafted (waiting for review) or blocked.

## Working on the holdco itself

In a normal session the guard hook refuses edits to the guard (`.claude/hooks/`,
`.claude/settings*.json`, `holdco/guard.py`, `holdco/keys.py`) and to any script or test that
patches the guard or writes holdco state. A person who wants Claude to work on those starts
Claude Code with `HOLDCO_DEV=1`. If you are blocked by this, tell the person why and stop; never
work around it. Dev mode never unlocks human-only commands, client state or the key store.

## Code conventions

- Python 3.9+, standard library only. Data is JSON, CSV and Markdown so people and agents read the same files.
- The job state machine in `holdco/jobs.py` (`TRANSITIONS`) is the whole policy. No agent role may
  ever reach `approved` or `sent`; `tests/test_pipeline.py` checks this, and `tests/test_security.py`
  checks signatures, forged approvals and the outbox.
- Rules are Markdown with optional JSON checks (`shared/rules/README.md`); a new check type goes in
  `holdco/checks.py` (`CHECKS`) and `holdco/rules.py` (`KNOWN_CHECK_TYPES`), with tests.
- After changing an agent file, a rule, or engine code: run the tests and the demo. After changing a
  workflow script: run `tests/test_workflows.py`. After changing the hook: run `tests/test_hook.py`.
