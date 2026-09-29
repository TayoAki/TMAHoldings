# TMA Holdings — thesis (DRAFT, for you to decide)

The thesis is what keeps you from buying something just because you got excited about it.
Everything below marked **DECIDE** is a recommendation, not a decision. Change it, then
update `buy-box.json` (which `python3 -m holdco deal score` reads) to match.

## What we believe

1. A large wave of small service businesses will change hands as owners retire. McKinsey
   (Feb 2026) counts about 6 million US small and mid-size businesses facing an ownership
   transition by 2035, of which more than 1 million are viable sale candidates worth up to
   $5 trillion. Nearly 80% of those exits are businesses worth under $2 million, too small for
   the funds.
2. Much of the work inside them is typing, chasing and first drafts, which agents can now do
   well enough that a person only checks the result. One reported pilot cut tax-prep time by 31%.
3. These firms are priced as if their margins can't change. If agents take over a real share of
   the hours, and we capture the freed time, margins can move from roughly 5–10% toward 15–25%,
   and toward 30–40% only if about half the hours move (see `docs/VIDEO-REVIEW.md`, "The math").
4. A solo owner can win the small deals the funds skip: many owners would rather hand their
   life's work to a person, and we can be the integration ourselves.
5. The durable edge is not the model (anyone can use it). It is the relationships we keep and
   the rules file we build: every way the agents go wrong in our kind of business, turned into
   rules and tests.

## Industries

| Industry | Licensing hurdle for us | Small-firm pricing (sourced) | Recurring | Agent-ready work | Watch-outs |
|---|---|---|---|---|---|
| **Bookkeeping** | Low, if no attest work and no "CPA" in the name | 1.04–1.17x revenue, 2.55–3.32x SDE (low-confidence source) | High: monthly fees | High: categorizing, reconciling, chasing documents | Fragmented and price-competitive; data rules still apply to work for individuals |
| **Tax prep (non-CPA)** | Medium: PTINs; a new EFIN (it doesn't transfer); some states license preparers | 1.11x revenue, 2.34x SDE (accounting and tax, 2025) | Yearly and seasonal | High: document intake, organizer data entry | IRC §7216 consent for any use beyond preparing the return; seasonal cash flow |
| CPA firm with audit work | High: CPAs must own the majority; needs an alternative practice structure | 1.1–1.3x revenue | High | Medium-high | Not solo-friendly unless you partner with CPAs |
| Insurance agency | Medium: agency license with a designated licensed producer; carrier consents | 1.53x revenue, 2.68x SDE (small agencies) | High: renewals | Medium: servicing, renewals, certificates | AI can't sell or advise; carrier contracts can end on a change of control |
| Property management | Medium-high: broker license; trust-account rules | 2.72x SDE (2025) | High: management fees | Medium: owner statements, work orders | Trust money; management agreements may not transfer |

Sources and dates: `docs/VIDEO-REVIEW.md`, "What the video leaves out".

**DECIDE — recommended starting point:** bookkeeping, for both the wedge service and the first
acquisition. It has the lowest licensing hurdle for a non-CPA owner, the most agent-ready work,
and monthly recurring revenue, and the whole operating system in this repo is already built and
tested on it. Tax prep is the natural second business (same clients, seasonal load), once a
bookkeeping firm is stable. Confirm with the `niche-validator` skill (Gate 0) in your region.

## What a good business looks like

- 10+ years old, $500k–$3M revenue, $150k+ seller's discretionary earnings.
- 60%+ recurring revenue, 100+ clients, no client over 15% of revenue.
- A senior person clients already trust who wants to run it (the future GM).
- An owner ready to step back within 12 months, who cares who takes over.
- Fixed-fee billing, or clients who would accept it (hourly billing turns time savings into lost revenue).
- Messy, paper-heavy processes that are *documentable*. Messy is opportunity; undocumentable is risk.
- **DECIDE — geography:** within a day's drive, so you can be in the room for day one and the GM calls.

## What we don't buy (anti-thesis)

- Businesses priced on the AI upside, or on "adjusted" earnings that don't survive a quality check.
- Audit/attest practices, unless a CPA partner owns that side.
- One client over 30% of revenue; no GM candidate; an owner who leaves at closing.
- Turnarounds. We buy healthy firms and make them better.
- Faster than one new business per 8 stable Mondays across the portfolio.

## The buy box (numbers in `buy-box.json`)

| Criterion | Draft value | Why |
|---|---|---|
| Industries | bookkeeping, tax-prep | the recommendation above |
| Revenue | $500k–$3M | big enough for a GM and a back office; small enough the funds skip it |
| SDE | at least $150k | covers debt service after paying someone to do the owner's job |
| Price / SDE | at most 3.0x | bookkeeping sells for about 2.5–3.3x SDE, accounting and tax about 2.3x |
| Price / revenue | 1.1x bookkeeping, 1.2x tax | small-practice norms of 1.0–1.3x |
| Debt coverage on today's earnings | at least 1.25x | the SBA minimum; we test it on today's numbers, not the plan |
| Recurring revenue | at least 60% | predictability through the transition |
| Top client | at most 15% | one departure can't sink the loan |
| GM candidate | required | the person clients are loyal to has to stay |
| Owner transition | at least 6 months | relationships transfer slowly |
| Agent-ready work | at least 30% of hours | below that, the thesis doesn't pay for the integration |

## The GM deal

A real raise on day one; a 5–15% profits interest (or phantom equity) vesting over 4 years;
an annual bonus on all five Monday numbers, not margin alone; written decision rights; client
messages signed by the GM. Details and warning signs: `shared/runbooks/11-gm-selection-and-incentives.md`.

## Capital plan (DECIDE)

For a first SBA-financed deal (rules from Oct 1, 2026; confirm with a lender):
- Cash: at least 10% of total project cost (price plus closing costs plus working capital). For the
  fictional example target at its maximum justified price ($1.08M), that is about $116k, plus a
  reserve of about 6 months of loan payments (about $75k at 10% over 10 years).
- Every owner of 20% or more personally guarantees the loan; every owner must be a US citizen or
  national living in the US.
- The SBA guarantees at most $3.75M per borrower including affiliates, and every business you
  control counts against it. Plan the second deal's financing before closing the first.
- No seller earnouts on SBA deals. Protect against client loss with a retention clawback paid as a
  buyer rebate against the loan.

Run the numbers any time: `python3 -m holdco deal score thesis/deals/example-target.json`.
