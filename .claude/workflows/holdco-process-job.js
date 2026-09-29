export const meta = {
  name: 'holdco-process-job',
  description: 'Run holdco client jobs through intake, preparer and reviewer agents, record every step, and stop at the human approval queue',
  whenToUse: 'A TMA Holdings business has jobs in state received, ready or blocked. Pass {root: "<absolute workspace path>", jobs: [{business, job, state, drafts}]} from `python3 -m holdco job list --json`. It never approves or sends anything: a person does that with the holdco CLI.',
  phases: [
    { title: 'Intake', detail: 'are the documents complete? draft a chase if not' },
    { title: 'Prepare', detail: 'preparer writes work/draft.vN.json' },
    { title: 'Review', detail: 'reviewer passes, blocks with findings, or asks a person' },
    { title: 'Record', detail: 'clerk records each step with holdco record-run; machine checks can veto a pass' },
  ],
}

// ---------------------------------------------------------------- inputs

const ROOT = String((args && args.root) || '.').replace(/\/+$/, '')
const JOBS = ((args && args.jobs) || []).filter(j => j && j.business && j.job)
const MAX_DRAFTS = (args && args.maxDrafts) || 3

if (!ROOT.startsWith('/')) log(`root "${ROOT}" is relative; pass an absolute path so agents can write files reliably`)
if (!JOBS.length) {
  log('No jobs given. Run `python3 -m holdco job list --state received --json` and pass {root, jobs}.')
  return { processed: [] }
}

const cli = cmd => `python3 -m holdco --root ${ROOT} ${cmd}`
const jobDir = j => `${ROOT}/businesses/${j.business}/jobs/${j.job}`
const bizDir = j => `${ROOT}/businesses/${j.business}`

// --------------------------------------------------------------- schemas

const INTAKE_SCHEMA = {
  type: 'object',
  properties: {
    status: { type: 'string', enum: ['complete', 'missing_documents', 'needs_human'] },
    documents_found: { type: 'array', items: { type: 'string' } },
    missing: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          document: { type: 'string' }, label: { type: 'string' }, reason: { type: 'string' },
          transaction_id: { type: 'string' },
        },
        required: ['document', 'label', 'reason'],
      },
    },
    chase_message: {
      type: 'object',
      properties: { subject: { type: 'string' }, body_markdown: { type: 'string' } },
      required: ['subject', 'body_markdown'],
    },
    question: { type: 'string' },
    rules_applied: { type: 'array', items: { type: 'string' } },
  },
  required: ['status', 'documents_found', 'missing', 'rules_applied'],
}

const PREP_SCHEMA = {
  type: 'object',
  properties: {
    status: { type: 'string', enum: ['drafted', 'needs_human'] },
    draft_file: { type: 'string' },
    summary: { type: 'string' },
    rules_applied: { type: 'array', items: { type: 'string' } },
    question: { type: 'string' },
    key: { type: 'string' },
    context: { type: 'object' },
  },
  required: ['status'],
}

const REVIEW_SCHEMA = {
  type: 'object',
  properties: {
    verdict: { type: 'string', enum: ['PASS', 'BLOCK', 'NEEDS_HUMAN'] },
    score: { type: 'number' },
    findings: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          severity: { type: 'string', enum: ['blocker', 'major', 'minor'] },
          rule: { type: 'string' }, location: { type: 'string' }, issue: { type: 'string' }, fix: { type: 'string' },
        },
        required: ['severity', 'rule', 'location', 'issue', 'fix'],
      },
    },
    summary: { type: 'string' },
    question: { type: 'string' },
  },
  required: ['verdict', 'score', 'findings', 'summary'],
}

const CLERK_SCHEMA = {
  type: 'object',
  properties: {
    ok: { type: 'boolean' },
    state: { type: 'string' },
    last_review_verdict: { type: 'string' },
    findings: { type: 'array', items: { type: 'object' } },
    open_question: { type: 'string' },
    output: { type: 'string' },
  },
  required: ['ok', 'output'],
}

// --------------------------------------------------------------- prompts

const readRules = j => `the rules that apply: ${ROOT}/shared/rules/global-rules.md, the industry file ` +
  `${ROOT}/shared/rules/industries/<industry>.md (industry is in ${bizDir(j)}/business.json), and ${bizDir(j)}/rules.md ` +
  `(rules with "Scope: client:<id>" apply only to that client)`

