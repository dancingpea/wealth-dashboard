# Monthly check-in

## Setting it up

1. Find a scheduling tool among your tools. Names vary by app ("scheduled tasks", "create trigger",
   "routines", "schedule"); some only load after a tool search. Use one that starts a fresh session on a
   schedule and that the person can see and manage. Don't use anything that only lives inside the current
   session and disappears with it.
2. Agree the day and time with the person. Default: monthly, a few days after payday (or the 3rd), 09:00 in
   their time zone. Avoid exactly the top of the hour if the tool suggests spreading start times.
3. Create the task with the prompt below, filled in. It must stand alone: the scheduled run remembers
   nothing of this conversation.
4. Store a one-line description with `settings --set schedule="monthly, 3rd, 09:00 Europe/Amsterdam"` and
   republish.
5. Tell the person in one or two sentences: when it runs, what it will do on its own, and that it will
   message them with a short list. Mention how runs get approved if the tool reports that runs will ask for
   approval.

If there is no scheduling tool, say so plainly and offer alternatives: a recurring calendar reminder (if a
calendar connector is available) saying "Update my wealth dashboard", or simply typing that sentence once a
month in a new chat. With a local file, remind them to attach the file.

## Prompt template

Fill in everything in angle brackets. Keep the person's language for the parts addressed to them.

```
Monthly wealth dashboard update for <first name>.

Use the wealth-dashboard skill in UPDATE mode. If the skill is not available, tell me that the
monthly update could not run because the skill is missing, and stop.

Dashboard: <artifact URL | file path | "ask me to upload my dashboard file">
Currency: <EUR>. Language: <fr>. Time zone: <Europe/Paris>.

Steps:
1. Load the dashboard and run `wealth.py plan` on it.
2. Do every automatic item without asking me: connector balances and positions, latest prices and FX for
   all holdings, on-chain balances, formulas, the latest inflation index if one is used.
3. Save a provisional snapshot dated today, validate, and republish it to the same place.
4. Send me one short message: net worth now and the change since last month (from `wealth.py summary`),
   then a checklist of what you need from me (from the plan). Tell me rough numbers, screenshots and
   exports are all fine, and that anything I skip stays marked as estimated.
5. When I reply, update this month's snapshot, the budget and contributions, validate, republish, and
   confirm in two lines.

Rules: never ask for passwords, account numbers or seed phrases; read-only use of connectors; no
investment advice; if a price can't be found, keep the old one and say which.
```

## What a good check-in message looks like

> Your dashboard is updated with today's prices: net worth €184,300, up €2,150 since September
> (investments +€1,640, of which €500 you added).
>
> To finish October I need:
> 1. Your ING current account balance (a screenshot is fine)
> 2. Your Revolut export for October, for the budget
> 3. How much you invested this month, if not €500
>
> Anything you skip stays as an estimate.

Keep it this short. No tables, no recap of the steps you took.
