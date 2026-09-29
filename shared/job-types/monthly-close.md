# Job type: monthly-close (bookkeeping)

Close one client's month: categorize every bank transaction, reconcile to the statement,
and send the client a short summary with any questions.

## Inputs (`jobs/<job-id>/input/`)

| File | Required | Content |
|---|---|---|
| `bank.csv` | yes (BK-001) | `id,date,description,amount` — one row per bank line; debits negative |
| `statement.json` | yes (BK-001) | `{"period", "account": "... ****4821", "opening_balance", "closing_balance"}` |
| `receipts.csv` | for BK-002 | `date,vendor,amount` — receipts on file, matched to expenses by date and amount |

People's answers to earlier questions are in `job.json` → `answers`, keyed by transaction id
(e.g. `{"T-0706": "Owner's Draw"}`). Use them; don't ask again.

## The deliverable

Write this to the path you are given (`work/draft.vN.json`):

```json
{
  "job_type": "monthly-close",
  "client": "acme",
  "client_message": {
    "subject": "Your June 2026 books are ready for review",
    "body_markdown": "Hi Maria,\n\nYour June 2026 books are closed. Here's the short version.\n\n## Summary\n- Money in: $14,935.00\n- Money out: $8,349.39\n- Net: $6,585.61\n- Bank balance ties to your statement: yes\n\n## Questions\n1. We left out T-0611 because it looks like a duplicate line in the bank export. Please confirm there was only one purchase.\n\nThe full categorized list is attached.\n\n— Dana"
  },
  "data": {
    "period": "2026-06",
    "transactions": [
      {"id": "T-0602", "date": "2026-06-03", "description": "HOME DEPOT #4410", "amount": -843.10, "category": "Materials (COGS)"}
    ],
    "excluded": [
      {"id": "T-0611", "reason": "Duplicate of T-0610 in the bank export (same date, description and amount). The statement balance only ties without it."}
    ],
    "summary": {"income": 14935.00, "expenses_by_category": {"Payroll": 5230.00}, "net": 6585.61},
    "reconciliation": {"opening_balance": 12450.00, "closing_balance": 19035.61,
                       "computed_closing": 19035.61, "difference": 0.00, "status": "tied"}
  },
  "questions_for_client": ["We left out T-0611 because ..."],
  "rules_applied": ["BK-003", "BK-004", "R-DEMO-002", "R-DEMO-003"],
  "assumptions": []
}
```

Rules for the fields:
- `transactions`: every bank line that is not excluded, with the **same id, date, description and
  amount as the input** (BK-004). Categories come from rules, most specific first; people's
  answers override defaults.
- `excluded`: only with a reason, and only with a client question that names the id (BK-005).
- `summary` and the reconciliation's `computed_closing`, `difference`, `status` are **derived**:
  the engine recomputes them on approval, and they are never logged as corrections.
- `reconciliation.status` is `tied` only if `opening + sum(transactions) == closing` to the cent (BK-003).
- Amounts are numbers (not strings), debits negative.

## Client message

- Greeting with the contact name from `clients.csv`.
- `## Summary`: money in, money out, net, and whether the bank ties (BK-009).
- `## Questions`: numbered, each naming the transaction id; or "None this month."
- Sign-off per the business rule (demo: "— Dana"). No fee talk, no tax advice (G-003).

## Done means

- Machine checks pass: `python3 -m holdco check <business> <job-id>`.
- The reviewer passes it, then a named approver approves it.
- Regression tests compare `categories` (by transaction id), the `excluded` ids, and
  `reconciliation.status`. Wording can change between versions; those facts cannot.
