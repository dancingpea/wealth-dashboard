---
name: wealth-dashboard
description: Guided setup and monthly upkeep of a private wealth dashboard for a person or household - net worth over time, every account, investments with per-position performance, debts and loan schedules, monthly budget against a 50/30/20 rule, goals with deadlines, a 30-year projection and how you compare with other households by country. Use this whenever someone wants to track their net worth, wealth, patrimoine, vermogen, savings, portfolio, assets and debts or budget in one place; says "set up my wealth dashboard", "update my dashboard", "add an account", "change my goal"; or a scheduled task asks for the monthly wealth update. Use it even when they only describe the goal, like "one page that shows everything we own".
license: MIT
metadata:
  version: "2.0.0"
  author: "@dancing_pea"
  homepage: "https://github.com/dancingpea/wealth-dashboard"
---

# Wealth dashboard

You build one person's or household's private dashboard of everything they own and owe, then keep it current with a
short monthly check-in. The person usually knows nothing about dashboards, connectors or scheduling. They answer plain
questions; you do all the plumbing. Settings and goals change when they ask you in chat.

`SKILL_DIR` is the folder holding this file. The tool is `python3 SKILL_DIR/scripts/wealth.py` (standard library only).
Below, `W` means that command.

## How it fits together

- **State file** `wealth.json`: the only source of truth (people, accounts, positions, monthly snapshots, budget,
  goals, settings). Every `W` command validates and saves it. Never edit numbers into anything else.
- **Dashboard**: an artifact made from the **Dashboard** artifact type. It holds a fixed page (`files/index.html`,
  identical for everyone, written by `W store`) and 15 file datasets (`W datasets` writes them from the state). The page
  computes everything from the datasets, so a change is always: change the state, rewrite the datasets that changed,
  upload them, point the dataset documents at the new files.
- **Saved state**: after every change, upload `wealth.json` as an asset of the dashboard and record its url in the
  dashboard's store document `pipeline/state` (`{state, updated, skill}`). That is how next month's run finds it.
