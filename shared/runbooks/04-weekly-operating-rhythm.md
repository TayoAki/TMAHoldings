# 04 · The weekly rhythm

It is less hectic than people expect, because the GMs and the agents handle the day-to-day.

| Day | What | Time |
|---|---|---|
| Daily (GM) | Clear the approval queue: approve/send, answer agent questions | 20–60 min |
| Monday (you) | The numbers, every business | 1 hour |
| Tuesday (you) | One call with each GM | 30 min per GM |
| Wednesday (you + GM) | Corrections review: the most important hour of the week | 1 hour per business |
| Thursday–Friday (you) | The next business: owner coffees, learning industries, deals | the rest |

## Daily: the approval queue (GM)
```bash
python3 -m holdco queue                    # everything waiting on a person, all businesses
python3 -m holdco job show <biz> <job>     # read the draft, the review, the findings
python3 -m holdco approve <biz> <job> --by "<GM>" --minutes 6       # (you) edits prompt for a category
python3 -m holdco send <biz> <job> --by "<GM>"                      # (you) releases to the outbox
python3 -m holdco answer <biz> <job> --by "<GM>" --text "Owner's Draw"   # (you) unblocks an agent
```

## Monday: the numbers
`python3 -m holdco metrics` shows five numbers per business:
1. **Profit margin.** Trend, not level. Up while clients leave is an alert, not a win.
2. **Human minutes per job.** Should fall as rules accumulate. Shadow jobs show the manual baseline.
3. **Share of agent drafts needing fixes.** Rising two weeks running means something changed:
   a new client, a new staff member, a rule that went stale.
4. **Client retention.** Any loss gets a "why" before Tuesday's call.
5. **Key people happy and staying.** From `pulse.csv`. Anyone below 4/5 or not low-risk is on
   Tuesday's agenda.

## Tuesday: one call per GM (30 minutes)
Agenda, always the same: what's working; what's annoying you; which clients need attention;
how can I help. Then update `pulse.csv` together (date, person, role, key, happiness 1–5,
flight risk low/medium/high, one-line note).

## Wednesday: corrections review
Runbook 05. Protect this hour. After a few hundred jobs, the list of rules it produces is the
most valuable thing the holdco owns: anyone can use the same AI models, but nobody else has
the list of every way they go wrong in your kind of business.

## Thursday–Friday: the next business
Runbook 08 (sourcing and screening), runbook 10 (the wedge service, before the first deal).
Buy slowly: the next deal waits until every current business has had 8 stable Mondays.
