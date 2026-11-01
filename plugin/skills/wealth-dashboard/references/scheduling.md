# Monthly check-in

## Setting it up

1. Find a scheduling tool among your tools. Names vary ("scheduled tasks", "create trigger", "routines"); some only
   load after a tool search. Use one that starts a fresh session on a schedule and that the person can see and manage.
   Don't use anything that only lives inside the current session.
2. Agree the day and time. Default: monthly, a few days after payday (or the 3rd), 09:00 in their time zone; avoid
   exactly the top of the hour if the tool suggests spreading start times.
3. Create the task with the prompt below, filled in. It must stand alone: the scheduled run remembers nothing of this
   conversation.
4. `W settings wealth.json --set "schedule=monthly, 3rd, 08:52 Europe/Paris" --set checkin_day=3`, then save the
   state as usual (datasets `checkin` and `settings` change, so publish them).
5. Tell them in one or two sentences when it runs, what it does on its own, and that it messages them with a short
   list. If the tool says runs will ask for approval, mention where they can switch that to automatic.

No scheduling tool: say so and offer a recurring calendar reminder (if a calendar connector is available) saying
"Update my wealth dashboard", or simply typing that once a month in a new chat.

## Prompt template

Fill in everything in angle brackets.

```
Monthly wealth dashboard update for <first names>.

Use the wealth-dashboard skill in UPDATE mode. If the skill is not available, tell me the monthly update could
not run because the skill is missing, and stop.

Dashboard: <artifact url>   (no artifact: "the files wealth.json and wealth-dashboard.html in <folder>",
or "ask me to upload wealth.json")
Currency: <EUR>. Language for messages: <fr>. Time zone: <Europe/Paris>.

Steps:
1. Load the state from the dashboard's pipeline/state document (references/publishing.md), then run
   wealth.py validate and plan.
2. Do every automatic item without asking me: connector balances and positions, latest prices and exchange
   rates for every position (plus EUR and USD), on-chain balances. Formulas update themselves.
3. Save a provisional snapshot dated today, publish the datasets that changed, save the state.
4. Send me one short message: net worth now and the change since last month (wealth.py summary), then a
   checklist of what you need from me (wealth.py plan). Rough numbers, screenshots and exports are all fine;
   anything I skip stays marked as estimated.
5. When I reply: update this month's snapshot, the budget month and the needs/wants map (ask me about new
   categories), publish the changed datasets, save the state, and confirm in two lines.

Rules: never ask for passwords, account numbers or seed phrases; connectors are read-only; no investment
advice; if a price can't be found, keep the old one and say which.
```

## What a good check-in message looks like

> Your dashboard has today's prices: net worth €544,800, up €4,350 since September (markets +€2,900, saved +€1,450).
>
> To finish October I need:
> 1. The joint current account balance (a screenshot is fine)
> 2. Your October bank export, for the budget
> 3. Anything you moved into your investment accounts, if not the usual €950
>
> Anything you skip stays as an estimate.

Keep it this short. No tables, no recap of the steps you took.
