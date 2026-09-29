# Review: "$5T opportunity: AI Roll Ups" (Greg Isenberg, Sep 28, 2026)

*Reviewed Sep 29, 2026 for TMA Holdings. Every factual claim in the episode was checked against
primary sources where they exist; where they don't, this says so. Planning research only: have a
lawyer, a CPA and an SBA lender confirm anything you rely on.*

## The short version

- **The thesis holds up, with the numbers softened.** Retiring owners, capable agents, and firms
  priced like their margins can't change: all three are real. But McKinsey says *up to* $5T across
  *viable sale candidates*, not "a million businesses will sell". Most exits today are closures.
- **The fund examples are real, but self-reported and partly out of date.** Thrive Holdings (about
  50 accounting practices, $1B more committed) and the 31% time saving in its tax pilot check out
  as company claims. Several General Catalyst figures trace back to one unsourced blog post.
- **The operating model is the valuable part, and it's right:** a shared layer of agents and rules,
  a GM with real upside, a person approving everything before it reaches a client, and a
  corrections log turned into rules every week. This repo implements all of it and proves the
  mechanics with a runnable demo (20/20 proofs), 75 tests, and a live run with real Claude agents.
- **The margin claim needs arithmetic.** At the reported 31% time saving, a 10%-margin firm gets to
  roughly 15–25%, depending on how much freed time you actually capture. 30–40% takes agents doing
  about half the labor hours *and* capturing most of them. Plan on the lower number.
- **The biggest gaps are legal and financial:** who is allowed to own an accounting, insurance or
  property-management firm; client-data law; and SBA loan rules that change on **Oct 1, 2026**
  (no earnouts, the seller can't stay as an employee, and the seller can't roll equity into a new
  holding company).
- **The start is the best advice in the episode:** sell one annoying job to firms in one industry
  first, then buy one when an owner is ready. That is a demand-first path, and your existing
  skills already cover it.

## What the episode argues, section by section

| Time | Section | Claim | Our read |
|---|---|---|---|
| 1:52 | Why now | Owners retiring + agents that work + firms priced at 5–10% margins = a new kind of business | Right on the first and third. The second ("I couldn't have said this eight months ago") is his judgment; the pilots below are the evidence so far, and they are self-reported. |
| 4:53 | Thrive and General Catalyst | Funds are buying accounting, property-management and support firms and running agents inside them | Real, but the numbers are self-reported and some are out of date (fact-check below). |
| 8:40 | The fund playbook | Build the agents first, buy a trusted firm, run agents in the background, move the back office over, repeat | Sound sequencing. Our version: shadow mode, then graduation per job type (runbooks 02–03). |
| 10:11 | The small-deal gap | Funds skip $2M firms; most sellers are small | Supported: nearly 80% of the projected exits are businesses worth under $2M. |
| 10:54 | One-person holdco | You on top, a GM with upside at each business, a shared layer underneath | The core model. The GM matters more than the agents (Greg says so too). |
| 14:28 | Folder structure | Thesis; shared (agents, global rules, test examples, runbooks); per-business clients, people, rules, corrections log | Implemented here almost exactly (see the map in `README.md`). |
| 16:54 | Agent pipeline | Intake → preparer → reviewer → person → client. The reviewer can block, never send | Implemented and enforced in code, three ways. |
| 18:38 | Reviewer file | Plain-English job description: job, can, can't, checks, when to stop and ask | `shared/agents/*.md`. |
| 19:43 | The week | Monday numbers, Tuesday GM calls, Wednesday corrections, Thursday–Friday deals | `holdco metrics`, runbooks 04–05, the deal screen. |
| 21:49 | First business | Sell a service to firms first; after 6–12 months an owner will be ready | Runbook 10, wired to your demand-first skills. |
| 22:24 | Counterarguments | Five objections, answered | Scored below. Greg takes "people hate change" most seriously; so do we. |

## Fact-check

