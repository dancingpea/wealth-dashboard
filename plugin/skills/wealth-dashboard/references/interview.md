# Setup interview

The goal: in about 15 minutes, someone who has never thought about this ends up with a working dashboard of
their real finances and a monthly routine that asks them for as little as possible.

Principles:
- Lead. Propose defaults and let them correct you, instead of asking open questions.
- 3 or 4 questions per message at most. Multiple choice where possible.
- Every step accepts screenshots, exports (CSV, PDF, XLSX) or rough numbers. Say so.
- Don't explain the data model. Translate everything into their words ("I'll update the ETF prices myself
  each month; you'll only need to send me your bank balance").
- If they want to stop halfway, build what you have. A dashboard with three accounts is useful.
- Write in their language. The examples below are in English; translate naturally.

## Step 1: Welcome and scope

Message shape (adapt, keep it short):

> I'll set up a private dashboard of everything you own and owe: net worth over time, your accounts,
> investments and, if you like, your monthly budget. It takes about 15 minutes. Rough numbers are fine,
> and you can answer with screenshots. I never need passwords or account numbers; please don't send them.
> Want to see an example with invented numbers first?

Then ask (one message, multiple choice if you can):

1. **Currency** for totals: EUR / USD / GBP / CHF / other. Default to the currency of their country if you
   know it.
2. **What to include** (multi-select): bank and savings accounts; investments (brokerage, ETFs, shares,
   funds); pension or retirement savings; crypto; gold or other precious metals; property (home, rental);
   vehicles; debts (mortgage, loans, credit cards); monthly budget (income and spending).
3. **Whose finances**: just mine / our household. For households: joint accounts count in full; ask whether
   to include the partner's own accounts. For co-owned property with someone outside the household, record
   their share only (say "your 50% share").
4. **How hands-off**: "monthly check-in where I ask you for a few numbers" (recommended) / "I'll update it
   myself when I feel like it".

If they want the demo: build it from `SKILL_DIR/assets/demo-data.json`, publish or send it as "Demo
(invented data)", give one sentence on what each section shows, then continue.

## Step 2: Inventory

Ask for everything in one go, with an example in their currency:

> List your accounts and assets with a rough current value, one per line, or drop screenshots of your
> banking and broker apps. For example:
> - ING current account 2,400
> - ING savings 15,000
> - DEGIRO portfolio about 32k
> - Pension (via work) 41,000
> - Bitcoin 0.2
> - Car, bought 2022 for 24k
> - Mortgage, 260k left

From the answer, build the account list. Mapping rules:

| They say | group | method (default) | notes |
|---|---|---|---|
| current/checking, savings, deposit, money market, cash at home | cash | statement or ask | statement if they'll send exports, ask if they'll type the number |
| brokerage, ETF, shares, funds, robo-advisor, PEA, ISA, Roth IRA, 401(k) in funds they pick, crowdlending | invested | holdings if they'll share positions, else ask/connector | tax wrappers are still `invested`; put the wrapper in the name ("PEA", "ISA") |
| workplace or private pension with a pot value, 3rd pillar, lijfrente | retirement | ask (source: provider portal) | defined-benefit pensions have no pot value: leave them out and say why |
| crypto on an exchange | invested, class crypto | holdings (quantity × price) or connector | |
| crypto in a self-custody wallet | invested, class crypto | holdings + public address | see data-sources: address tracking |
| gold, silver, coins, bars | invested, class gold (or silver) | holdings (quantity in oz or g) | ask whether to value at spot or at the dealer's buyback price |
| home, rental, land | property | ask (yearly estimate) or formula growth | |
| car, motorbike, boat | other, class vehicle | formula depreciation | |
| watches, art, collectibles, money lent to friends | other | ask or fixed | |
| mortgage, car loan, student loan, personal loan | debt | formula (annuity or linear) or statement | |
| credit card balance | debt | statement | only if they carry a balance month to month |

Account ids: short, lowercase, stable (`ing-savings`, `degiro`, `mortgage`). Names: what they call it.
Institution: the brand. Never put account numbers anywhere.

Then confirm with a table (this is the moment most errors get caught):

| Account | Group | Value today | How it updates each month |
|---|---|---|---|
| ING current account | Cash | 2,400 | You send a screenshot or export |
| DEGIRO | Investments | 32,000 | I refresh prices automatically (needs your positions, next step) |
| Mortgage | Debts | 260,000 | Calculated from your loan terms |

Ask: "Anything missing or wrong?"

## Step 3: Detail where it pays off

Only ask what applies. Each item says why it helps, so they can skip it.

**Investment positions** (the biggest win: prices then update without them):
> If you share your positions (a screenshot of the portfolio screen or an export is easiest), I'll update
> prices myself every month and show the performance of each holding. I need, per position: name or ticker,
> quantity, and ideally what you paid in total.

Record each with `holding`: ticker and ISIN when visible, quantity, current price and its currency (with fx
if not base), cost basis in base currency if known (total paid including fees). Uninvested cash in the
account goes in `account --cash`. If cost is unknown, leave it out; the page then shows no gain for that line.
For the account value, the sum of positions plus cash should match what their app shows; if it's off by more
than 1 to 2%, ask.

