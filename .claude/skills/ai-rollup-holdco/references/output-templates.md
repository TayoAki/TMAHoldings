# Output templates

## Deal decision memo (`thesis/deals/<target>.memo.md`)

```markdown
# <Target> — decision memo  (<date>)

## Recommendation
PURSUE / NEGOTIATE / WALK AWAY. Most to pay: $X (binding limit: coverage | SDE multiple |
revenue multiple). One paragraph on why, priced on today's earnings.

## The numbers
Asking vs max price; price/SDE, price/adj. EBITDA, price/revenue; sources and uses; debt
service and coverage (year 1 and peak); what the AI scenarios need to be true.

## What has to be true
3–5 testable beliefs, each with the diligence step that tests it.

## Top risks and mitigations
Deal-breakers first. Clients, people, the work, rules and licensing, financing.

## The case for walking away
The red team's strongest argument, stated fairly.

## Diligence questions
Grouped: clients · people · work · rules/licensing/data · financing.

## LOI terms to propose
Price and structure (SBA: 10% equity; seller note standby; no earnout; retention clawback as a
buyer rebate; consulting transition), GM agreement as a closing condition, exclusivity.

## Next steps
Owner and date for each.

Recommendation only. The decision, and advice from a lawyer, CPA and lender, belong to people.
```

## Weekly owner summary (Monday, after `holdco metrics`)

```markdown
# Week of <date>

## Alerts first
- <business>: <alert> → <what you will do, by when>

## Five numbers per business
| Business | Margin | Min/job | Drafts fixed | Retention (90d) | Key people |
|---|---|---|---|---|---|

## Decisions this week
- Rules accepted / rejected (Wednesday), job types graduated or rolled back, deals advanced.

## Next week
- Tuesday GM calls: topics per GM.
- Thursday/Friday: owner meetings and deal work.
```

## Phase-gate decision record (append to `TODO.md` or `docs/decisions/<date>-<gate>.md`)

```markdown
## <date> · Gate <n>: <name>
- Decision: GO / KILL / PIVOT (<which variable>)
- Evidence: <facts with sources>
- Assumptions still open: <list>
- Confidence: <low/medium/high> — would change if: <signal>
- Next physical action: <what, who, when>
- Review date: <date>
```
