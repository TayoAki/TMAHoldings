export const meta = {
  name: 'holdco-eval',
  description: 'Re-run the Claude agents on golden cases (real accepted work) and compare the material facts with what a person approved',
  whenToUse: 'After changing an agent file or a rule, and before graduating a job type. Pass {root: "<absolute workspace path>", business, cases: ["G-0001", ...]} from `python3 -m holdco golden list <business> --json`.',
  phases: [
    { title: 'Materialize', detail: 'turn each golden case into an eval job' },
    { title: 'Run', detail: 'holdco-process-job on the eval jobs' },
    { title: 'Compare', detail: 'compare each latest draft with the accepted output' },
  ],
}

const ROOT = String((args && args.root) || '.').replace(/\/+$/, '')
const BIZ = args && args.business
const CASES = ((args && args.cases) || []).map(c => (typeof c === 'string' ? c : c && c.id)).filter(Boolean)
if (!BIZ || !CASES.length) {
  log('Pass {root, business, cases}. List cases with `python3 -m holdco golden list <business> --json`.')
  return { error: 'nothing to evaluate' }
}
const cli = cmd => `python3 -m holdco --root ${ROOT} ${cmd}`

const MATERIALIZE_SCHEMA = {
  type: 'object',
  properties: {
    jobs: {
      type: 'array',
      items: { type: 'object', properties: { case: { type: 'string' }, job: { type: 'string' }, ok: { type: 'boolean' } }, required: ['case', 'job', 'ok'] },
    },
  },
  required: ['jobs'],
}
const COMPARE_SCHEMA = {
  type: 'object',
  properties: {
    results: {
      type: 'array',
      items: {
        type: 'object',
        properties: { case: { type: 'string' }, job: { type: 'string' }, passed: { type: 'boolean' }, differences: { type: 'array', items: { type: 'object' } }, output: { type: 'string' } },
        required: ['case', 'job', 'passed'],
      },
    },
  },
  required: ['results'],
}

async function clerk(prompt, schema, phaseName, label) {
  try {
    return await agent(prompt, { schema, phase: phaseName, label, agentType: 'holdco-clerk' })
  } catch (e) {
    return agent(prompt, { schema, phase: phaseName, label })
  }
}

phase('Materialize')
const made = await clerk(`You are the CLERK for TMA Holdings. Run each command below from the repository, in order:
${CASES.map((c, i) => `${i + 1}. ${cli(`golden materialize ${BIZ} ${c} --json`)}`).join('\n')}
Each prints JSON like {"job": "eval-G-0001", "state": "ready"}.
Return {"jobs": [{"case": <case id>, "job": <job id from the output, or "" on error>, "ok": <exit code was 0>}]}.`,
  MATERIALIZE_SCHEMA, 'Materialize', `materialize ${CASES.length} case(s)`)
const evalJobs = ((made && made.jobs) || []).filter(j => j.ok && j.job)
if (!evalJobs.length) return { error: 'no eval jobs were created', details: made }

phase('Run')
const run = await workflow('holdco-process-job', {
  root: ROOT,
  jobs: evalJobs.map(j => ({ business: BIZ, job: j.job, state: 'ready', drafts: 0 })),
})

phase('Compare')
const compared = await clerk(`You are the CLERK for TMA Holdings. Run each command below, in order:
${evalJobs.map((j, i) => `${i + 1}. ${cli(`golden compare ${BIZ} ${j.case} --job ${j.job} --json`)}`).join('\n')}
Each prints JSON with "passed" and "differences" (exit code 1 just means the case failed).
Return {"results": [{"case", "job", "passed", "differences", "output"}]} in order.`,
  COMPARE_SCHEMA, 'Compare', `compare ${evalJobs.length} case(s)`)

const results = (compared && compared.results) || []
const passed = results.filter(r => r.passed).length
log(`${passed}/${results.length} golden case(s) match what a person approved`)
return {
  business: BIZ,
  passed,
  failed: results.length - passed,
  results,
  runs: run && run.processed,
  note: 'Eval jobs never reach the approval queue or the Monday numbers. A failing case means the agents ' +
        'no longer produce what a person accepted: fix the agent file or rule before trusting it with clients.',
}
