# Rules

Rules are how the holdco remembers. Agents read the plain-English `Rule` line; the code
runs the optional `Check`. Every accepted rule also has regression tests (golden cases)
built from the jobs that taught it.

## Layers (most specific wins)

| Layer | File | Example |
|---|---|---|
| client | `businesses/<biz>/rules.md` with `Scope: client:<id>` | Bluebird's Restaurant Depot runs are Ingredients (COGS) |
| business | `businesses/<biz>/rules.md` | Every message is signed "— Dana" |
| industry | `shared/rules/industries/<industry>.md` | Books must tie to the bank to the cent |
| global | `shared/rules/global-rules.md` | Nothing reaches a client without a person's approval |

`Non-negotiable: yes` rules can never be overridden by a more specific layer.
If you set up only three files, set up the global rules, each business's rules, and the
corrections log: that's what turns agents into something you can trust with a client.

## Format

```markdown
## R-DEMO-012 · Bluebird Bakery: Restaurant Depot purchases are Ingredients (COGS)
- **Applies to:** monthly-close            (comma-separated job types, or all)
- **Scope:** client:bluebird               (or all)
- **Non-negotiable:** yes                  (optional)
- **Rule:** For Bluebird Bakery, categorize any transaction whose description contains "RESTAURANT DEPOT" as "Ingredients (COGS)".
- **Why:** Fixed 3 times across 2 jobs by Dana Ruiz. Evidence: C-0031, C-0032, C-0035.
- **Check:** `{"type": "vendor_category", "match": "RESTAURANT DEPOT", "category": "Ingredients (COGS)"}`
- **Source:** weekly corrections review, proposal P-0007
- **Added:** 2026-08-05 by Dana Ruiz

(An illustration: this rule is not in the demo firm's `rules.md`.)
```

IDs: `G-###` global, `<INDUSTRY>-###` industry (e.g. `BK-###`), `R-<BUSINESS>-###` business.
`python3 -m holdco rules list <business>` shows what applies; a rule file that doesn't
parse fails loudly the next time any command loads it.

## Supported check types

A blocker check that fails blocks the draft even if the reviewer agent passed it.

| Type | Stage | What it verifies | Fields |
|---|---|---|---|
| `document_checklist` | intake | required files are in `input/` | `documents` |
| `receipt_threshold` | intake | a receipt (date + amount) for every expense over the amount | `amount`, `exempt_patterns` |
| `vendor_map` | preparer | default categories by description pattern | `map` |
| `vendor_category` | preparer + review | matching transactions carry this category | `match`, `category`, `severity` (blocker) |
| `reconciliation_tied` | review | opening + included transactions = statement closing, to the cent; finds the duplicate that explains a gap | — |
| `transactions_match_input` | review | every input line included or excluded; nothing invented or altered | — |
| `exclusions_explained` | review | each exclusion has a reason and a client question naming it | — |
| `uncategorized_have_questions` | review | each "Uncategorized" item has a client question naming it | — |
| `large_unknown_escalation` | preparer + review | items at or over the amount with no rule were asked about, not guessed | `amount` |
| `no_phrases` | review | the client message avoids these phrases | `phrases`, `severity` (blocker) |
| `mask_numbers` | review | no full account numbers or SSNs in the client message | — |
| `required_sections` | review | the message has these `##` sections | `sections`, `severity` (major) |
| `signoff` | review | the message is signed this way | `text`, `severity` (minor) |
| `chase_message_format` | review | a chase names every missing item and stays under the word limit | `max_words` |
| `message_totals` | review | the Summary's Money in / Money out / Net equal the included transactions, and "ties to your statement" matches the reconciliation | — |
| `period_matches` | review | the statement, the draft's period and every transaction date match the job's month | — |

New check types are small Python functions in `holdco/checks.py` (add each to `CHECKS` there and
to `KNOWN_CHECK_TYPES` in `holdco/rules.py`; an unknown type fails loudly). Add one only when the
same rule keeps being broken and can be verified exactly; a plain-English rule is enough
for everything else.
