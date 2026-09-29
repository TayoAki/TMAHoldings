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
2. You say what changes for now: **nothing clients can see**, until each kind of work has
   proven itself in the background (weeks, not days). Same people, same service, same prices,
   same software.
3. You introduce the GM as the person running the business, and say they have real upside.
4. You explain the agents honestly: trainees that do first drafts in the background while
   everyone keeps working as usual; staff check the drafts and their fixes become the firm's
   rules. Their expertise is what makes this work. Only promise job security you can keep.

## Day one, afternoon (you and the GM, two hours)
5. Create the business folder, then the GM and you each set an approval passphrase in your own
   terminals. The GM's key signs the client work they approve and release; yours is for when you
   approve or release something yourself and for checking what you released (`outbox verify`).
   As owner you also make the rule and rollout calls, which need no key:
   `python3 -m holdco new-business <slug> --name "<Name>" --industry <industry> --gm "<GM name>" --owner "<you>"`
   **(you)** `python3 -m holdco keys add <slug> --by "<GM name>"` and `... --by "<you>"`
6. Interview the GM and fill in, in this order:
   - `clients.md` for the top 20 clients by revenue *and* the 5 most sensitive: who they are
     loyal to, what they are sensitive about, their quirks, what would make them leave.
   - `people.md`: who knows what, and every "only Sam knows how to do that" (those become runbooks or rules).
   - `rules.md`: the firm's unwritten rules. Report dates, formats, sign-offs, "never email X about
     fees", "Y gets theirs on the 3rd because they asked in 2011".
7. Baselines: `clients.csv` (roster with start dates, status, fee), `financials.csv` (last 12
   months of revenue and costs), `pulse.csv` (first check-in on each key person).
8. Pick the first job type for shadow mode: high-volume, repetitive, low-risk work, so it reaches
   the 20 shadow jobs graduation needs in weeks (the monthly close across all clients, or
   document chasing). Five messy clients make a good wedge offer (runbook 10) but too few jobs to
   graduate on. `new-business` already lists the GM in `approvers`, you in `owners`, and puts the
   template's job type in shadow; add the first job type to `"rollout"` in `business.json` if it
   is a different one (new job types start in shadow anyway).

## Do not, on day one
- Change prices, roles, or client-facing software.
- Let any agent draft reach a client (shadow mode makes this impossible; keep it that way).
- Remove the seller's access before the agreement says so, or leave it after.

## Done when
The folder is filled in, MFA is on everything, the GM agreement is signed, baselines are
recorded, and one job type is running in shadow mode. Next: runbook 02.
