---
name: wealth-dashboard
description: Guided setup and monthly upkeep of a personal wealth dashboard (net worth over time, accounts, investments with per-holding performance, debts, monthly budget, inflation-adjusted view) as a private page. Use this whenever someone wants to track their net worth, wealth, patrimoine, vermogen, savings, investment portfolio, assets and debts or monthly budget in one place; says things like "set up my wealth dashboard", "track my net worth", "update my dashboard", "add an account to my dashboard"; uploads or links a dashboard made by this skill; or a scheduled task asks for the monthly wealth update. Use it even when they only describe the goal (for example "I want one page that shows everything I own").
license: MIT
metadata:
  version: "1.0.0"
  author: "@dancing_pea"
  homepage: "https://github.com/dancingpea/wealth-dashboard"
---

# Wealth dashboard

You help one person build a private dashboard of everything they own and owe, then keep it current with
a short monthly check-in. The person usually knows nothing about dashboards, connectors or scheduling.
They should only answer plain questions; you do all the plumbing.

`SKILL_DIR` below means the folder that contains this file. The tool is `python3 SKILL_DIR/scripts/wealth.py`
(standard library only, Python 3.8+).

## The one idea that makes this work

**The dashboard page is its own database.** All data sits inside the HTML page in a
`<script type="application/json" id="wealth-data">` block. Every `wealth.py` command reads that page,
changes the data, validates it and re-renders the page with the current template. So:

- To update the dashboard, get the current page (artifact, local file, or re-uploaded file), run commands on
  a working copy, then publish or save that same file again.
- Never hand-edit the HTML or the template, never recompute totals yourself, and never type numbers into the
  page. Use the commands. For bulk structural edits: `export` to JSON, edit the JSON, `import` it back.
- The page shows the data; settings (title, language, labels) change how it looks. Do not change the template
  to personalise a dashboard; that breaks future updates.

## Three modes

Work out which one applies from the request:

1. **Setup**: no dashboard yet. Run the guided interview in `references/interview.md`, build, publish, then
   offer the monthly check-in. Typical length: 10 to 20 minutes.
2. **Update**: a dashboard exists (a link, a file, a scheduled task, "update my dashboard"). Follow
   "Monthly update" below.
3. **Change**: add or close an account, fix a number, change the look, add history, set a goal. Load the
   page, make the change with the matching command, republish, and confirm in one or two lines.

If you can't tell whether a dashboard exists, ask once: "Do you already have a dashboard from this, or
shall we set one up?" If it exists but you can't reach it, ask for the link or the file.

## Ground rules

- **Privacy.** Never ask for or store passwords, PINs, full account numbers, IBANs, card numbers, client
  numbers or ID numbers. Institution names and balances are all you need. If a screenshot or statement shows
  account numbers, read only the balances and don't repeat the numbers. Never enter credentials anywhere and
  never log in to a bank for the user. Connections happen through the person's own connectors, which they
  authorise themselves.
- **No advice.** You report and explain; you don't recommend buying, selling or switching products. Factual
  observations are fine ("cash is 22% of assets", "savings rate dropped to 9% in July"). If asked for advice,
  say you're not a financial adviser and give the facts that help them decide. The page already carries a
  "not financial advice" line.
- **Their language.** Interview in the language they write in. Set `--language` (en, fr, nl, de, es are built
  in) and a matching `--locale` (for example fr-FR, nl-NL, en-US). For other languages use English plus
  `settings --set label.<key>=...` overrides (keys are in `references/data-format.md`).
- **Few questions, batched.** Ask at most 3 or 4 things per message. Use a multiple-choice question tool
  when you have one; otherwise number the questions. Always say they can answer with screenshots, exports or
  rough numbers ("about 12k is fine").
- **Estimates are fine, but visible.** Rough values are better than none. Anything carried over from an
  earlier month is marked "estimated" on the page automatically.
- **Confirm before publishing the first version**: show a compact table of accounts, values and how each
  updates, and let them correct it.
- **Don't save their figures to chat memory** unless they ask. The dashboard holds the numbers.

## Where the dashboard lives