const intakePrompt = j => `You are the INTAKE agent for TMA Holdings.
Workspace root: ${ROOT}. Business: ${j.business}. Job: ${j.job}. Job folder: ${jobDir(j)}.
1. Read ${ROOT}/shared/agents/intake.md and follow it exactly.
2. Read ${jobDir(j)}/job.json (job type, client, period), then ${ROOT}/shared/job-types/<job type>.md.
3. Read ${readRules(j)}.
4. Read the client notes: ${bizDir(j)}/clients.md and ${bizDir(j)}/clients.csv.
5. Check the files in ${jobDir(j)}/input/ against the checklist and threshold rules.
Do not write any files. Return the JSON your job description specifies.`

const chaseReviewPrompt = (j, intake) => `You are the REVIEWER agent for TMA Holdings, reviewing a document-chase
message drafted by the intake agent. It is not recorded yet; it is quoted below.
Workspace root: ${ROOT}. Business: ${j.business}. Parent job: ${j.job}. Job folder: ${jobDir(j)}.
1. Read ${ROOT}/shared/agents/reviewer.md and ${ROOT}/shared/job-types/document-chase.md.
2. Read ${readRules(j)}. Rules apply to this chase if "Applies to" is all or document-chase.
3. Read the client notes (${bizDir(j)}/clients.md, clients.csv) and the files in ${jobDir(j)}/input/,
   so you can confirm each item really is missing and is described correctly.
Missing items (from intake): ${JSON.stringify(intake.missing)}
Chase message: ${JSON.stringify(intake.chase_message)}
Return the review JSON from your job description.`

const preparePrompt = (j, draftFile, feedback) => `You are the PREPARER agent for TMA Holdings.
Workspace root: ${ROOT}. Business: ${j.business}. Job: ${j.job}. Job folder: ${jobDir(j)}.
1. Read ${ROOT}/shared/agents/preparer.md and follow it exactly.
2. Read ${jobDir(j)}/job.json (type, client, period, "answers" people gave, and past "reviews"), the job-type spec
   ${ROOT}/shared/job-types/<job type>.md, ${readRules(j)}, the client notes (${bizDir(j)}/clients.md and clients.csv),
   and any accepted work for this client in ${bizDir(j)}/golden/*/expected.json.
3. Do the work from the files in ${jobDir(j)}/input/. Copy ids, dates, descriptions and amounts exactly.
4. ${feedback
    ? `Your previous draft was blocked. Fix every one of these findings and change nothing else:\n${JSON.stringify(feedback, null, 2)}`
    : 'If job.json shows an earlier review with verdict BLOCK or SENT_BACK, fix every finding in the latest one.'}
5. Write the deliverable JSON to exactly ${jobDir(j)}/${draftFile}. It is the only file you may write.
Return {"status": "drafted", "draft_file": "${draftFile}", "summary": "...", "rules_applied": [...]}
or, if you must stop and ask a person, {"status": "needs_human", "question": "...", "key": "<e.g. transaction id>", "context": {...}}.`

const reviewPrompt = (j, draftFile) => `You are the REVIEWER agent for TMA Holdings.
Workspace root: ${ROOT}. Business: ${j.business}. Job: ${j.job}. Job folder: ${jobDir(j)}.
1. Read ${ROOT}/shared/agents/reviewer.md and follow it exactly.
2. The draft to review is ${jobDir(j)}/${draftFile}. Also read the files in ${jobDir(j)}/input/,
   ${jobDir(j)}/job.json (answers people gave), the job-type spec ${ROOT}/shared/job-types/<job type>.md,
   ${readRules(j)}, and the client notes (${bizDir(j)}/clients.md, clients.csv).
3. Recompute every total from the input files yourself. Check client-scoped rules first.
You cannot edit the draft. Return the review JSON from your job description.`

const clerkPrompt = (j, payload, n) => `You are the CLERK for TMA Holdings. Do exactly this and nothing else.
1. Write this JSON exactly (valid JSON, same content) to the file ${jobDir(j)}/work/run-${n}.json:
${JSON.stringify(payload, null, 2)}
2. Run this command and capture its output and exit code:
${cli(`record-run ${j.business} ${j.job} --file ${jobDir(j)}/work/run-${n}.json --json`)}
3. Return JSON: {"ok": <exit code was 0>, "state": <"state" from the command's JSON output>,
   "last_review_verdict": <last_review.verdict or "">, "findings": <last_review.findings or []>,
   "open_question": <open_question or "">, "output": <the full command output, or the error text>}.`

