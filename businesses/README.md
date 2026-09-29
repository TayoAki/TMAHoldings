# Businesses

One folder per business, each with the same files (see `_template/README.md`):
`business.json`, `clients.md` + `clients.csv`, `people.md` + `pulse.csv`, `rules.md`,
`corrections-log.jsonl`, `financials.csv`, plus `jobs/`, `outbox/`, `golden/` and
`proposals/`, which the `holdco` CLI creates.

- `_template/` is copied by `python3 -m holdco new-business <slug> ...`.
- `demo-bookkeeping/` is a fictional firm used by `python3 -m holdco demo` and the tests.

**Real businesses are confidential and never committed.** `.gitignore` excludes every folder
here except the template and `demo-*` folders. Keep real business folders in this workspace
(ignored by git) or in a separate private, encrypted store, and back them up.
