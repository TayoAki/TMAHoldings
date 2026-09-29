# Agent job files

Every agent in the holdco gets a plain-English job description, like a new hire would.
Each one answers the same questions: **what is my job, what can I do, what can I never
do, and when do I stop and ask a person.** Most agent problems come from nobody telling
the agent where its job ends, so the "never" and "stop and ask" sections carry the most weight.

| Agent | Job | Can | Can never |
|---|---|---|---|
| [intake](intake.md) | Make sure a job has everything before work starts; chase what's missing | read inputs, draft a chase | send anything, start the work |
| [preparer](preparer.md) | Do the first draft of the actual work | read, write its own draft file | send, grade itself, guess big unknowns |
| [reviewer](reviewer.md) | Check every draft against the rules; pass it to a person or send it back | read, pass, block, ask | edit the draft, approve, send |
| [rules-curator](rules-curator.md) | Weekly: turn the corrections log into proposed rules and tests | read the log, propose | accept rules, edit rules or tests |

The flow for every client job:

```
work arrives → INTAKE (complete? if not, draft a chase) → PREPARER (first draft)
            → REVIEWER (pass, or block with findings → back to PREPARER, max 3 drafts)
            → a named PERSON approves (edits are logged as corrections) → a PERSON sends
```

**The rule that prevents most disasters:** the reviewer can block, but it can never send.
The preparer can't send either. A person approves everything before it reaches a client.
In this repo that rule is enforced in layers, so it never depends on an agent remembering it:

1. The `holdco` library refuses human-only actions (`approve`, `send`, `answer`, `shadow`,
   `rollout`, `rules accept`, ...) inside an agent session (Claude Code sets `CLAUDECODE=1`;
   other runners set `HOLDCO_AGENT=1`) or without an interactive terminal.
2. Approvals and releases are signed with the approver's passphrase, which no agent has: `send`
   refuses an unsigned approval, and `holdco outbox verify` flags released items that were changed
   and items no approver or owner released.
3. `.claude/hooks/human_only_guard.py` blocks those commands, and any write to outboxes,
   approvals, job state, inputs, logs or golden cases, before the tool call runs; holdco agents
   may write only their job's `work/` folder.
4. Inputs, drafts and approved output are hashed; changes made outside the CLI are refused.

For real client work, agents also run as a separate OS user that can write only `jobs/` and
`proposals/` (runbook 09), because anything running under your own account could, with enough
effort, rewrite files the first layers guard.

## Where these files are used

- **Claude Code agents** (`.claude/agents/holdco-*.md`) point at these files and add tool
  restrictions: the reviewer has no Write or Bash tool at all.
- **The workflow** (`.claude/workflows/holdco-process-job.js`) runs them in order.
- **Other runtimes** (Codex, Gemini, the API) can use the same files as system prompts;
  the output contracts at the bottom of each file are runtime-neutral JSON.

## Changing an agent file

Treat it like changing code: after any edit, run the golden cases
(`python3 -m holdco eval <business>` for the demo runner, or the `holdco-eval` workflow for
the Claude agents) and read the diff of what changed before trusting it with client work.
