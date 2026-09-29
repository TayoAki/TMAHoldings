# Live run with real Claude agents, Sep 29, 2026

What the `holdco-process-job` workflow recorded when it ran with real Claude agents (the
tool-restricted `holdco-intake`, `holdco-preparer`, `holdco-reviewer` and `holdco-clerk` types) on
two jobs in a sandbox copy of the fictional demo firm. Everything here is fictional demo data.
The narrative is in `docs/PLAYBOOK.md`, "How this was proven", part 3.

| Job | Files | Outcome |
|---|---|---|
| `2026-06-acme-monthly-close` | `intake.json` (intake agent), `work/draft.v1.json` (preparer), `work/run-1.json` (what the clerk passed to `holdco record-run`), `drafts/v1.json` + `v1.md` (the recorded draft), `job.json` (state and history) | Intake complete; the preparer excluded the duplicated bank line T-0611 on its own and asked the client to confirm; the reviewer passed it (100); machine checks passed. Left in the approval queue. |
| `2026-07-acme-monthly-close` | `intake.json`, `work/run-1.json`, `job.json` | Intake complete; the preparer stopped and asked a person about the $6,200 transfer to J SMITH (T-0706) instead of guessing. Left waiting for an answer. |

The client documents are the demo inbox (`businesses/demo-bookkeeping/inbox/2026-06-acme`,
`2026-06-acme-late-receipts` and `2026-07-acme`), so they are not copied here.

## Read with care

- These records come from the engine as it was that day. Later changes (input hashes, signed
  approvals, the message-totals and period checks) are not in them; nothing here was approved or
  sent, so no signature was due. Re-checked afterwards with today's rules, the June draft still
  passes every check, including the message totals (BK-011) and the month (BK-012).
- Two jobs are a smoke test that the workflow, the agents and the recording fit together. They say
  nothing about accuracy at volume: that is what shadow mode and the graduation report measure
  (runbooks 02 and 03).
- No model identifiers are recorded in these files.