| # | What the episode says | What the source says | Verdict |
|---|---|---|---|
| 1 | $5T, about 1M businesses selling by 2035 (McKinsey) | About 6M US small and mid-size businesses face ownership transitions by 2035; "more than one million firms are viable candidates for sale, representing up to $5 trillion in enterprise value." 52% of owners are within 10 years of retiring. In 2022, 92% of exits were closures, 5% sales and 3% transfers. [1][2] | **Partly right.** The numbers are real, but they measure viable candidates and a ceiling, not a forecast of sales. |
| 2 | Thrive Holdings bought close to 50 accounting firms in 24 months and committed another $1B | "A two year-long acquisition binge of nearly 50 local accounting practices" and "committing $1 billion". The platform (Crete Professionals Alliance, renamed Current in Jun 2026) itself counts "almost 30" firms, 2,000+ staff, $500M+ revenue. OpenAI took a stake in Dec 2025. [3][4][5] | **Verified**, counting partner-firm deals. |
| 3 | Larson Gross: since 1949, 5 offices, 200 people; AI on OpenAI Codex; 7,000 returns; 31% time saved; 180 hours to 15; interns now review | All confirmed as company statements. But the 7,000 returns and the 31% are Current's multi-firm pilot, in which Larson Gross was one of the first firms; OpenAI describes it as "about a third" less prep time with up to 97% accuracy. Nothing is independently audited. [3][6][7] | **Verified, self-reported**, attribution broader than stated. |
| 4 | General Catalyst set aside $1.5B; put $750M+ into at least 10 companies | $1.5B for its "Creation" strategy in Fund XII (Oct 2024) is confirmed. "At least ten" co-created companies is reported elsewhere. The $750M figure appears only in an unsourced blog post. [8][9] | **Half verified.** |
| 5 | Long Lake: 18 property-management acquisitions, $100M EBITDA in under 2 years, margins doubling | 18 acquisitions was true in Aug 2025; by May 2026 it was 30, including a $6.3B deal for Amex GBT. "$100M EBITDA in under 2 years" was said of "some" GC companies without naming Long Lake. GC's CEO says Long Lake doubled free cash flow in its HOA businesses "without reducing headcount." [9][10] | **Outdated / unattributed.** |
| 6 | Crescendo: AI handles about 90% of frontline tickets | Marketing says "up to 90%"; its homepage says "70% resolution from day one"; one named customer reports 67%. [11] | **A ceiling, not an average.** |
| 7 | GC deals pay 60–70% cash, founders roll about 30% | The 30% rollover is a GC partner's example. The 60–70% cash figure has no primary source. PE deals for CPA firms are often 50% cash, 20% on performance, and 30% rolled equity. [12][13] | **Half verified.** |
| 8 | Service firms run at 5–10% profit | GC's partner uses "5 to 10% EBITDA". Benchmarks vary by industry and by how owner pay is counted: property management averaged 6% (2017) and 11% (2021); top-performing insurance agencies 26%; accounting, tax and bookkeeping firms about 14% net in IRS-based data (secondary source). [12][14][15] | **Plausible after paying the owner a market salary**; varies by industry. |

What the checking changes: nothing about the direction, a lot about the confidence. Treat every
fund number as a signal from companies that are raising money, and none of them has been through a
recession yet (Greg says this himself).

## The math behind "5–10% to 30–40%"

Time saved is not money saved. Freed hours only become margin if you either **stop paying for
them** (attrition, not backfilling) or **sell them** (new clients served by the same team). Hours
that are freed but not captured become slack, extra review, or rework.

`python3 -m holdco model margin` runs a simple, transparent model: a firm at 10% margin, labor at
55% of revenue, other costs at 35%, 5% of revenue lost in the transition, and agents costing 3% of
revenue.

| Share of labor hours agents take over | Capture 25% | Capture 50% | Capture 75% | Capture 100% |
|---|---|---|---|---|
| 20% | 6.7% | 10.3% | 13.7% | 16.9% |
| **31% (the reported pilot)** | 9.2% | **14.8%** | 20.0% | **24.8%** |
| 40% | 11.5% | 18.9% | 25.5% | 31.4% |
| 50% | 14.5% | 24.1% | 32.1% | 38.9% |

What this says:
- At the reported 31% saving, you land between about **15% and 25%**, depending on capture. Even
  the best case (every freed hour captured through attrition, no churn, free agents) is about 27%.
