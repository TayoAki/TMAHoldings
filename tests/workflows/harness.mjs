// Runs a .claude/workflows/*.js script outside Claude Code, with scripted agents.
//
//   node tests/workflows/harness.mjs <workflow.js> '<args json>' <mock agent command...>
//
// agent() calls go to the mock command (with the role appended and the prompt on stdin),
// which must print the agent's JSON result. Prints {meta, out, calls, phasesUsed} as JSON.

import { readFileSync } from 'node:fs'
import { spawnSync } from 'node:child_process'
import path from 'node:path'

const [, , file, argsJson, ...mockCmd] = process.argv
const calls = []
const phasesUsed = new Set()   // phases of the top-level workflow only; a nested workflow() has its own
let depth = 0

function load(p) {
  const src = readFileSync(p, 'utf8')
  const m = src.match(/^export const meta = (\{[\s\S]*?\n\})\n/m)
  if (!m) throw new Error(`${p}: must start with export const meta = {...}`)
  for (const banned of ['Date.now(', 'Math.random(', 'new Date()']) {
    if (src.includes(banned)) throw new Error(`${p}: ${banned} is not allowed in workflow scripts`)
  }
  const meta = Function(`"use strict"; return (${m[1]})`)()
  return { meta, body: src.slice(m.index + m[0].length) }
}

const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor

async function agent(prompt, opts = {}) {
  const role = opts.agentType ? opts.agentType.replace(/^holdco-/, '') : 'default'
  if (opts.phase && depth === 0) phasesUsed.add(opts.phase)
  calls.push({ role, label: opts.label || '', phase: opts.phase || '' })
  const r = spawnSync(mockCmd[0], [...mockCmd.slice(1), role], { input: prompt, encoding: 'utf8', maxBuffer: 1 << 24 })
  if (r.status !== 0) throw new Error(`mock agent "${role}" failed:\n${r.stderr}`)
  return JSON.parse(r.stdout)
}

const parallel = thunks => Promise.all(thunks.map(t => t().catch(e => { console.error(String(e)); return null })))
const pipeline = (items, ...stages) => Promise.all(items.map(async (item, i) => {
  let value = item
  for (const stage of stages) {
    try { value = await stage(value, item, i) } catch (e) { console.error(String(e)); return null }
  }
  return value
}))
const log = m => console.error(`[log] ${m}`)
const phase = title => { if (depth === 0) phasesUsed.add(title) }
const budget = { total: null, spent: () => 0, remaining: () => Infinity }

async function runWorkflow(p, args) {
  const { body } = load(p)
  const fn = new AsyncFunction('args', 'agent', 'parallel', 'pipeline', 'log', 'phase', 'workflow', 'budget', body)
  return fn(args, agent, parallel, pipeline, log, phase, workflow, budget)
}

async function workflow(nameOrRef, args) {
  const p = typeof nameOrRef === 'string' ? path.join(path.dirname(file), `${nameOrRef}.js`) : nameOrRef.scriptPath
  if (depth > 0) throw new Error('workflow() nests one level only')
  depth += 1
  try {
    return await runWorkflow(p, args)
  } finally {
    depth -= 1
  }
}

const { meta } = load(file)
const out = await runWorkflow(file, JSON.parse(argsJson))
console.log(JSON.stringify({ meta, out, calls, phasesUsed: [...phasesUsed] }))
