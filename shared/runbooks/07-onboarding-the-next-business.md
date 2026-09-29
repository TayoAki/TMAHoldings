# 07 · Onboarding the next business

The point of the shared layer: the second business is easier than the first, because half
of what it needs already exists. The third is easier again.

## Before you sign the LOI
- [ ] Every current business has had 8 stable Mondays: margin steady or rising *with* retention
      steady, key people OK, no open incidents. Buy slowly.
- [ ] You have the time: shadow mode at a new business takes roughly one day a week of yours
      until its first job type graduates.
- [ ] Financing plan checked against the SBA's $3.75M guaranty cap per borrower *including
      affiliates*: every business the holdco controls shares that cap (runbook 08).

## Same industry (reuse almost everything)
1. Day one (runbook 01): new folder with `python3 -m holdco new-business ...`.
2. Industry rules, job types and agent files already exist. Only business and client rules are new.
3. Shadow mode (runbook 02) still applies, but graduation usually comes faster: many of the
   differences are already rules.
4. Consider promoting anonymized golden cases from business #1 to `shared/golden/` so both
   businesses test against the same accepted work.

## New industry (reuse the machinery, write new knowledge)
1. Before closing: write `shared/rules/industries/<industry>.md` (licensing, non-negotiables,
   thresholds) and the job-type specs for the first job type (see `shared/job-types/README.md`).
2. Licensing and data rules change by industry: insurance agencies need a designated licensed
   producer, carrier consents, and AI kept away from selling and advice; property managers need a
   designated broker and trust-account discipline (runbook 09 has the data side).
3. Plan for a longer shadow period: the agents have no industry rules yet, so expect more
   differences and consider a higher bar in `business.json` → `"graduation"` (for example 30
   shadow jobs) rather than fewer.
4. Run the golden cases for *all* businesses after changing any global rule.

## What stays the same everywhere
The approval rule, the corrections log, the Wednesday review, the Monday numbers, and a GM
with real upside at every business.
