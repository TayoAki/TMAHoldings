# 08 · Deal sourcing and screening

**Principle:** price the business on what it makes today. The AI upside is yours to create,
not the seller's to charge for. Most roll-ups that fail overpay, buy faster than they can
integrate, or lose the culture, and AI fixes none of those.

## Sourcing (Thursdays and Fridays)
- **Your wedge-service clients first** (runbook 10). You already know how their firm works.
- **Direct outreach to owners** aged 60+ who have run the firm 20+ years. Marketplace listings
  (BizBuySell and similar) are mostly picked over unless the source is curated.
- **Referrals:** the CPAs, bankers, attorneys, and industry-association people who hear about
  succession first. Buy them coffee; tell them exactly what you buy (the buy box).
- **Lists:** state association directories; Google Maps by category and metro. The
  `lead-source-planner` skill builds the outreach plan; your pitch is to the owner's legacy,
  staff and clients, not to price.

## First conversation (listen)
What does the owner want: legacy, staff kept on, clients looked after, timing, money? Who runs
the place day to day (your likely GM)? Don't talk price in the first meeting.

## Screening
1. NDA, then 3 years of P&Ls and tax returns, a client list with revenue per client, a staff
   list with tenure, and how they bill (fixed fee or hourly).
2. Write the deal file (copy `thesis/deals/example-target.json`) and run the screen:
   `python3 -m holdco deal score thesis/deals/<target>.json`
   It checks the buy box (`thesis/buy-box.json`), works out sources and uses, debt service
   and coverage **on today's earnings**, the most you should pay, SBA pitfalls, and what the AI
   thesis would add on top.
3. For a full memo, in Claude Code: "screen the deal in thesis/deals/<target>.json". The
   `holdco-deal-screen` workflow runs four lenses in parallel (money, clients, people, rules and
   licensing), a red-team agent that argues for walking away, and writes a decision memo.
4. Decide with the `clear-thinking-os` skill if it's close: write the decision, your confidence,
   and what would change your mind.

## LOI terms that protect you (US, SBA 7(a) financed)
As of SBA SOP 50 10 8.1 (loans numbered on or after Oct 1, 2026). Confirm every point with your lender.
- **Equity:** at least 10% of total project cost in cash for a first acquisition. A seller note
  counts toward it only if it is on full standby for the whole loan term, and then for at most half.
- **No earnouts** on SBA deals. Put retention protection in as a **buyer rebate** (for example a
  12-month client-retention clawback) that pays down loan principal.
- **Seller transition:** when you buy control, the seller exits fully: they can't stay as an owner
  or employee, only as a consultant (up to 24 months total under 8.1). So **seller rollover equity
  is not available** in a control acquisition with SBA money, and a new holding company owned by
  both of you is ineligible. If the seller must keep a stake, use a seller note on full standby
  instead, or non-SBA financing, and have your lender confirm the structure.
- **Coverage:** lenders want debt-service coverage of at least 1.25x on today's earnings, and
  an independent valuation above a $350k price (a quality-of-earnings report at $3M+).
- **Guaranty cap:** SBA guarantees at most $3.75M per borrower including affiliates, so all
  your businesses share it. Plan deal #2 before closing deal #1.
- **Ownership:** since Mar 1, 2026 every owner and guarantor must be a US citizen or national
  living in the US.
- **GM agreement** signed as a closing condition; 60–90 days exclusivity.

## Diligence checklist
- [ ] Revenue quality: 3 years by client; retention history; top-client share; billing model.
- [ ] Earnings quality: owner add-backs are real; the cost of replacing the owner's work is counted.
- [ ] People: interview the GM candidate and key staff; who are clients loyal to?
- [ ] Licensing: CPA attest work needs CPA-majority ownership (buy only the non-attest practice,
      or pair with a CPA-owned attest firm); EFIN doesn't transfer; insurance and real-estate licenses.
- [ ] Contracts: can client agreements, leases and software licenses be assigned?
- [ ] Data: where client data lives, who has access, past breaches, WISP (runbook 09).
- [ ] Agent-readiness: which job types, how many hours, how clean the data is.
- [ ] Claims: E&O claims, complaints, regulator letters.

## Walk away when
Any of these is true (they are the `hard_fail` rules in `thesis/buy-box.json`, so `deal score`
says WALK AWAY):
- the industry isn't in the thesis;
- licensing would make you a passive owner of regulated work;
- coverage is under 1.0x on today's earnings;
- one client is over 30% of revenue;
- there is no GM candidate;
- the owner leaves at closing;
- the owner wants to be paid for the AI upside.

Everything else in the buy box (price, years, clients, recurring revenue, billing model, how
long the owner stays) is a reason to negotiate or dig deeper, not to walk.