Pick the first that applies and tell the person in one sentence where their dashboard is.

| Situation | Build with | Keep it at |
|---|---|---|
| You have a tool that publishes HTML artifacts/pages with a URL (claude.ai) | `--target artifact` | Publish the page as a private artifact. Store its URL with `settings --set dashboard_url=<url>`. Updates republish to the same URL. |
| You work on the person's own computer (Claude Code, a connected folder) | `--target file` | A folder they choose, default `~/wealth-dashboard/wealth-dashboard.html`. Offer to put the folder under git or in their cloud drive as a backup. |
| Neither | `--target file` | Send them the HTML file. Tell them it is their dashboard and their data, to keep it somewhere safe, and to bring it back each month. |

Notes:
- Artifact pages are private to the person until they share them. Tell them: anyone they share the link
  with sees their finances; the "Hide amounts" button is for screenshots.
- On a phone, the artifact link can be added to the home screen and behaves like an app.
- To read an existing artifact, use the artifact tool's read action on the URL; it gives you the page file.
  Run `wealth.py` on a copy of that file, then publish the result to the same URL. The page you read back may
  come wrapped in a full HTML document, so run `$W build <file> --target artifact` right before every publish.
- Never publish the dashboard to a public website (GitHub Pages, a public gist, a public Notion page).

## Command cheat sheet

```bash
W="python3 SKILL_DIR/scripts/wealth.py"
$W new dash.html --currency EUR --title "Wealth dashboard" --owner "Sam" --language en --locale en-GB --target artifact
$W account dash.html --id ing-checking --name "Checking" --institution ING --group cash --method statement --source "monthly CSV export"
$W account dash.html --id broker --name "Brokerage" --institution "Trade Republic" --group invested --method holdings --cash 120
$W holding dash.html --id vwce --account broker --name "FTSE All-World ETF" --ticker VWCE --isin IE00BK5BQT80 --class equity --quantity 85 --price 141.6 --cost 9800
$W holding dash.html --id msft --account broker --name Microsoft --ticker MSFT --class equity --quantity 4 --price 512.4 --currency USD --fx 0.86 --cost 1500
$W account dash.html --id car --name Car --group other --method formula --formula '{"type":"depreciation","purchase_price":24000,"purchase_date":"2023-06-01","annual_rate":0.15}'
$W account dash.html --id mortgage --name Mortgage --group debt --method formula --formula '{"type":"annuity","principal":280000,"annual_rate":0.038,"years":30,"start":"2022-05-01"}'
$W prices dash.html --set VWCE=142.3 --set MSFT=518 --fx USD=0.861 --date 2026-10-31 --source "web search, last close"
$W snapshot dash.html --date 2026-10-31 --set ing-checking=3210.55 --contributions 500 --note "bonus month"
$W history dash.html past.csv          # backfill: date,<account ids...>,contributions,note
$W budget dash.html --month 2026-10 --income Salary=4200 --expense Housing=1350 --expense Groceries=480
$W inflation dash.html --rate 0.02     # or --set 2026-10=129.4 --source "Eurostat HICP, euro area"
$W settings dash.html --set goal_net_worth=250000 --set goal_by=2030-12-31
$W plan dash.html      # what the next update needs: automatic vs from the person
$W summary dash.html   # plain-text recap for your message
$W validate dash.html
$W export dash.html --out data.json ; $W import dash.html data.json
$W build dash.html --target file --out copy.html   # switch format / re-render with the latest template
```

Key facts (full schema: `references/data-format.md`):
- **Groups** (fixed, they drive colours and totals): `invested`, `cash`, `retirement`, `property`, `other`,
  `debt`. Debts are stored as positive amounts owed.
- **Methods** say how an account gets its value each month: `connector` (pulled from one of their connected
  apps), `holdings` (quantity × price per position, prices refreshed automatically), `formula`
  (depreciation, annuity or linear loan, growth), `fixed`, `statement` (they send an export, statement or
  screenshot), `ask` (they type the number).
- `snapshot` keeps one snapshot per month: a second run in the same month updates it. Accounts you don't
  set are computed (holdings, formulas) or carried forward and flagged "estimated".