- **No Dashboard type** (Claude Code in a terminal, or the type isn't offered): `W standalone wealth.json
  wealth-dashboard.html` makes one self-contained page with the same look and features. Keep it with `wealth.json` in
  a folder the person chooses, or publish it as a private HTML artifact (`--target artifact`).

Read `references/publishing.md` before the first publish and before any update: it has the exact calls.

## Three modes

1. **Setup**: no dashboard yet. Follow `references/interview.md` (about 15 minutes), build, publish, offer the monthly
   check-in (`references/scheduling.md`).
2. **Update**: a scheduled task or "update my dashboard". Follow "Monthly update" below.
3. **Change**: "add my new savings account", "make my savings goal 25%", "Robin and I split the joint account 60/40",
   "compare us with Spain too". Load the state, run the matching command, republish the datasets that changed, save
   the state, confirm in one or two lines.

If you can't tell whether a dashboard exists, ask once. Look first: the person's artifacts (Artifact `list`, title
"Wealth dashboard") and a `wealth.json` in their folders.

## Ground rules

- **Privacy.** Never ask for or store passwords, PINs, full account numbers, IBANs, card numbers or ID numbers.
  Institution names and balances are all you need. Read only balances from screenshots and statements, never repeat
  account numbers. Never sign in anywhere for the person. Only use connectors they switched on themselves, and only to
  read. `W validate` warns when text looks like an account number or a seed phrase: remove it.
- **Their data stays theirs.** The dashboard and its files are private to the person until they share it; tell them
  that anyone they share it with sees everything on it. Never put their figures in a public place, a message to anyone
  else, or a web request.
- **No advice.** Report and explain; don't recommend buying, selling or switching products. Factual observations are
  fine ("cash covers 11 months of spending"). If asked for advice, say you're not a financial adviser and give the
  facts that help them decide.
- **Their language.** Talk in their language. The page itself is in English for now; say so if they write in another
  language, and offer to name accounts, categories and goals in their language (those labels show on the page).
- **Few questions, batched.** At most 3 or 4 per message, multiple choice when you can. Rough numbers, screenshots and
  exports are always fine.
- **Estimates are visible.** Anything not refreshed this month keeps its value and shows as estimated.
- **Confirm before the first publish**: a compact table of people, accounts, values and how each updates.
- Don't save their figures to chat memory unless they ask: the dashboard holds them.

## Command cheat sheet

```bash
W new wealth.json --currency EUR --title "Wealth dashboard"
W person wealth.json --id sam --name Sam --birth 1989-05 --gross 74000          # one per adult
W household wealth.json --children-under-14 1 --joint-split sam=0.5,robin=0.5
W settings wealth.json --set compare_countries=NL,DE,US --set fx.USD=0.862 --set checkin_day=3
W account wealth.json --id broker --name "Sam's brokerage" --owner sam --group invested --method holdings --institution "Trade Republic"
W holding wealth.json --id vwce --account broker --name "FTSE All-World ETF" --ticker VWCE --class equity --quantity 85 --price 141.6 --cost 9800 \
    --region "United States=0.63" --region Europe=0.15 --region "Emerging markets=0.10" --region Japan=0.06 --region "Other developed=0.06"
W account wealth.json --id pension --name "Sam's pension" --owner sam --group retirement --method ask --monthly-contribution 650
W account wealth.json --id mortgage --name Mortgage --owner joint --group debt --method formula \
    --formula '{"type":"annuity","principal":245000,"annual_rate":0.031,"years":30,"start":"2022-10-01"}'
W account wealth.json --id car --name Car --owner joint --group other --class vehicle --method formula \
    --formula '{"type":"depreciation","purchase_price":24000,"purchase_date":"2023-06-01","annual_rate":0.15}'
W prices wealth.json --set VWCE=142.3 --fx USD=0.861 --date 2026-11-03 --source "exchange close"
W snapshot wealth.json --date 2026-11-03 --set current=3210 --set pension=48200 --contribution broker=950 --gift robin=15000
W budget wealth.json --month 2026-10 --income "Sam's salary=3480" --expense Groceries=760 --expense "Mortgage payment=1046"
W map wealth.json --set Groceries=Needs --set "Eating out=Wants" --set "Mortgage payment=Loan" --set "Transfer to savings=Saving"
W goal wealth.json --defaults                                                     # 50/30/20 + 3 months of cash
W goal wealth.json --id nw-750k --kind milestone --label "€750k net worth" --metric net_worth --target 750000 --deadline 2031-12-31
W history wealth.json past.csv          # backfill: date, one column per account id, optional contributions, gift_<person>, note
W note wealth.json --add "Apartment: our own estimate, updated once a year"
W validate wealth.json ; W plan wealth.json ; W summary wealth.json ; W show wealth.json
W datasets wealth.json out/             # 15 files + manifest; prints which changed since the last publish
W store wealth.json store/ --urls urls.json [--versions versions.json] [--only-changed] [--live ibkr]
W published wealth.json --manifest out/manifest.json --urls urls.json --dashboard-url <url>
W standalone wealth.json wealth-dashboard.html [--target artifact]
```

Key facts (full schema: `references/data-format.md`):
- **Groups**: `invested`, `cash`, `retirement`, `property`, `other`, `debt`. Debts are entered as positive amounts owed.
- **Owner**: a person id or `joint`. Joint lines are split between people by `--joint-split` (equal if unset). With one
  person, owner defaults to them.
- **Methods**: `connector` (read from their connected app), `holdings` (quantity × price, prices refreshed by you),
  `formula` (depreciation, annuity or linear loan, growth), `fixed`, `statement` (they send a statement or screenshot),
  `ask` (they type the number).
- One snapshot per month: a second `snapshot` in the same month updates it. Accounts you don't set are computed
  (positions, formulas) or kept from the last month and flagged estimated.
- **Money moved** is not saving or market gain: record deposits into investment accounts with `--contribution
  ACCOUNT=AMOUNT` (negative for withdrawals), gifts and inheritances with `--gift`. Pension `--monthly-contribution`
  is counted automatically. This is what splits each month's change into saved, markets and gifts.
- **Budget categories** map to `Needs`, `Wants`, `Loan` (debt payments: interest counts as needs, principal as saved,
  from the loan's schedule) or `Saving` (transfers to savings: not spending). Unmapped categories count as wants.
- **Exchange rates** are always "base currency per 1 unit": `--fx USD=0.86` when the base is EUR. Keep `fx.EUR` and
  `fx.USD` current for the comparison section (the monthly `prices --fx` does this).

## Setup (summary)

Full wording and mapping rules: `references/interview.md`. Where numbers come from: `references/data-sources.md`.

1. **Welcome and scope**: what they'll get, about 15 minutes, the privacy promise. Offer the demo
   (`references/publishing.md`, "Demo"). Ask: who is in the household (adults, children), base currency, what to
   include, how hands-off.
2. **People**: first names, birth year (for age-group comparisons), gross yearly income from work (optional, for
   income comparisons), how joint money splits.
3. **Inventory**: every account and asset with a rough value and its owner; map, then confirm with a table.
4. **Detail where it pays off**: positions (prices then update themselves and each position gets its performance),
   regions of their funds, crypto address, gold, property, vehicle, loan terms, pension contributions. Check which of
   their institutions have a connector (search the connector registry if you can) and suggest them; never require.
5. **History and budget** (optional): past values for the chart; 3 to 12 months of income and spending and the
   needs/wants map.
6. **Goals**: start with `W goal --defaults`, then ask for one or two of their own (an amount by a date). Comparison
   countries (default: where they live plus 2 or 3 they care about).
7. **Build and publish**: today's snapshot, `W validate`, `W summary` (sanity check), then publish as in
   `references/publishing.md`. Give them one paragraph on what each tab shows.
8. **Monthly check-in**: offer it and set it up (`references/scheduling.md`).

## Monthly update

1. **Load**: `pipeline/state` → download the state asset → `W validate`, `W plan` (details in `publishing.md`).
2. **Automatic first, without asking**: connector balances and positions; latest prices and exchange rates for every
   position (`W prices`, which also records the price history); on-chain balances; formulas update themselves.
3. **Provisional snapshot** dated today (`W snapshot`, manual accounts carry over as estimated), publish the changed
   datasets, save the state. The dashboard is already fresher.
4. **Ask once, in one message**: two lines of recap from `W summary`, then the checklist from `W plan` (balances,
   statements, odometer, budget export, money moved). Rough numbers are fine; anything skipped stays estimated.
5. **When they answer**: update the same snapshot (same month merges), add the budget month, map new categories (ask
   if unsure), publish changed datasets, save the state, confirm in two lines. Mention anything unusual, without advice.

## Changes

- Settings, goals, map, people, countries, projection returns: the matching command, then republish the changed
  datasets (`W datasets` lists them) and save the state. Then confirm what changed and where it shows.
- New account: `account` then `snapshot --set` its value. Closed account: `account --closed DATE` (keeps history).
- A wrong past value: `snapshot --date <that date> --history --set ...` with every account for that date.
- A newer version of this skill changes the page: rewrite only `files/index.html` with `W store ... --only-changed`
  and an empty urls file (see `publishing.md`, "Upgrade the page"). The data stays as it is.

## Live broker data (optional)

If the person has the Interactive Brokers connector switched on and wants live figures, build the page with
`--live ibkr`: it adds a "Live IBKR" tab whose four sources are live queries run with each viewer's own IBKR
connection (positions, balances, 12-month time-weighted return, six months of weekly prices). Before writing them, make
each call yourself once (`get_account_positions`, `get_account_balances`, `get_pa_performance_all_periods`) to confirm
the connector works, and pass its name as it appears in your tools with `--connector`. The rest of the dashboard
still comes from the monthly state (the IBKR account is an ordinary `connector` account there).

## Finishing a turn

Say what changed (net worth and the change since last time), where the dashboard is (the artifact card carries the
link), and the next step if there is one ("your next check-in is on the 3rd"). No recap of the steps.
