export const meta = {
  name: 'holdco-weekly-review',
  description: 'Wednesday corrections review: propose rules for repeated fixes, red-team each proposal, and record the survivors for a person to accept',
  whenToUse: 'Weekly, per business. Pass {root: "<absolute workspace path>", business, asOf?: "YYYY-MM-DD"}. Proposals are recorded with `holdco rules propose`; only a person accepts or rejects them.',
  phases: [
    { title: 'Curate', detail: 'rules-curator reads the corrections log and proposes rules' },
    { title: 'Challenge', detail: 'a skeptic tries to refute each proposal' },
    { title: 'Record', detail: 'clerk records the proposals that survive' },
  ],
}

const ROOT = String((args && args.root) || '.').replace(/\/+$/, '')
const BIZ = args && args.business
const AS_OF = args && args.asOf
if (!BIZ) {
  log('Pass {root, business}.')
  return { error: 'no business given' }
}
const cli = cmd => `python3 -m holdco --root ${ROOT} ${cmd}`

const PROPOSAL = {
  type: 'object',
  properties: {
    title: { type: 'string' }, applies_to: { type: 'string' }, scope: { type: 'string' },
    rule_text: { type: 'string' }, why: { type: 'string' },
    check: { type: ['object', 'null'] },
    evidence: { type: 'array', items: { type: 'string' } },
    golden_candidates: { type: 'array', items: { type: 'string' } },
  },
  required: ['title', 'applies_to', 'scope', 'rule_text', 'why', 'check', 'evidence', 'golden_candidates'],
}

const CURATOR_SCHEMA = {
  type: 'object',
  properties: {
    counts_by_category: { type: 'object' },
    deterministic_proposals: { type: 'array', items: { type: 'string' } },
    rules_not_followed: { type: 'array', items: { type: 'string' } },
    proposals: { type: 'array', items: PROPOSAL },
    agent_file_fixes: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          agent: { type: 'string' }, problem: { type: 'string' }, suggested_change: { type: 'string' },
          evidence: { type: 'array', items: { type: 'string' } },
        },
        required: ['agent', 'problem', 'suggested_change'],
      },
    },
    notes: { type: 'string' },
  },
  required: ['counts_by_category', 'deterministic_proposals', 'proposals', 'agent_file_fixes', 'notes'],
}

const SKEPTIC_SCHEMA = {
  type: 'object',
  properties: {
    keep: { type: 'boolean' },
    reasons: { type: 'array', items: { type: 'string' } },
    revised_rule_text: { type: 'string' },
    revised_scope: { type: 'string' },
    drop_check: { type: 'boolean' },
  },
  required: ['keep', 'reasons'],
}

const CLERK_SCHEMA = {
  type: 'object',
  properties: {
    results: {
      type: 'array',
      items: {
        type: 'object',
        properties: { title: { type: 'string' }, ok: { type: 'boolean' }, output: { type: 'string' } },
        required: ['title', 'ok', 'output'],
      },
    },
  },
  required: ['results'],
}

async function run(role, prompt, schema, phase, label) {
  try {
    return await agent(prompt, { schema, phase, label, agentType: role ? `holdco-${role}` : undefined })
  } catch (e) {
    log(`agent type holdco-${role} unavailable; using a default agent`)
    return agent(prompt, { schema, phase, label })
  }
}

phase('Curate')
const curated = await run('rules-curator', `You are the RULES CURATOR for TMA Holdings.
Workspace root: ${ROOT}. Business: ${BIZ}.
1. Read ${ROOT}/shared/agents/rules-curator.md and ${ROOT}/shared/rules/README.md and follow them exactly.
2. Run: ${cli(`corrections review ${BIZ} --json${AS_OF ? ` --as-of ${AS_OF}` : ''}`)}
   It records exact-repeat proposals itself (ids like P-0003): list them in "deterministic_proposals",
   and list any "rule_not_followed" rule ids in "rules_not_followed". Do not re-propose them.
3. Read ${ROOT}/businesses/${BIZ}/corrections-log.jsonl, the rules, and the job folders the corrections point to.
   Group corrections that mean the same thing even when worded differently.
4. Propose a rule only for a group seen in two or more separate jobs. Evidence must be real correction ids;
   golden_candidates must be approved jobs (job.json has "approval").
5. List every factual error from the review window under agent_file_fixes, even single ones.
Return the JSON from your job description (with the extra fields above).`, CURATOR_SCHEMA, 'Curate', `curator ${BIZ}`)
if (!curated) return { error: 'curator returned nothing' }
log(`${curated.deterministic_proposals.length} exact-repeat proposal(s) recorded; ${curated.proposals.length} more from the curator`)

