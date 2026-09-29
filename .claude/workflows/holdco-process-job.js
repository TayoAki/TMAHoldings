export const meta = {
  name: 'holdco-process-job',
  description: 'Run holdco client jobs through intake, preparer and reviewer agents, record every step, and stop at the human approval queue',
  whenToUse: 'A TMA Holdings business has jobs in state received, ready, drafted or blocked. Pass {root: "<absolute workspace path>", jobs: <the output of `python3 -m holdco job list --json --root <root>`, as is>}. It never approves or sends anything: a person does that with the holdco CLI.',
  phases: [
    { title: 'Intake', detail: 'are the documents complete? draft a chase if not' },
    { title: 'Prepare', detail: 'preparer writes work/draft.vN.json' },
    { title: 'Review', detail: 'reviewer passes, blocks with findings, or asks a person' },
    { title: 'Record', detail: 'clerk records each step with holdco record-run; machine checks can veto a pass' },
  ],
}

// ---------------------------------------------------------------- inputs

const ROOT = String((args && args.root) || '.').replace(/\/+$/, '')
// Accepts `job list --json` rows as they are ({business, job, id, state, drafts, ...}).
const JOBS = ((args && args.jobs) || []).filter(Boolean).map(j => ({ ...j, job: j.job || j.id }))
  .filter(j => j.business && j.job)
// The engine hands a job to a person after business.json "max_drafts" blocked drafts; this is only a safety net.
const MAX_ROUNDS = (args && args.maxRounds) || 10
const AGENT_STATES = ['received', 'ready', 'drafted', 'blocked']

if (!ROOT.startsWith('/')) log(`root "${ROOT}" is relative; pass an absolute path so agents can write files reliably`)
if (!JOBS.length) {
  log('No jobs given. Run `python3 -m holdco job list --json --root <root>` and pass {root, jobs: <its output>}.')
  return { processed: [], error: 'no jobs given' }
}

// --root goes last so the command matches the permission rules in .claude/settings.json.
const cli = cmd => `python3 -m holdco ${cmd} --root ${JSON.stringify(ROOT)}`
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
    question_key: { type: 'string' },
    rules_applied: { type: 'array', items: { type: 'string' } },
  },
  required: ['status', 'documents_found', 'missing', 'rules_applied'],
}

// What record_intake will refuse, checked before anything is recorded.
function intakeProblem(r) {
  if (!r) return 'the intake agent returned nothing'
  if (r.status === 'missing_documents') {
    const m = r.chase_message || {}
    if (!(r.missing || []).length || !m.subject || !m.body_markdown) {
      return 'status "missing_documents" needs a non-empty "missing" list and a chase_message with subject and body_markdown'
    }
  }
  if (r.status === 'needs_human' && !String(r.question || '').trim()) return 'status "needs_human" needs a "question"'
  return null
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
    question_key: { type: 'string' },
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

const intakePrompt = (j, problem) => `You are the INTAKE agent for TMA Holdings.
Workspace root: ${ROOT}. Business: ${j.business}. Job: ${j.job}. Job folder: ${jobDir(j)}.
1. Read ${ROOT}/shared/agents/intake.md and follow it exactly.
2. Read ${jobDir(j)}/job.json (job type, client, period), then ${ROOT}/shared/job-types/<job type>.md.
3. Read ${readRules(j)}.
4. Read the client notes: ${bizDir(j)}/clients.md and ${bizDir(j)}/clients.csv.
5. Check the files in ${jobDir(j)}/input/ against the checklist and threshold rules.
Do not write any files. Return the JSON your job description specifies.${problem
  ? `\nYour previous answer could not be recorded: ${problem}. Return corrected JSON.` : ''}`

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
2. The draft to review is ${jobDir(j)}/${draftFile}. Also read the files in ${jobDir(j)}/input/
   (for a document-chase job, the input/ folder of the parent job named in job.json),
   ${jobDir(j)}/job.json (answers people gave, earlier reviews), the job-type spec ${ROOT}/shared/job-types/<job type>.md,
   ${readRules(j)}, and the client notes (${bizDir(j)}/clients.md, clients.csv).
3. Recompute every total from the input files yourself. Check client-scoped rules first.
You cannot edit the draft. If a person must decide something, return verdict NEEDS_HUMAN with a "question"
(and "question_key", e.g. the transaction id). Return the review JSON from your job description.`

// Named after the job's event count when the run started, so a later run never overwrites an earlier record.
const runFile = (j, n) => `${jobDir(j)}/work/run-e${j.events || 0}-${n}.json`

const clerkPrompt = (j, payload, n) => `You are the CLERK for TMA Holdings. Do exactly this and nothing else.
1. Write this JSON exactly (valid JSON, same content) to the file ${runFile(j, n)}:
${JSON.stringify(payload, null, 2)}
2. Run this command and capture its output and exit code:
${cli(`record-run ${j.business} ${j.job} --file ${runFile(j, n)} --json`)}
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
    let feedback = null
    let drafts = j.drafts || 0
    if (!AGENT_STATES.includes(state)) {
      result.error = `job is ${state}; nothing for agents to do`
      return result
    }
    if (state === 'received') {
      let intake = await run('intake', intakePrompt(j), INTAKE_SCHEMA, 'Intake', `intake ${j.job}`)
      let problem = intakeProblem(intake)
      if (problem) {
        log(`${j.job}: intake answer rejected (${problem}); asking once more`)
        intake = await run('intake', intakePrompt(j, problem), INTAKE_SCHEMA, 'Intake', `intake ${j.job} (retry)`)
        problem = intakeProblem(intake)
        if (problem) throw new Error(`intake: ${problem}`)
      }
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
    if (state === 'drafted') {
      // A recorded draft is waiting for review (for example after a person answered the reviewer's question).
      const draftFile = `drafts/v${drafts}.json`
      const review = await run('reviewer', reviewPrompt(j, draftFile), REVIEW_SCHEMA, 'Review', `review ${j.job} v${drafts}`)
      if (!review) throw new Error(`reviewer returned nothing for v${drafts}`)
      const rec = await record({ rounds: [{ version: drafts, review }] })
      result.steps.push(`v${drafts}: reviewer ${review.verdict} (score ${review.score}) -> ${rec.state}`)
      if (rec.state !== 'blocked') return result
      feedback = (rec.findings && rec.findings.length) ? rec.findings : review.findings
      state = 'blocked'
    }
    for (let round = 1; round <= MAX_ROUNDS; round++) {
      const version = drafts + 1
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
      drafts = version
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
