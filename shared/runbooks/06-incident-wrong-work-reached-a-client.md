# 06 · Wrong work reached a client

In this system an agent cannot send anything, so "the agent sent something wrong" really
means one of two things: a person approved a wrong draft, or something left outside the
system. Both are handled the same way. Blameless, fast, and fixed at the root.

## First hour: contain
1. Stop the job type at that business, **(you)**:
   `python3 -m holdco rollout <biz> <job-type> shadow --by "<you>" --reason "incident <date>"`
   Nothing of that type can be approved or sent until you switch it back.
2. Find exactly what went out: `businesses/<biz>/outbox/<job>/manifest.json` shows who approved
   it, when, and the content hash; `jobs/<job>/job.json` has the full history.
3. Decide how serious it is:
   - **Wrong fact or number:** correct it with the client today.
   - **Advice, or a promise the firm can't keep:** involve the licensed professional before anything else goes out.
   - **Client data sent to the wrong person, or exposed:** this is a data incident. Follow the
     incident plan in runbook 09 now (counsel, insurer, and possibly an FTC notice within 30 days
     if 500+ consumers' unencrypted data is involved).

## Same day: correct with the client
4. The GM calls the client (not email). Own it, fix it, say what changes. Never blame "the AI":
   the firm approved it, so the firm owns it.
5. Send the correction through the normal approval flow once the job type is safe to use.

## Within a week: root cause and fix
6. Which layer missed it: preparer, reviewer, machine checks, or the approving person? If the
   person, why? A draft too long to read, a queue too big, a rule nobody told them about?
7. Fix every layer that could have caught it:
   - a rule (plus a machine check if it can be verified exactly),
   - a golden case built from the corrected output,
   - the agent file wording,
   - a tighter pass mark (`review_pass_score`) or a smaller daily queue for the approver.
8. Write a one-page note in `businesses/<biz>/incidents/<date>.md`: what happened, impact, root
   cause, what changed. No names in the "cause" section; systems, not people.

## Resume
9. `python3 -m holdco eval <biz>` passes, then two weeks in shadow and a clean graduation
   report (runbook 03) before switching back to assisted.
