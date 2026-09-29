# Job type: document-chase (any industry)

A short message asking a client for exactly the documents a job is missing. Created by
the intake agent when a job can't start; reviewed like any other draft; approved and sent
by a person like any other client message (G-001). The parent job waits in
`waiting_on_client` until `holdco job add-inputs` brings the documents in.

## The deliverable

```json
{
  "job_type": "document-chase",
  "client": "acme",
  "client_message": {
    "subject": "Quick request: 2 items for your June 2026 books",
    "body_markdown": "Hi Maria,\n\nWe're closing your June 2026 books and need 2 more items before we can finish:\n\n- Receipt for SHELL OIL 57442 on 2026-06-05 ($96.40)\n- Receipt for GREENLEAF NURSERY on 2026-06-18 ($1,275.50)\n\nA photo or PDF is fine. Just reply to this email.\n\nThank you!\n— Dana"
  },
  "data": {
    "missing": [
      {"document": "receipt:T-0603", "label": "Receipt for SHELL OIL 57442 on 2026-06-05 ($96.40)",
       "reason": "receipts are required for expenses over $75 (BK-002)", "transaction_id": "T-0603"}
    ],
    "parent_job": "2026-06-acme-monthly-close"
  },
  "rules_applied": ["BK-001", "BK-002"]
}
```

## Rules that matter most

- Name every missing item with what, when and how much; the `label` must appear in the body (BK-010).
- Under 180 words. Say how to send it.
- No full account numbers (G-004), no fee talk, nothing the client notes flag as sensitive.
- Don't chase the same job twice within 3 business days (intake stops and asks instead).
- Signed per the business rule.

## Why chasing is usually the first job to hand to agents

Chasing is pure follow-up, it happens on every job, staff hate it, and a wrong chase is
cheap (the client just sends the thing). It is also the first client-facing message an
agent drafts, so it's where the firm learns to trust the approval queue.
