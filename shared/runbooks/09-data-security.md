# 09 · Data security and approved tools

Client data at these firms is regulated. Set this up **before** any client data touches an AI
tool, and review it quarterly. This page is a working checklist, not legal advice: have
counsel and your CPA confirm it for each business and state.

## Approved tools (fill in; G-008 points here)

| Tool | Used for | Data allowed | Contract / settings checked |
|---|---|---|---|
| Claude (Anthropic) via a business plan or the API | agents in this repo | client documents for the job | business terms: no training on your data; retention settings; US processing |
| _ledger software_ | books of record | all | |
| _document portal_ | client uploads | all | MFA on |
| _email_ | client messages | messages only, masked numbers | MFA on |
| _password manager_ | credentials | credentials | |

Anything not on this list does not get client data. Consumer chat apps and personal accounts
never do.

## The baseline (all businesses)
- [ ] **Written information security plan** (the IRS publishes a template: Pub 5708; see also Pub 4557).
- [ ] A named **Qualified Individual** responsible for it (you, until a business is big enough).
- [ ] **MFA** on every system that touches client data; encryption in transit and at rest.
- [ ] Access reviewed quarterly; the seller's access removed on the agreed date.
- [ ] **Vendor oversight:** a signed agreement with every AI and software vendor covering
      confidentiality, no training on your data, data location, and breach notice.
- [ ] Staff training at onboarding and yearly.
- [ ] **Incident plan:** who decides, who calls counsel and the insurer, and the notice deadlines.
- [ ] Cyber and E&O insurance that covers AI-assisted work.
- [ ] Real client data never goes in git (`.gitignore` keeps `businesses/*` out, except the
      template and fictional demos).

## Tax and accounting firms
- The **FTC Safeguards Rule** treats tax preparers as financial institutions: written program,
  risk assessment, MFA, encryption, vendor oversight, monitoring or annual penetration tests,
  an incident plan, and notice to the FTC within 30 days of discovering an exposure of
  unencrypted data on 500+ consumers. (Firms with fewer than 5,000 consumers are exempt from
  some parts. Bookkeeping for businesses only may fall outside the rule; treat any work for
  individuals as covered.)
- **IRC §7216** restricts using or disclosing tax-return information. Using a US service
  provider to help prepare returns is generally allowed; anything beyond preparing the return
  needs the client's written consent. **Watch-out for this repo:** keeping client tax data as
  golden test cases or using it to improve agents is arguably "another purpose". Get consent
  that covers quality control, or anonymize the cases, and ask counsel first.
- **IRS guidance on AI (OPR Alert 2026-19, June 2026):** treat AI output as drafts a
  practitioner reviews, vet third-party AI tools, set procedures and training, and don't
  upload taxpayer data to unsecured or public AI tools. That is this repo's approval rule.
- **CPA firms (AICPA Code):** tell clients before sharing confidential data with a third-party
  provider, and have a confidentiality agreement with the provider or the client's consent.
  Consider telling clients you use AI with human review.

## Insurance agencies
- State insurance data-security laws (NAIC model #668, adopted widely) apply instead of the FTC rule.
- AI stays on servicing work. Selling, soliciting and advice are for licensed producers.

## Property management
- Trust-account rules (deposit deadlines, no commingling, monthly reconciliation) are strict and
  state-specific. Agents can draft owner statements; they never move money.
- Some states now require notice and human review for automated decisions in housing, insurance
  and financial services (for example Colorado from Jan 1, 2027). Keep a person on every
  tenant-facing decision.

Sources and dates for each point: `docs/VIDEO-REVIEW.md`, section "What the video leaves out".