**Connectors.** For each institution, check if a connector to it is already among your tools. If you can
search a connector registry, search for the institution name and for its category (for example
["degiro", "broker"]) and suggest matches the person can enable in one click. Explain the benefit in one line
("then I can read your positions directly each month"). Never insist; screenshots work fine. If a
connector exists, set the account's method to `connector` and write the exact tool or call in `--source`
so future runs know what to do.

**Crypto in self-custody**: offer address tracking:
> If you give me the public receiving address (never the seed phrase or private key), I can read the balance
> each month. Note: anyone with that address can see its balance on the blockchain, and it will be stored in
> your private dashboard.

Only single addresses. Don't accept extended public keys (xpub) or seed phrases; if someone pastes a seed
phrase, tell them to treat it as compromised and move funds to a new wallet, and don't store it.

**Gold and metals**: quantity and unit (oz or grams), and which price: spot (market) or dealer buyback.
Store the choice in `--price-source`.

**Property**: their estimate today. Offer: update once a year when they feel like it (method `ask`, the value
carries forward, marked estimated), or a growth assumption (method `formula`, type `growth`, ask the rate;
say clearly it's an assumption).

**Vehicle**: purchase price and date. Default 15% per year depreciation, adjustable. Optional: price per km
and odometer for a mileage-based value; then the monthly check-in asks for the odometer only.

**Loans**: outstanding balance today, interest rate, remaining or total term, start date, and type: annuity
(same payment every month, most mortgages and car loans) or linear (fixed capital repayment, common in the
Netherlands and Belgium). With these the balance updates itself. If they don't know, use `statement` and ask
for the balance at each check-in. Interest-only loans: method `fixed`.

**Pension**: pot value and where they see it. Most providers update quarterly or yearly; it will carry
forward between updates. If it's a defined-benefit or state pension with no pot value, leave it out and
explain in one line.

## Step 4: History (optional)

> Do you want the chart to start in the past? If you have older numbers, for example a total at the end of each
> year, or a spreadsheet where you tracked this, send them. Otherwise the chart starts today and grows every
> month.

- Year-end totals per account, or a spreadsheet: convert to a CSV with `date` plus one column per account id
  (and optional `contributions`, `note`), then `history dash.html past.csv`.
- If they only know total net worth for past dates, ask which account group it was mostly in, or put it in
  the largest account for those dates and note it (`note` column). Say this is an approximation.
- Read the warnings: an account missing on a past date counts as zero.

## Step 5: Monthly budget (optional)

Ask how they want to feed it:
1. **Bank exports** (recommended): each month they send the CSV or PDF of their main account(s); you
   categorise transactions. Rules: exclude transfers between their own accounts; investment deposits are
   contributions, not spending; refunds reduce their category; card bill payments are not spending if the
   card's transactions are already counted.
2. **A sheet they already keep**: they send it monthly, or once with history; you copy the monthly totals.
3. **Totals**: they type income and spending by category.

Default categories (rename freely, keep 8 to 14): Income: Salary, Bonus, Side income, Benefits, Other income.
Expenses: Housing, Utilities, Groceries, Eating out, Transport, Insurance, Health, Subscriptions, Shopping,
Travel, Kids, Gifts and donations, Other. Use their language for category names.

Record each month with `budget --month YYYY-MM` (one call per month; `--json` for many categories). Backfill
the last few months if they have exports; 3 to 12 months makes the chart meaningful.

## Step 6: Extras (optional, one message)

1. **Goal**: a net worth target and date? (`settings --set goal_net_worth=... --set goal_by=...`)
2. **Real terms**: show values adjusted for inflation? Offer the official monthly index for their country or
   area (more accurate, you update it monthly) or a flat assumption (for example 2% a year).
3. **Contributions**: how much do they usually invest per month, and is it automatic? This lets the page
   split growth into "money you added" and "market gain". Each check-in confirms the actual amount.

## Step 7: Build, confirm, publish

1. `new` with their currency, title (default "Wealth dashboard", or their own name for it), owner first name,
   language, locale and the right target.
2. `account` and `holding` calls; `history` if any; today's `snapshot` with every value; `budget` months;
   `inflation`; `settings`.
3. `validate`: fix every ERROR; read WARNINGs.
4. `summary`, and compare net worth with what they'd expect. If it looks off, check for a missing debt, a
   double-counted account, or a currency mix-up before publishing.
5. Publish (or save, or send). Record the URL or path in `settings --set dashboard_url=...`.
6. Explain the page in one short paragraph: the big number and its change; the period and Nominal/Real
   buttons; the chart's By group view; allocation; "estimated" tags; holdings; budget; Hide amounts for
   screenshots.

## Step 8: Monthly check-in

Offer it as the last step: "Want me to check in every month? I'll update prices and everything automatic
myself, then send you a short list of what I need from you, usually 2 or 3 numbers." Ask which day (default:
3 days after their payday, or the 1st) and time. Then follow `references/scheduling.md`.

## Wrong turns to avoid

- Asking for every detail of every account before anything exists. Build early, refine later.
- Treating a transfer between their own accounts as income or spending.
- Counting the same money twice (a savings pot shown inside the bank app and also listed separately; a
  pension also counted inside "investments").
- Mixing currencies: every value passed to `snapshot --set` is in base currency unless you add a currency
  suffix with `--fx` (for example `--set ibkr=12000USD --fx USD=0.86`).
- Storing anything that identifies an account (numbers, IBANs) or anything secret (seed phrases, logins).
