# Runbooks

Step-by-step instructions for things that happen more than once. When something happens a
second time and there is no runbook, write one.

| # | Runbook | Use it when |
|---|---|---|
| 01 | [Day one after taking over](01-day-one-takeover.md) | The day after closing |
| 02 | [Shadow mode](02-shadow-mode.md) | From day one at every new business, until a job type graduates |
| 03 | [Graduating a job type](03-graduating-a-job-type.md) | Moving a job type from shadow to assisted, or back |
| 04 | [The weekly rhythm](04-weekly-operating-rhythm.md) | Every week, forever |
| 05 | [Wednesday corrections review](05-wednesday-corrections-review.md) | Every Wednesday, every business |
| 06 | [An agent's work reached a client wrong](06-incident-wrong-work-reached-a-client.md) | Something wrong went out |
| 07 | [Onboarding the next business](07-onboarding-the-next-business.md) | Business #2, #3, ... |
| 08 | [Deal sourcing and screening](08-deal-sourcing-and-screening.md) | Thursdays and Fridays; any time a deal appears |
| 09 | [Data security and approved tools](09-data-security.md) | Before any client data touches an AI tool |
| 10 | [Landing the first business](10-landing-the-first-business.md) | Before you own anything |
| 11 | [Choosing and paying a GM](11-gm-selection-and-incentives.md) | Every acquisition |

Commands in these runbooks are for the `holdco` CLI (`python3 -m holdco --help`). Commands
marked **(you)** are human-only: they refuse to run inside an agent session, so a person
types them in their own terminal, as someone listed in the business's `approvers` or `owners`.
`approve`, `send` and `outbox verify` also ask for that person's passphrase, set once per
business with `python3 -m holdco keys add <biz> --by "<name>"`.
