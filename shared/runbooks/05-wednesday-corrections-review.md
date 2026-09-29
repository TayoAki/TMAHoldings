# 05 · Wednesday corrections review

**The prompt this hour runs on** (from the playbook this repo implements):

> Compare each agent draft with the version a person approved this week. Sort every change
> into factual error, client preference, missing information or style. For any correction
> that happened more than once, propose a rule. Add each approved rule as a test using the
> original input and the accepted output.

The first two sentences already happened: every approval, shadow comparison, answer and
send-back logged its corrections with a category. This hour is the last two sentences.

## Steps (one business at a time, about an hour)
1. Get the proposals.
   - Exact repeats (fast, deterministic): `python3 -m holdco corrections review <biz>`
   - Fuzzy patterns too: in Claude Code, "run the weekly review for <biz>". The
     `holdco-weekly-review` workflow runs the rules-curator agent, has a skeptic agent argue
     against each proposal, and records surviving ones with `holdco rules propose`.
2. For each proposal, read the evidence (`python3 -m holdco corrections list <biz>`) and ask:
   - Is it really a pattern (two or more separate jobs), not one odd month?
   - Is it one client's preference (`Scope: client:<id>`) or the whole firm's?
   - Does it conflict with another rule? Non-negotiables always win.
   - Is the wording something a new hire would follow correctly?
3. Decide, **(you)**:
   - `python3 -m holdco rules accept <biz> P-0007 --by "<you>"` (optionally `--text "better wording"`)
   - `python3 -m holdco rules reject <biz> P-0007 --by "<you>" --reason "one-off: client changed banks"`
   Accepting appends the rule to `rules.md` and turns each evidence job into a golden case.
4. Re-run the tests: `python3 -m holdco eval <biz>` (demo runner) or the `holdco-eval`
   workflow. All cases must pass. If an old case fails, the new rule conflicts with past
   accepted work: decide which one is right before moving on.
5. **"Rule not followed" items**: the rule exists and agents ignored it. Fix the agent file or
   make the rule's wording more specific, then re-run the tests. Don't add a duplicate rule.
6. **Factual errors**, even single ones: find which agent missed what (preparer? reviewer?),
   and fix its job file. If the error is machine-checkable, consider a new check type.

## What good looks like after a few months
- New corrections per job trend toward zero for graduated job types.
- Most remaining corrections are `missing_information` (things only the client knows).
- The rules file reads like the firm's operating manual, because it is one.
