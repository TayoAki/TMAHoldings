# Rules — Demo Bookkeeping Co. (fictional)

Rules that apply only to this business. Global rules: `shared/rules/global-rules.md`.
Bookkeeping defaults: `shared/rules/industries/bookkeeping.md`. Client-scoped rules
(`Scope: client:<id>`) override business rules, which override industry defaults.

New rules are added by `python3 -m holdco rules accept` after the weekly corrections
review. Write them in plain English: agents read the `Rule` line, code runs the `Check`.

## R-DEMO-001 · Acme gets its close on the 3rd
- **Applies to:** monthly-close
- **Scope:** client:acme
- **Rule:** Acme's monthly close goes out on the 3rd calendar day of the month, not the 1st business day.
- **Why:** Acme's owner asked for this in 2011 so it lands after their own payroll run.
- **Source:** onboarding interview with Dana Ruiz, 2026-06-01

## R-DEMO-002 · Every client message is signed by Dana
- **Applies to:** all
- **Scope:** all
- **Rule:** End every client message with "— Dana". Clients have worked with Dana for years; messages come from her, not from "the team".
- **Why:** Continuity. Clients should not notice the change of ownership.
- **Check:** `{"type": "signoff", "text": "— Dana"}`
- **Source:** shadow-mode runbook (02)

## R-DEMO-003 · Acme: Greenleaf Nursery purchases are Materials (COGS)
- **Applies to:** monthly-close
- **Scope:** client:acme
- **Rule:** For Acme Landscaping, categorize any transaction containing "GREENLEAF NURSERY" as "Materials (COGS)".
- **Why:** Acme resells plants to its customers, so these are cost of goods sold, not supplies.
- **Check:** `{"type": "vendor_category", "match": "GREENLEAF NURSERY", "category": "Materials (COGS)"}`
- **Source:** Dana's client notes, onboarding 2026-06-01
