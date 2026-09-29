export const meta = {
  name: 'holdco-deal-screen',
  description: 'Screen an acquisition target: deal math, four diligence lenses in parallel, a red-team case for walking away, and a decision memo for a person',
  whenToUse: 'A deal file exists in thesis/deals/<target>.json (copy example-target.json). Pass {root: "<absolute workspace path>", deal: "thesis/deals/<target>.json", docs?: "<folder of CIM, P&Ls, client lists>"}. The memo is a recommendation; a person decides.',
  phases: [
    { title: 'Numbers', detail: 'holdco deal score: price on today\'s earnings, coverage, SBA pitfalls' },
    { title: 'Lenses', detail: 'clients, people, the work, rules and licensing' },
    { title: 'Red team', detail: 'the strongest case for walking away' },
    { title: 'Memo', detail: 'decision memo written next to the deal file' },
  ],
}

const ROOT = String((args && args.root) || '.').replace(/\/+$/, '')
const DEAL = args && args.deal
const DOCS = args && args.docs
if (!DEAL) {
  log('Pass {root, deal: "thesis/deals/<target>.json"}.')
  return { error: 'no deal file given' }
}
const dealPath = DEAL.startsWith('/') ? DEAL : `${ROOT}/${DEAL}`
const memoPath = dealPath.replace(/\.json$/, '') + '.memo.md'
const context = `Workspace root: ${ROOT}. Deal file: ${dealPath}.${DOCS ? ` Deal documents: ${DOCS}.` : ' No other deal documents were provided; say what you would need.'}
Read ${ROOT}/thesis/THESIS.md and ${ROOT}/thesis/buy-box.json for what TMA Holdings buys and why.`

const NUMBERS_SCHEMA = {
  type: 'object',
  properties: {
    verdict: { type: 'string' }, fit_score: { type: 'number' }, ebitda_today: { type: 'number' },
    asking_price: { type: 'number' }, max_price: { type: 'number' }, binding_cap: { type: 'string' },
    dscr_year1: { type: 'number' }, dscr_peak: { type: 'number' },
    failed_checks: { type: 'array', items: { type: 'string' } },
    warnings: { type: 'array', items: { type: 'string' } },
    scenarios: { type: 'array', items: { type: 'object' } },
  },
  required: ['verdict', 'ebitda_today', 'asking_price', 'max_price', 'dscr_peak', 'failed_checks', 'warnings'],
}
const LENS_SCHEMA = {
  type: 'object',
  properties: {
    lens: { type: 'string' },
    score: { type: 'number' },
    findings: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          severity: { type: 'string', enum: ['deal_breaker', 'major', 'minor'] },
          finding: { type: 'string' }, evidence: { type: 'string' }, diligence_question: { type: 'string' },
        },
        required: ['severity', 'finding', 'evidence', 'diligence_question'],
      },
    },
    summary: { type: 'string' },
  },
  required: ['lens', 'score', 'findings', 'summary'],
}
const RED_SCHEMA = {
  type: 'object',
  properties: {
    walk_away_case: { type: 'string' },
    strongest_reasons: { type: 'array', items: { type: 'string' } },
    what_would_change_my_mind: { type: 'array', items: { type: 'string' } },
    verdict_if_forced: { type: 'string', enum: ['PURSUE', 'NEGOTIATE', 'WALK AWAY'] },
  },
  required: ['walk_away_case', 'strongest_reasons', 'what_would_change_my_mind', 'verdict_if_forced'],
}
const MEMO_SCHEMA = {
  type: 'object',
  properties: {
    recommendation: { type: 'string', enum: ['PURSUE', 'NEGOTIATE', 'WALK AWAY'] },
    max_price: { type: 'number' },
    memo_path: { type: 'string' },
    top_risks: { type: 'array', items: { type: 'string' } },
    next_steps: { type: 'array', items: { type: 'string' } },
  },
  required: ['recommendation', 'max_price', 'memo_path', 'top_risks', 'next_steps'],
}

phase('Numbers')
const numbers = await agent(`${context}
Run: python3 -m holdco deal score ${dealPath} --json --root ${JSON.stringify(ROOT)}
Return the key numbers from its JSON: verdict, fit_score, ebitda_today, asking_price (financing.price), max_price,
binding_cap, dscr_year1, dscr_peak, failed_checks (criterion + detail for every check with ok=false),
warnings, and scenarios (name, margin, dscr, cash_after_debt). Do not add opinions.`,
  { schema: NUMBERS_SCHEMA, phase: 'Numbers', label: 'deal score' })
