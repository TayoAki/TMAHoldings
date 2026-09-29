# Job types

A job type is one repeatable piece of client work: a monthly close, a document chase, an
owner statement, a renewal packet. Each one gets a spec here so every agent, every person
and the code agree on what "done" looks like.

| Job type | Industry | Spec | Engine support |
|---|---|---|---|
| `monthly-close` | bookkeeping | [monthly-close.md](monthly-close.md) | validator, machine checks, demo runner |
| `document-chase` | any | [document-chase.md](document-chase.md) | validator, machine checks, demo runner |

## Every deliverable uses the same envelope

```json
{
  "job_type": "monthly-close",
  "client": "acme",
  "client_message": {"subject": "...", "body_markdown": "..."},
  "data": { "...job-type specific..." },
  "questions_for_client": ["..."],
  "rules_applied": ["BK-003", "R-DEMO-003"],
  "assumptions": ["..."]
}
```

`client_message` is what the client reads. `data` is the structured work product: it is
what gets diffed when a person edits a draft (one correction per changed field), what the
machine checks verify, and what regression tests compare.

## Adding a job type (for a new industry or a new service)

1. **Pick one annoying, repeatable job** the firm does every week or month. Start with the
   one staff complain about most; it is usually document chasing or data entry.
2. **Write the spec** (copy `monthly-close.md`): inputs, required documents, the `data`
   shape, what makes it right, what the client message must contain.
3. **Write the rules** in `shared/rules/industries/<industry>.md`: the checklist, the
   thresholds, the non-negotiables. Plain English first; add a `Check` only where the code
   can verify it exactly.
4. **Register it** in `holdco/jobtypes.py` if it needs validation, derived fields, or
   attachments beyond the generic envelope (optional: generic job types work without code).
5. **Run it in shadow mode** (`business.json` → `rollout` → `"<job-type>": "shadow"`) for at
   least 20 jobs before a client sees an agent draft (runbooks 02 and 03).

### Starting ideas by industry

| Industry | First job type to automate | Why it's a good first job |
|---|---|---|
| Bookkeeping | monthly close for the messiest clients; missing-document chasing | pure data entry and follow-up, easy to check against the bank |
| Tax prep | source-document intake and organizer data entry | high volume, seasonal, reviewer already exists (the preparer) |
| Insurance agency | renewal packets, certificate-of-insurance requests | repetitive servicing work; licensed staff still do all selling and advice |
| Property management | owner statements, maintenance work-order triage | monthly, formulaic, reconciles to the trust account |
| Customer support | ticket triage and first-draft replies | the video's Crescendo example; humans approve before sending at first |
