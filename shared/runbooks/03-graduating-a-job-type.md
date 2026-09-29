# 03 · Graduating a job type (shadow → assisted), and rolling back

Graduation is per job type, per business. Evidence first, then the GM's agreement.

## The evidence
```bash
python3 -m holdco graduation <biz> <job-type>
```
Default criteria (override in `business.json` → `"graduation": {...}`):

| Criterion | Default | Why |
|---|---|---|
| Shadow jobs | ≥ 20 | enough to see the patterns, including the monthly oddities |
| Jobs where the agent differed from the person | ≤ 25% | most differences should already be rules |
| Factual errors in the last 10 shadow jobs | 0 | preferences can be corrected at approval; wrong facts should not reach it |

## The decision
1. Read the report with the GM. Ask: "Would you be comfortable approving these drafts after a
   quick read?" If the GM says no, the answer is no, whatever the numbers say.
2. Run the golden cases: `python3 -m holdco eval <biz>` (demo runner) or the `holdco-eval` workflow.
3. Switch, **(you)**:
   `python3 -m holdco rollout <biz> <job-type> assisted --by "<you>" --reason "graduation report ready; GM agrees"`
   The decision is logged in `rollout-log.jsonl`.

## The first two weeks in assisted mode
- The GM approves every job and records minutes (`--minutes`). Watch minutes per job and the
  share of drafts needing fixes on Monday.
- Nothing changes about the rule: a person approves everything before it reaches a client.

## Roll back to shadow when
- A factual error reaches the approval queue twice in a week, or
- the share of drafts needing fixes doubles for two weeks running, or
- anything wrong reaches a client (runbook 06), or
- the GM asks.

**(you)** `python3 -m holdco rollout <biz> <job-type> shadow --by "<you>" --reason "..."`
Rolling back is not failure; it's the system working.
