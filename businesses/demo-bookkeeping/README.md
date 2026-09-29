# Demo Bookkeeping Co. (fictional)

A made-up bookkeeping firm used to prove the operating system works. Nothing here is a
real business, client or person. `python3 -m holdco demo` runs three months of its work
in a throwaway copy; the files in this folder never change.

- **What it does:** monthly bookkeeping and closes for ~40 small local businesses, fixed monthly fees
- **Size (fictional):** ~$500k revenue, 5 staff, margin 8.5% at acquisition (see financials.csv)
- **Acquired:** 2026-06-01 (fictional). GM: Dana Ruiz, senior bookkeeper, 15 years at the firm
- **Job types and rollout:** monthly-close and document-chase in *assisted* mode (agents draft, Dana approves)
- **Clients in the demo:** Acme Landscaping (active), Bluebird Bakery (active), Northside Dental (left 2026-08-15)

What the demo exercises: missing receipts → chase email → approval; a duplicate bank
line → reviewer block → preparer fix; a $6,200 unknown transfer → the preparer stops and
asks; Dana's repeated Home Depot fix → a proposed rule → accepted → two regression tests
→ the next month needs no edits; the Monday numbers flag profit rising while a client left.

`inbox/` holds the client documents for each month (bank export, statement, receipts).