const challenged = await pipeline(curated.proposals, (p, _item, i) => agent(`You are a SKEPTIC reviewing a proposed rule for
TMA Holdings business ${BIZ} (workspace root ${ROOT}). Try to refute it. Default to keep=false if the evidence is thin.
Proposed rule: ${JSON.stringify(p, null, 2)}
Check, reading ${ROOT}/businesses/${BIZ}/corrections-log.jsonl, ${ROOT}/businesses/${BIZ}/rules.md,
${ROOT}/shared/rules/ and ${ROOT}/shared/rules/README.md:
- Is it a real pattern: do the evidence ids exist, and do they come from two or more separate jobs?
- Is it overbroad? A single client's preference must be "client:<id>", not "all".
- Does it conflict with an existing rule or a non-negotiable global rule?
- Is the check (if any) exactly right for the supported check type, or would it misfire? If unsure, drop_check=true.
- Would a new hire follow the rule text correctly? If not, give revised_rule_text.
Return {keep, reasons, revised_rule_text?, revised_scope?, drop_check?}.`,
  { schema: SKEPTIC_SCHEMA, phase: 'Challenge', label: `skeptic ${i + 1}: ${p.title.slice(0, 40)}` })
  .then(v => ({ proposal: p, verdict: v })))

const survivors = challenged.filter(c => c && c.verdict && c.verdict.keep).map(({ proposal, verdict }) => ({
  ...proposal,
  rule_text: verdict.revised_rule_text || proposal.rule_text,
  scope: verdict.revised_scope || proposal.scope,
  check: verdict.drop_check ? null : proposal.check,
}))
const refuted = challenged.filter(c => c && c.verdict && !c.verdict.keep)
  .map(c => ({ title: c.proposal.title, reasons: c.verdict.reasons }))
const unreviewed = challenged.filter(c => !c || !c.verdict).length
if (unreviewed) log(`${unreviewed} proposal(s) had no skeptic verdict and were not recorded`)

let recorded = []
if (survivors.length) {
  phase('Record')
  const steps = survivors.map((p, i) => `${i + 1}. Write this JSON exactly to /tmp/holdco-proposal-${BIZ}-${i + 1}.json:
${JSON.stringify(p, null, 2)}
   Then run: ${cli(`rules propose ${BIZ} --file /tmp/holdco-proposal-${BIZ}-${i + 1}.json`)}`).join('\n')
  const clerk = await run('clerk', `You are the CLERK for TMA Holdings. Do exactly these steps and nothing else:
${steps}
Return {"results": [{"title": <proposal title>, "ok": <exit code was 0>, "output": <command output or error>}]} in order.`,
    CLERK_SCHEMA, 'Record', `record proposals ${BIZ}`)
  recorded = clerk ? clerk.results : []
}

return {
  business: BIZ,
  counts_by_category: curated.counts_by_category,
  exact_repeat_proposals: curated.deterministic_proposals,
  rules_not_followed: curated.rules_not_followed || [],
  curated_proposals_recorded: recorded,
  refuted_by_skeptic: refuted,
  agent_file_fixes: curated.agent_file_fixes,
  notes: curated.notes,
  next: `A person decides each proposal: python3 -m holdco rules proposals ${BIZ}, then ` +
        `rules accept ${BIZ} <P-id> --by "<name>" or rules reject ... (human-only). Then run the eval.`,
}
