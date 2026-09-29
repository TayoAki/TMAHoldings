# 01 · Day one after taking over a business

**Goal:** everyone knows what changes (almost nothing, for now), the firm's unwritten rules
are written down, and the business is plugged into the holdco without a client noticing.
**Who:** you (holdco owner) and the GM, with the seller in the room for the morning.

## The week before closing
- [ ] GM agreement signed as a closing condition (runbook 11).
- [ ] Access list: every system, bank, portal, domain and email account; who has which login.
- [ ] Insurance bound: E&O that covers AI-assisted work, and cyber.
- [ ] Written information security plan ready (runbook 09); MFA plan for every system.
- [ ] Licensing tasks started. Tax practice: the IRS EFIN does **not** transfer, so file a new
      e-file application with proof of sale (window: 45 days before to 30 days after acquisition;
      approval can take 45 days). Insurance agency: designated responsible licensed producer and
      carrier consents. Property management: designated broker and trust-account signers.
- [ ] Client-file transfer notices sent the way counsel says (for CPA/tax firms, AICPA ET
      1.400.205; tax data may also need IRC §7216 consent for anything beyond preparing returns).

## Day one, morning (all staff, seller present)
1. The seller introduces you and says why they chose you. Keep it short and human.
2. You say what changes in the next 30 days: **nothing clients can see.** Same people, same
   service, same prices, same software.
3. You introduce the GM as the person running the business, and say they have real upside.
4. You explain the agents honestly: trainees that do first drafts in the background while
   everyone keeps working as usual; staff check the drafts and their fixes become the firm's
   rules. Their expertise is what makes this work. Only promise job security you can keep.

## Day one, afternoon (you and the GM, two hours)
5. Create the business folder:
   `python3 -m holdco new-business <slug> --name "<Name>" --industry <industry> --gm "<GM name>"`
6. Interview the GM and fill in, in this order:
   - `clients.md` for the top 20 clients by revenue *and* the 5 most sensitive: who they are
     loyal to, what they are sensitive about, their quirks, what would make them leave.
   - `people.md`: who knows what, and every "only Sam knows how to do that" (those become runbooks or rules).
   - `rules.md`: the firm's unwritten rules. Report dates, formats, sign-offs, "never email X about
     fees", "Y gets theirs on the 3rd because they asked in 2011".
7. Baselines: `clients.csv` (roster with start dates, status, fee), `financials.csv` (last 12
   months of revenue and costs), `pulse.csv` (first check-in on each key person).
8. Pick the first job type for shadow mode: the most repetitive, lowest-risk work (document
   chasing, or the monthly close for the 5 messiest clients). In `business.json` set
   `"rollout": {"<job-type>": "shadow"}`, and list the GM in `approvers`.

## Do not, on day one
- Change prices, roles, or client-facing software.
- Let any agent draft reach a client (shadow mode makes this impossible; keep it that way).
- Remove the seller's access before the agreement says so, or leave it after.

## Done when
The folder is filled in, MFA is on everything, the GM agreement is signed, baselines are
recorded, and one job type is running in shadow mode. Next: runbook 02.