// ----------------------------------------------------------------- agents

async function run(role, prompt, schema, phase, label) {
  try {
    return await agent(prompt, { schema, phase, label, agentType: `holdco-${role}` })
  } catch (e) {
    log(`agent type holdco-${role} unavailable (${String((e && e.message) || e).slice(0, 80)}); ` +
        `falling back to a default agent that follows shared/agents/${role}.md`)
    return agent(prompt, { schema, phase, label })
  }
}

// ------------------------------------------------------------------ flow

async function processJob(j) {
  const result = { business: j.business, job: j.job, steps: [], state: j.state, error: null }
  let n = 0
  const record = async payload => {
    n += 1
    const out = await run('clerk', clerkPrompt(j, payload, n), CLERK_SCHEMA, 'Record', `record ${j.job} #${n}`)
    if (!out || !out.ok) throw new Error(`record-run failed: ${out ? String(out.output).slice(0, 400) : 'clerk returned nothing'}`)
    result.state = out.state || result.state
    return out
  }
  try {
    let state = j.state
    let pendingIntake = null
    if (state === 'received') {
      const intake = await run('intake', intakePrompt(j), INTAKE_SCHEMA, 'Intake', `intake ${j.job}`)
      if (!intake) throw new Error('intake agent returned nothing')
      if (intake.status === 'missing_documents') {
        const chaseReview = await run('reviewer', chaseReviewPrompt(j, intake), REVIEW_SCHEMA, 'Review', `review chase ${j.job}`)
        await record({ intake, chase_review: chaseReview || null, rounds: [] })
        result.steps.push(`intake: ${intake.missing.length} item(s) missing; chase drafted, reviewer ${chaseReview ? chaseReview.verdict : 'did not run'}`)
        return result
      }
      if (intake.status === 'needs_human') {
        await record({ intake, rounds: [] })
        result.steps.push(`intake asked a person: ${intake.question}`)
        return result
      }
      pendingIntake = intake
      result.steps.push('intake: all documents present')
      state = 'ready'
    }
    if (state !== 'ready' && state !== 'blocked') {
      result.error = `job is ${state}; nothing for agents to do`
      return result
    }
    let feedback = null
    for (let round = 1; round <= MAX_DRAFTS; round++) {
      const version = (j.drafts || 0) + round
      const draftFile = `work/draft.v${version}.json`
      const prep = await run('preparer', preparePrompt(j, draftFile, feedback), PREP_SCHEMA, 'Prepare', `prepare ${j.job} v${version}`)
      if (!prep) throw new Error(`preparer returned nothing for v${version}`)
      if (prep.status === 'needs_human') {
        await record({ intake: pendingIntake, rounds: [{ version, escalation: { question: prep.question || 'Preparer needs a person.', key: prep.key || null, context: prep.context || {} } }] })
        result.steps.push(`preparer asked a person: ${prep.question}`)
        break
      }
      const review = await run('reviewer', reviewPrompt(j, draftFile), REVIEW_SCHEMA, 'Review', `review ${j.job} v${version}`)
      if (!review) throw new Error(`reviewer returned nothing for v${version}`)
      const rec = await record({ intake: pendingIntake, rounds: [{ version, draft_file: draftFile, review }] })
      pendingIntake = null
      const vetoed = review.verdict === 'PASS' && rec.state === 'blocked'
      result.steps.push(`v${version}: reviewer ${review.verdict} (score ${review.score})` +
        (vetoed ? ' but machine checks blocked it' : '') + ` -> ${rec.state}`)
      if (rec.state !== 'blocked') break
      feedback = (rec.findings && rec.findings.length) ? rec.findings : review.findings
    }
  } catch (e) {
    result.error = String((e && e.message) || e)
  }
  log(`${j.business}/${j.job}: ${result.state}${result.error ? ` (error: ${result.error.slice(0, 120)})` : ''}`)
  return result
}

const processed = (await parallel(JOBS.map(j => () => processJob(j)))).filter(Boolean)
return {
  processed,
  next: 'Nothing was approved or sent. A person reviews the queue with `python3 -m holdco queue` and ' +
        '`python3 -m holdco job show <business> <job>`, then approves and sends from their own terminal.',
}