- **30–40% needs agents doing about half the labor hours** and you capturing most of them.
  Possible, but it's the thesis case, not the plan.
- **Hourly billing breaks the model.** If the firm bills by the hour, doing the work faster cuts
  revenue. Convert to fixed fees before (or while) you move work to agents, which is why billing
  model is in the buy box.
- **Price on today.** The deal screen shows the scenarios, but the maximum price comes from today's
  earnings. The upside is yours to create; the seller doesn't get paid for it.

## What to take from it (and where it lives in this repo)

1. **The shared layer.** Build it once and every business plugs in: `shared/agents`, `shared/rules`,
   `shared/job-types`, `shared/runbooks`, `shared/golden`.
2. **The reviewer can block but never send; a person approves everything.** Enforced three ways:
   the CLI refuses human-only commands inside any agent session, a Claude Code hook blocks them
   before they run, and `send` checks the content hash of what the person approved. The demo and
   the tests prove each one.
3. **Plain-English agent files** whose "never" and "stop and ask" sections carry the most weight: `shared/agents/`.
4. **The corrections log is the moat.** Every edit becomes a categorized correction; fixes repeated
   across jobs become proposed rules; accepted rules become regression tests from the original input
   and the accepted output. `holdco corrections review`, `rules accept`, `eval`.
5. **Change nothing clients see for 30 days.** Shadow mode: agent drafts can't be approved or sent,
   and each difference from the person's own work is logged. `holdco shadow`, `graduation`, `rollout`.
6. **A GM who already works there, with real upside.** Runbook 11.
7. **Five Monday numbers**, including the two most people skip (retention and whether key people are
   staying), plus an alert when margin rises while clients leave. `holdco metrics`.
8. **Serve first, then buy.** Runbook 10.

## What the video leaves out (and what we added)

**Who can own what** (checked Sep 2026; state rules vary)
- *CPA firms:* licensed CPAs must hold a majority of any firm doing audit or attest work; passive
  investors are prohibited. Private equity uses an "alternative practice structure": a CPA-owned
  attest firm plus an investor-owned firm for tax, bookkeeping and advisory, linked by a services
  agreement. The AICPA proposed tighter independence rules for these structures in Dec 2025. A
  solo non-CPA buyer should buy the non-attest practice only. [16][17][18]
- *Bookkeeping and tax-only firms:* no CPA ownership rule, but every paid preparer needs a PTIN,
  some states license preparers (California, Oregon), and **an EFIN does not transfer**: the buyer
  files a new e-file application with proof of sale (45 days before to 30 days after the
  acquisition; approval can take 45 days). [19][20]
- *Insurance agencies:* an agency license with a designated licensed producer; carrier appointment
  contracts often allow termination on a change of control, so get consents before closing; AI and
  unlicensed staff stay on servicing, never selling or advice. [21][22]
- *Property management:* a broker license or designated broker; strict trust-account rules;
  management agreements may not be assignable without the owner's consent. [23][24]

**Client data and AI**
- The FTC Safeguards Rule treats tax preparers as financial institutions: a written security
  program, a qualified individual, MFA, encryption, vendor oversight, testing, an incident plan, and
  FTC notice within 30 days of an exposure of unencrypted data on 500+ consumers. [25][26]
- IRC §7216: using a US service provider to help prepare returns is generally allowed; any other use
  of return information needs the client's written consent. **Keeping client tax data as golden
  test cases is arguably "another use"**: get consent that covers quality control or anonymize the
  cases, and ask counsel. [27]
- The IRS issued AI guidance for tax practitioners in Jun 2026 (OPR Alert 2026-19): treat AI output
  as drafts a practitioner reviews, vet AI vendors, set procedures, and don't upload taxpayer data
  to unsecured tools. That is the human-approval rule, in regulator language. [28]
- The AICPA Code expects firms to tell clients before sharing confidential data with third-party
  providers and to have confidentiality agreements with them. [29]
- All of this is a checklist in runbook 09.

**Financing (SBA 7(a), rules for loans numbered on or after Oct 1, 2026)** [30][31][32]
- At least 10% of total project cost in buyer cash for a first acquisition. A seller note counts only
  if it is on full standby for the whole loan term, and then for at most half.