if (!numbers) return { error: 'could not run the deal score' }

const LENSES = [
  { key: 'clients', prompt: 'CLIENTS AND REVENUE QUALITY: concentration, retention history, recurring share, billing model (hourly billing means faster work shrinks revenue until pricing changes), pricing power, who clients are loyal to, what could make them leave after a change of ownership.' },
  { key: 'people', prompt: `PEOPLE AND THE GM: is there a GM candidate who already works there and knows every client; key-person risk; staff tenure and likely reaction; what the GM deal should be. Use ${ROOT}/shared/runbooks/11-gm-selection-and-incentives.md.` },
  { key: 'work', prompt: 'THE WORK AND AGENT-READINESS: which repeatable job types exist, hours per job type, how structured the data is, which systems hold it, what the first shadow-mode job type should be, and a realistic share of hours agents could take over in year one. Be conservative: one reported pilot saved 31% of tax-prep time.' },
  { key: 'rules', prompt: `RULES, LICENSING, DATA AND FINANCING: licensing on change of ownership (CPA attest work needs CPA-majority ownership; EFINs do not transfer; insurance and real-estate licenses), client data obligations (FTC Safeguards Rule, IRC 7216 for tax data), contract assignability, and SBA 7(a) terms. Use ${ROOT}/shared/runbooks/08-deal-sourcing-and-screening.md and 09-data-security.md. Flag anything needing a lawyer or CPA.` },
]

const lenses = (await parallel(LENSES.map(l => () => agent(`${context}
You are one of four diligence analysts for TMA Holdings. Your lens: ${l.prompt}
The deal math already done (do not redo it): ${JSON.stringify(numbers)}
Score the deal 0-10 through your lens only. Every finding needs evidence from the deal file or documents, or
must say plainly that the evidence is missing. Each finding ends with the diligence question that would settle it.`,
  { schema: LENS_SCHEMA, phase: 'Lenses', label: `lens: ${l.key}` })))).filter(Boolean)
if (lenses.length < LENSES.length) log(`${LENSES.length - lenses.length} lens(es) returned nothing`)

phase('Red team')
const red = await agent(`${context}
You are the red team for TMA Holdings. Make the strongest honest case for WALKING AWAY from this deal,
using the numbers and the four lens reports below. Roll-ups usually fail by overpaying, buying faster than they
can integrate, or losing the people; check each. Then say what evidence would change your mind.
Numbers: ${JSON.stringify(numbers)}
Lens reports: ${JSON.stringify(lenses)}`,
  { schema: RED_SCHEMA, phase: 'Red team', label: 'red team' })

phase('Memo')
const memo = await agent(`${context}
Write a decision memo for the owner of TMA Holdings and save it with the Write tool to ${memoPath}.
Inputs: numbers ${JSON.stringify(numbers)}; lens reports ${JSON.stringify(lenses)}; red team ${JSON.stringify(red)}.
Structure (plain English, short sentences, no filler):
# <target name> — decision memo
## Recommendation (PURSUE / NEGOTIATE / WALK AWAY, the most to pay and why: price on today's earnings, never the AI upside)
## The numbers (asking vs max price, multiples, coverage, sources and uses, what the scenarios need to be true)
## What has to be true (3-5 testable beliefs, each with how diligence will test it)
## Top risks and mitigations (from the lenses, deal-breakers first)
## The case for walking away (the red team, fairly stated)
## Diligence questions (grouped by lens)
## LOI terms to propose (structure consistent with SBA rules: equity, seller note standby, no earnout, retention rebate, transition, GM agreement, exclusivity)
## Next steps (owner, date)
End with: "Recommendation only. The decision, and advice from a lawyer, CPA and lender, belong to people."
Return {recommendation, max_price, memo_path, top_risks, next_steps}.`,
  { schema: MEMO_SCHEMA, phase: 'Memo', label: 'decision memo' })

return {
  deal: dealPath,
  numbers,
  lens_scores: lenses.map(l => ({ lens: l.lens, score: l.score, deal_breakers: l.findings.filter(f => f.severity === 'deal_breaker').length })),
  red_team_verdict: red && red.verdict_if_forced,
  memo,
}
