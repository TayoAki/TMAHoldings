# Golden cases (shared)

"A folder of real accepted work that you use to test the agents every time you change
something."

Golden cases are created automatically when a person accepts a proposed rule
(`python3 -m holdco rules accept`): each job that taught the rule becomes a case with its
**original input** and the **output a person approved**. Business-specific cases live in
`businesses/<business>/golden/` (confidential, not in git). This shared folder is for
**anonymized** cases that test global and industry rules across every business.

## When to run them

- After editing any agent file in `shared/agents/`.
- After editing or accepting any rule.
- Before moving a job type from shadow to assisted mode.
- Before plugging a newly acquired business into the shared layer.

```bash
python3 -m holdco eval demo-bookkeeping                        # deterministic demo runner
python3 -m holdco eval demo-bookkeeping --without R-DEMO-004   # what breaks if a rule is lost?
# Claude agents: run the holdco-eval workflow (see .claude/workflows/holdco-eval.js)
```

## Promoting a case to shared

1. Copy `businesses/<biz>/golden/G-xxxx/` here as `shared/golden/<industry>/<case-id>/`.
2. Replace client names, contacts, account last-4s, addresses and vendor names that could
   identify a client with neutral placeholders. Keep amounts, dates and the structure.
3. Re-run the case against the anonymized expected output, and have a person check that
   nothing identifying remains before committing.

Agents can't write inside this folder (the guard hook blocks it): promotion is a person's job.
Never edit an `expected.json` to make a failing test pass. If the accepted output was
wrong, a person retires the case (deletes it) and says why in the corrections log.