- **Seller earnouts are not allowed.** Retention protection has to be a buyer rebate that pays down
  the loan.
- In a first acquisition the seller can't stay as an owner or employee, only as a consultant (up to
  24 months in total). Seller rollover only works as a partial stock sale with a 2-year personal
  guarantee from the seller. **A new holding company owned by both buyer and seller is ineligible.**
- At least 1.25x debt-service coverage; an independent valuation above a $350k price; a
  quality-of-earnings report at $3M or more; up to 10-year terms; $5M maximum loan.
- **The SBA guarantees at most $3.75M per borrower including affiliates**: every business the
  holdco controls shares that cap. This is the constraint a serial acquirer hits first.
- Since Mar 1, 2026, every owner and guarantor must be a US citizen or national living in the US.
- The GC-style "60–70% cash plus 30% rollover" structure mostly does not work with SBA money.

**Prices for small firms** [33]–[37]

| Industry | Revenue multiple | SDE multiple | Source (date) |
|---|---|---|---|
| Accounting and tax practices | 1.1–1.3x (well-run); 1.11x average | 2.34x | Poe Group (Mar 2026); BizBuySell (2025 data) |
| Bookkeeping firms | 1.04–1.17x | 2.55–3.32x | Peak Business Valuation (May 2026), low confidence |
| Insurance agencies (small) | 1.53x | 2.68x | BizBuySell (2025 data) |
| Property management (small) | — | 2.72x | BizBuySell (2025 data) |
| All small businesses, Q2 2026 | 0.7x | 2.7x cash flow | BizBuySell Insight report |

Accounting practices traditionally sell with a 12-month client-retention adjustment; about half of
one broker's deals were 100% cash at closing. [38][39]

**Other things worth knowing**
- *Criticism is growing:* "the maths doesn't make sense … a lot of VCs getting hurt" (PitchBook, Jun
  2026); low-quality AI output ("workslop") and thinner staff to catch it (TechCrunch, Sep 2025). [40][41]
- *A cautionary tale:* Bench, a VC-backed bookkeeping company with 35,000+ customers, shut down
  abruptly in Dec 2024. Clients stay because they trust people, and they leave fast when that breaks. [42]
- *The big players are moving up-market* into large, debt-funded deals (Long Lake's $6.3B Amex GBT
  purchase), which widens the small-deal gap Greg points at. [10][43]

## The counterarguments, scored

| Objection | Greg's answer | Our read | How the system tests it |
|---|---|---|---|
| "Roll-ups always fail; it's PE with an AI sticker" | They fail from overpaying, buying too fast and losing the culture; buy slowly and price on today | **Agree.** This is the most useful answer in the episode. | Deal screen caps price on today's earnings; "8 stable Mondays" before the next deal |
| "Margins get competed away" | Eventually, but the window is years, and relationships plus your rules list are hard to copy | **Mostly agree.** The window is real in fragmented local markets; the rules list only becomes a moat after hundreds of jobs. | Corrections per job and rules count, tracked weekly |
| "Regulated work needs humans checking everything, so no savings" | Checking is faster than making; people shift from doing to checking | **Agree, with the math.** Savings are real but smaller than the headline (see the math above). | Minutes per job vs the shadow-mode manual baseline |
| "People hate change; staff and clients will leave" | The one he takes most seriously: change nothing visible for 30 days, keep the GM with upside | **This is the real risk.** One key person leaving can cost more than the agents save. | Retention and key-people metrics; pulse alerts; shadow mode |
| "It's a fancy word for layoffs" | Roles shift to reviewing; some jobs will change | **Be honest with staff early.** Capture freed time through growth and attrition first. | The capture split in the margin model; the people metric |
| (not in the episode) "The math doesn't work at fund scale" | — | **Probably true for big funds paying big multiples, and less so for small deals priced on today.** | Deal screen scenarios with a stress case |

## Audience signal from the comments

Commenters asked for a ready-made product and the full playbook, and several said they are already
doing this (UK contracting firms; a one-person holdco "building in public"). By your own evidence
hierarchy that is attention, the weakest signal: interest, not purchase intent. It does hint at a
later option (a productized version of this operating system), which belongs in the demand-first
Phase 4 once the holdco itself works, not now.

