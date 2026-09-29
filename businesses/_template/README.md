# REPLACE: Business name

One page a new person (or agent) can read to understand this business.

- **What it does:** services, typical client, how it bills (fixed fee / hourly / mixed)
- **Size:** revenue, SDE, staff, number of clients (at acquisition)
- **Acquired:** date, price, structure (cash / loan / seller note / rollover, which SBA money rules
  out when you buy control), seller transition period
- **GM:** name, their upside (see thesis/THESIS.md → GM deal)
- **Systems:** ledger software, document portal, email, payroll, anything client-facing
- **Job types and rollout:** which work runs in shadow mode vs assisted mode (business.json → rollout)
- **Day-one notes:** link to the day-one interview notes
- **Risks:** key-person risk, client concentration, anything the diligence flagged

Files in this folder:
- `business.json` config: GM, approvers (client work), owners (rules, rollout, incidents), rollout
  per job type, thresholds, graduation criteria. Written by `holdco new-business` and `rollout`;
  each approver and owner also sets a passphrase once with `holdco keys add` (kept in `~/.holdco`,
  never here)
- `clients.md` + `clients.csv` who the clients are (judgment + roster)
- `people.md` + `pulse.csv` who knows what + the weekly GM check-in on key people
- `rules.md` rules only this business follows
- `corrections-log.jsonl` every human fix to agent work (written by the holdco CLI)
- `financials.csv` monthly revenue and costs for the Monday numbers
- `jobs/`, `outbox/`, `golden/`, `proposals/` created by the CLI (confidential, not in git)
