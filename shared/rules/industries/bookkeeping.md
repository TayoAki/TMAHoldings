# Industry rules — bookkeeping

Defaults for every bookkeeping business in the holdco. A business can override a default
(for example a client-specific category) in its own `rules.md`; it cannot override a
non-negotiable global rule.

## BK-001 · Monthly close needs the bank export and the statement
- **Applies to:** monthly-close
- **Scope:** all
- **Rule:** Before any work starts, check the job has the month's bank transactions export (`bank.csv`) and the bank statement balances (`statement.json`). If either is missing, chase it.
- **Why:** Without the statement there is nothing to reconcile against, so every number is unverified.
- **Check:** `{"type": "document_checklist", "documents": ["bank.csv", "statement.json"]}`

## BK-002 · Receipts for expenses over $75
- **Applies to:** monthly-close
- **Scope:** all
- **Rule:** Every expense over $75 needs a receipt or invoice before the month is closed. Transfers between accounts and to owners are exempt. Match receipts by date and amount.
- **Why:** Firm policy, borrowed from the IRS $75 documentary-evidence line for travel and gift expenses and applied to all expenses. Receipts are easy to get this week and hard to get at tax time.
- **Check:** `{"type": "receipt_threshold", "amount": 75, "exempt_patterns": ["TRANSFER"]}`

## BK-003 · The books must tie to the bank, to the cent
- **Applies to:** monthly-close
- **Scope:** all
- **Non-negotiable:** yes
- **Rule:** Opening balance plus every included transaction must equal the statement's closing balance exactly. If it does not tie, the draft is blocked. Look for duplicates first; if nothing explains the gap, stop and ask a person.
- **Why:** An unreconciled close is a guess. This is the single most important check in bookkeeping.
- **Check:** `{"type": "reconciliation_tied"}`

## BK-004 · Every transaction in the export is accounted for
- **Applies to:** monthly-close
- **Scope:** all
- **Non-negotiable:** yes
- **Rule:** Each line in the bank export appears in the draft, either categorized or listed as excluded with a reason. Amounts and dates are copied exactly. Nothing is added that is not in the export.
- **Why:** Silently dropped or invented transactions are how small errors become big ones.
- **Check:** `{"type": "transactions_match_input"}`

## BK-005 · Exclusions are explained and confirmed
- **Applies to:** monthly-close
- **Scope:** all
- **Rule:** When a transaction is excluded (for example a duplicate line in the export), give the reason and ask the client to confirm it, naming the transaction.
- **Why:** The client is the only one who knows whether two identical charges were one purchase or two.
- **Check:** `{"type": "exclusions_explained"}`

## BK-006 · Big unknowns go to a person
- **Applies to:** monthly-close
- **Scope:** all
- **Rule:** A transaction of $5,000 or more that matches no category rule must not be guessed. Stop and ask a person what it is.
- **Why:** Large transfers are often owner draws, loans or tax payments. Getting them wrong changes the client's profit and taxes.
- **Check:** `{"type": "large_unknown_escalation", "amount": 5000}`

## BK-007 · Small unknowns become client questions
- **Applies to:** monthly-close
- **Scope:** all
- **Rule:** A smaller transaction that matches no rule is categorized "Uncategorized" and listed as a question for the client, naming the transaction.
- **Why:** Guessing a category hides the question; asking gets the right answer and teaches us a rule.
- **Check:** `{"type": "uncategorized_have_questions"}`

## BK-008 · Default vendor categories
- **Applies to:** monthly-close
- **Scope:** all
- **Rule:** Unless a business or client rule says otherwise, use these defaults: HOME DEPOT → Repairs & Maintenance; LOWE'S → Repairs & Maintenance; SHELL, CHEVRON, EXXON → Fuel; INTUIT, QUICKBOOKS → Software; ADP, GUSTO → Payroll; STATE FARM → Insurance; COMCAST → Utilities; AMZN → Office Supplies; STRIPE, SQUARE → Sales Income.
- **Why:** Sensible starting points. Client-specific rules override them.
- **Check:** `{"type": "vendor_map", "map": {"HOME DEPOT": "Repairs & Maintenance", "LOWE'S": "Repairs & Maintenance", "SHELL": "Fuel", "CHEVRON": "Fuel", "EXXON": "Fuel", "INTUIT": "Software", "QUICKBOOKS": "Software", "ADP": "Payroll", "GUSTO": "Payroll", "STATE FARM": "Insurance", "COMCAST": "Utilities", "AMZN": "Office Supplies", "STRIPE": "Sales Income", "SQUARE": "Sales Income"}}`

## BK-009 · Close messages have a Summary and Questions
- **Applies to:** monthly-close
- **Scope:** all
- **Rule:** The client message has a "Summary" section (money in, money out, net, whether the bank ties) and a "Questions" section (or "None this month").
- **Why:** Clients skim. The same two sections every month make the email easy to act on.
- **Check:** `{"type": "required_sections", "sections": ["Summary", "Questions"]}`

## BK-010 · Chase messages are short and specific
- **Applies to:** document-chase
- **Scope:** all
- **Rule:** A document chase names every missing item (what, date, amount), says how to send it, and stays under 180 words.
- **Why:** Vague chases get ignored. Specific, short ones get answered the same day.
- **Check:** `{"type": "chase_message_format", "max_words": 180}`

## BK-011 · The message states the numbers in the books
- **Applies to:** monthly-close
- **Scope:** all
- **Rule:** The Summary's "Money in", "Money out" and "Net" lines equal the included transactions to the cent, and "Bank balance ties to your statement" says yes only when the reconciliation is tied.
- **Why:** The client reads the message, not the data file. A wrong total in the email is a wrong answer, even if the attachment is right.
- **Check:** `{"type": "message_totals"}`

## BK-012 · The books are for the job's month
- **Applies to:** monthly-close
- **Scope:** all
- **Rule:** The bank statement, the draft's period and every transaction date match the month the job is for. If the documents are for a different month, stop and ask a person.
- **Why:** Closing August with July's statement, or sending "Your October books" built from August data, is a factual error the client may never notice.
- **Check:** `{"type": "period_matches"}`