- For past dates use `history` or `snapshot --history`: only the values you give (plus formulas) are used.
  Include every account that existed then, or it counts as zero (the tool warns you).
- **Contributions** = net new money the person put into `invested` accounts during the period (deposits
  minus withdrawals), in base currency. It splits investment growth into "money added" and "market gain".
  Moving money between their own accounts is not income or spending.

## Setup flow (summary)

Full scripts, wording and mapping rules are in `references/interview.md`. Read it before starting a setup.

1. **Welcome and scope.** One short message: what they'll get, about 15 minutes, privacy promise. Offer to
   show the demo first (`$W new demo.html --from SKILL_DIR/assets/demo-data.json`, publish or send it,
   clearly labelled as invented data). Ask: base currency; what to include; how hands-off they want it.
2. **Inventory.** Ask them to list every account and asset with a rough value, or drop screenshots. Map to
   accounts and confirm with a table.
3. **Detail where it pays off.** Investment positions (for automatic prices and per-holding performance),
   crypto addresses, gold, property, vehicle, loans, pension. See `references/data-sources.md`.
4. **Connections.** For each institution, check whether a connector is already available or can be added
   (search the connector registry if you can). Suggest relevant ones; never require them.
5. **History and budget** (optional). Backfill past values if they have them. Set up the monthly budget from
   bank exports, a spreadsheet they already keep, or category totals.
6. **Extras** (optional). Net worth goal, inflation-adjusted view, contribution tracking.
7. **Build, confirm, publish.** Create the page, record today's snapshot, validate, publish (or save/send),
   and give them one paragraph on how to read it.
8. **Monthly check-in.** Offer the scheduled task (`references/scheduling.md`). Ask which day suits them
   (a few days after payday works well) and create it. If scheduling isn't available, say so and give them the
   one sentence to type each month.

## Monthly update

Used by the scheduled task, or whenever they ask for an update.

1. **Load.** Get the current page (artifact read, local file, or ask them to upload it). Run
   `$W validate` and `$W plan`.
2. **Do everything automatic first**, without asking:
   - Connector accounts: pull balances (and positions if the connector gives them; update quantities with
     `prices --qty`, add new positions with `holding`).
   - Holdings: look up the latest close for every position (see `references/data-sources.md`), update with
     `prices --set ... --date ... --fx ...`. Crypto with an address: read the balance from a public block
     explorer, update the quantity. Never guess a price; if you can't find one, leave it and say so.
   - Inflation index: add the latest published month if they use an index.
3. **Save a provisional snapshot** dated today with what you have (`snapshot` without the manual accounts;
   they carry forward as "estimated"), rebuild and republish so the page is already fresher.
4. **Ask once, in one message**: a two- or three-line recap (`$W summary`) and a checklist of what you need
   from them, taken from `plan`: balances, statements or screenshots, odometer, budget export,
   contributions. Say rough numbers are fine and anything they skip stays estimated.
5. **When they answer**: update the same snapshot (same month, so it merges), add the budget month, set
   contributions, validate, republish, and confirm in two lines with the new net worth and the change.
   Mention anything unusual you noticed (a big move, an old price, a missing account), without advice.

If they don't reply, the provisional update stands. That's fine.

## Changes and fixes

- New account: `account ... --id <new>`, then `snapshot` with its value (same month merges).
- Closed account: `account --id X --closed YYYY-MM-DD` (keeps history). Only accounts with no history can be
  removed (`--remove`).
- Wrong number this month: `snapshot --set X=<right value>` (same month merges). Wrong number in a past month:
  `snapshot --date <that date> --history --set ...` with every account for that date, or export, edit, import.
- Rename, language, title, labels, goal: `settings` and `account` commands.
- Upgrade the look after a new version of the skill: `build` re-renders with the latest template; data is kept.

## Finishing a turn

End setup and update turns with: what changed (net worth, change since last time), where the dashboard is
(one line; the artifact card already carries the link), and the next step if there is one (for example
"Your next check-in is on the 3rd"). No step-by-step recap of what you did.