## What this means for TMA Holdings

1. **Pick one industry.** Recommended: bookkeeping (lowest licensing hurdle, most agent-ready work,
   recurring revenue, and the system here is built on it). Validate it locally with `niche-validator`.
2. **Sell the wedge service first** (runbook 10) and run it on this repo's pipeline. That builds the
   rules file, the relationships and the cash flow before you own anything.
3. **Line up a lawyer, a CPA and an SBA lender now**, especially because the SBA rules change on Oct 1, 2026.
4. **Buy one firm priced on today's earnings**, with a GM who stays and has upside, and run it in shadow
   mode for 30 days before any client sees agent work.
5. **Protect the Wednesday hour.** The rules list is the asset.

The step-by-step version, with exit criteria and proof for each step, is `docs/PLAYBOOK.md`. Your
action list is `TODO.md`.

## Sources

1. McKinsey Institute for Economic Mobility, "The Great Ownership Transfer: A new era of business stewardship," Feb 26, 2026. https://www.mckinsey.com/institute-for-economic-mobility/our-insights/the-great-ownership-transfer-a-new-era-of-business-stewardship
2. Fortune, Feb 26, 2026. https://fortune.com/2026/02/26/great-small-business-wealth-transfer-mckinsey-5-trillion-baby-boomer-businesses-sale/
3. Forbes (Anna Tong), "Thrive Holdings to bet $1 billion on AI-powered accounting roll-up," Jun 2, 2026. https://www.forbes.com/sites/annatong/2026/06/02/thrive-holdings-to-bet-1-billion-on-ai-powered-accounting-roll-up/
4. Current (formerly Crete Professionals Alliance), rebrand release, Jun 2, 2026. https://www.current.co/news/crete-professionals-alliance-rebrands-as-current
5. OpenAI, "Thrive Holdings," Dec 1, 2025. https://openai.com/index/thrive-holdings/ ; TechCrunch, Aug 12, 2026. https://techcrunch.com/2026/08/12/openai-backed-thrive-holdings-raises-2b-to-bring-ai-to-the-enterprise/
6. OpenAI, "Building self-improving tax agents with Codex," May 27, 2026. https://openai.com/index/building-self-improving-tax-agents-with-codex/
7. Larson Gross, About us. https://larsongross.com/about-us/
8. General Catalyst, "Announcing Fund XII," Oct 24, 2024. https://www.generalcatalyst.com/stories/fundxii
9. General Catalyst, "The Future of Services," Aug 28, 2025. https://www.generalcatalyst.com/stories/the-future-of-services
10. PitchBook via Yahoo Finance, May 6, 2026 (Long Lake / Amex GBT). https://finance.yahoo.com/sectors/technology/articles/general-catalysts-6-3b-amex-230800080.html
11. Crescendo. https://www.crescendo.ai/
12. Cognitive Revolution podcast with Marc Bhargava (General Catalyst), Aug 2, 2025. https://www.cognitiverevolution.ai/the-revolution-in-services-general-catalysts-ai-rollup-strategy-with-marc-bhargava/
13. Rosenberg Associates, Mar 4, 2026. https://rosenbergassoc.com/a-peek-behind-the-curtain-the-highs-and-lows-of-private-equity/
14. Big "I" and Reagan Consulting best-practices study, Aug 12, 2025. https://www.independentagent.com/news/big-i-and-reagan-consulting-release-2025-best-practices-study/
15. SecondNature (NARPM data), Dec 16, 2024. https://www.secondnature.com/blog/property-management-profitability
16. NASBA/AICPA, Uniform Accountancy Act, 9th ed., Jul 2025. https://nasba.org/wp-content/uploads/2025/07/Uniform-Accountancy-Act-9th-Edition-003.pdf
17. Hunton, "Forming an accounting firm alternative practice structure," Feb 27, 2024. https://www.hunton.com/insights/legal/forming-an-accounting-firm-alternative-practice-structure-key-considerations
18. Journal of Accountancy, Dec 19, 2025 and Aug 10, 2026. https://www.journalofaccountancy.com/news/2025/dec/aicpa-proposes-changes-to-independence-rules-related-to-private-equity/
19. IRS, EFIN FAQs (reviewed Oct 10, 2025). https://www.irs.gov/e-file-providers/faqs-about-electronic-filing-identification-numbers-efin
20. IRS Publication 3112 (Rev. 11-2025). https://www.irs.gov/pub/irs-pdf/p3112.pdf
21. NAIC Producer Licensing Model Act. https://content.naic.org/sites/default/files/model-law-218.pdf
22. Big "I", Guide to Agency-Company Appointment Contracts, Feb 2025. https://www.independentagent.com/wp-content/uploads/2025/02/agencyappointmentcontractguidance1-1.pdf
23. Texas Real Estate Commission, business entity broker. https://www.trec.texas.gov/become-licensed/business-entity-real-estate-broker
24. Arizona Revised Statutes §32-2173. https://www.azleg.gov/ars/32/02173.htm
25. 16 CFR 314.4 (FTC Safeguards Rule). https://www.law.cornell.edu/cfr/text/16/314.4
26. FTC, Safeguards Rule notification requirement, May 2024. https://www.ftc.gov/business-guidance/blog/2024/05/safeguards-rule-notification-requirement-now-effect
27. 26 CFR 301.7216-2 and -3. https://www.law.cornell.edu/cfr/text/26/301.7216-2
28. IRS Office of Professional Responsibility, Alert 2026-19, Jun 24, 2026. https://content.govdelivery.com/accounts/USIRS/bulletins/41d6e70
29. Journal of Accountancy, "Should I disclose my use of gen AI to clients?", Apr 1, 2025. https://www.journalofaccountancy.com/issues/2025/apr/should-i-disclose-my-use-of-gen-ai-to-clients/
30. SBA Information Notice 5000-880695 (SOP 50 10 8.1), Aug 14, 2026. https://legacy.sba.gov/document/information-notice-5000-880695-issuance-sop-50-10-81
31. SBA Policy Notice 5000-876441 (citizenship and residency), effective Mar 1, 2026. https://legacy.sba.gov/document/policy-notice-5000-876441-update-sop-50-10-8-citizenship-residency-requirements-recission-procedural-notice-5000-872050
32. Whiteford, "SBA issues SOP 50 10 8," May 6, 2025. https://www.whitefordlaw.com/news-events/client-alert-sba-issues-sop-50-10-8-key-changes-impacting-sba-7a-lending
33. Poe Group Advisors, accounting practice value (updated Mar 9, 2026). https://poegroupadvisors.com/blog/accounting-practice-value/
34. BizBuySell valuation benchmarks, accounting/CPA/tax practice (2025 data). https://www.bizbuysell.com/learning-center/valuation-benchmarks/accounting-cpa-tax-practice/
35. Peak Business Valuation, bookkeeping firm multiples (updated May 8, 2026). https://peakbusinessvaluation.com/valuation-multiples-for-a-bookkeeping-firm/
36. BizBuySell valuation benchmarks, insurance agency and property management (2025 data). https://www.bizbuysell.com/learning-center/valuation-benchmarks/insurance-agency/
37. BizBuySell Insight Report, Q2 2026. https://www.bizbuysell.com/insight-report/
38. Poe Group Advisors, practice sale price and terms (updated Jun 24, 2025). https://poegroupadvisors.com/blog/accounting-practice-sales-price-terms/
39. MICPA / Accounting Practice Sales, Nov 10, 2025. https://micpa.org/community/stay-informed/news/2025/11/10/ready-to-sell--how-accounting-practices-are-sold
40. PitchBook, Jun 22, 2026. https://pitchbook.com/news/articles/the-math-doesnt-make-sense-ai-rollup-hype-tests-the-limits-of-vc-economics
41. TechCrunch, Sep 28, 2025. https://techcrunch.com/2025/09/28/the-ai-services-transformation-may-be-harder-than-vcs-think/
42. Yahoo Finance / TechCrunch, Bench shutdown, Dec 2024. https://finance.yahoo.com/news/bench-shuts-down-leaving-thousands-215200329.html
43. CNBC, Jun 8, 2026. https://www.cnbc.com/2026/06/08/silicon-valleys-new-buyout-playbook-is-hitting-wall-street.html
