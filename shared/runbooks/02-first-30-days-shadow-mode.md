# 02 · First 30 days: shadow mode

**Goal:** agents do real work in the background while people keep doing it the old way.
Every difference is logged. Nothing a client sees changes. By day 30 you know, with
numbers, whether the agents are ready for one job type.
**Who:** the GM runs it daily; you run the Wednesday review.

## How a shadow job flows
1. Work arrives. Create the job (an agent can do this):
   `python3 -m holdco job new <biz> --type <job-type> --client <id> --inputs <folder> --period 2026-10`
2. Run the agents: in Claude Code, "process the new jobs for <biz>" (the `holdco-process-job`
   workflow). They draft, review, and park the draft; they cannot approve or send it
   (`holdco approve` refuses any job type in shadow mode).
3. Staff do the job exactly as before and send it the old way.
4. The GM records what they actually did, **(you)**:
   `python3 -m holdco shadow <biz> <job> --by "<GM>" --minutes 42 --human-csv booked.csv`
   (or `--final their-version.json`, or `--set PATH=VALUE`). Each difference gets a category:
   factual error, client preference, missing information, or style.
5. The minutes become the **manual baseline** in the Monday numbers.

## Week by week
- **Week 1:** 5–10 jobs. Expect lots of differences; most will be client preferences that
  were never written down. That is the point: each one is a rule waiting to be written.
- **Weeks 2–3:** Wednesday reviews turn repeated differences into rules (runbook 05).
  Differences should fall week over week. If factual errors don't fall, fix the agent files.
- **Week 4:** run the graduation report and decide with the GM (runbook 03):
  `python3 -m holdco graduation <biz> <job-type>`

## Rules for the 30 days
- No agent draft reaches a client. No price, staffing, or client-software changes.
- Log every difference, even small ones. An unlogged fix is a rule you'll pay for again.
- Staff are the reviewers, not the reviewed. Say so, and mean it.
- If a key person looks shaky in the Tuesday pulse, slow down. People leaving is the risk
  that matters most here, more than any agent mistake.

## Done when
20 or more shadow jobs for the job type, rules captured for the repeated differences, and a
graduation decision made with the GM (graduate, or another 2 weeks of shadow).
