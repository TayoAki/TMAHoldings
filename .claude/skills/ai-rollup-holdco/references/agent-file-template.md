# Agent job file template

Every agent gets a plain-English job description, like a new hire. Copy this, fill it in,
and save it as `shared/agents/<agent>.md`. Then add a thin Claude Code wrapper in
`.claude/agents/holdco-<agent>.md` that points at it and restricts tools (read-only unless
the agent must write a draft).

```markdown
# <Agent name> agent — job description

## Your job
One or two sentences. What outcome, for whom, and where the job ends.

## What you receive
- The exact files and folders, by path.
- The rules that apply (global, industry, business, client-scoped).
- The spec for the output format.

## You can
- Each allowed action. Be specific about the one place it may write, if any.

## You can never
- Send, approve or release anything to a client (G-001).
- Do the next agent's job (separation of duties).
- Invent a fact, number, date or name (G-002).
- The two or three mistakes this job is most tempted to make, stated as "never".

## Check / How to work
Numbered steps in the order a careful person would do them, including the core check
that proves the work is right.

## Stop and ask a person when
- Rules conflict, inputs look wrong, stakes are above a threshold, or the client seems upset.
- One question a person can answer in one line, with the key it is about.

## What you return
The exact JSON shape, with an example.
```

## Checklist before using a new or changed agent file

- [ ] The "never" list names the specific mistakes seen in the corrections log.
- [ ] Every "stop and ask" trigger is observable (a threshold, a mismatch, a missing file).
- [ ] The output contract matches the job-type spec and the workflow schema.
- [ ] The golden cases pass (`python3 -m holdco eval <biz>`, or the holdco-eval workflow).
- [ ] 20+ jobs in shadow mode before a client sees its work (for a new job type).
