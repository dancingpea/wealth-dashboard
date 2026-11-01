# Setup interview

Goal: in about 15 minutes, someone who has never thought about this ends up with a working dashboard of their real
finances and a monthly routine that asks them for as little as possible.

Principles:
- Lead. Propose defaults and let them correct you, instead of asking open questions.
- 3 or 4 questions per message at most. Multiple choice where possible.
- Every step accepts screenshots, exports (CSV, PDF, XLSX) or rough numbers. Say so.
- Don't explain the data model. Translate into their words ("I'll update the ETF prices myself each month; you'll
  only need to send me your bank balance").
- If they want to stop halfway, build what you have. A dashboard with three accounts is useful.
- Write in their language. The examples below are in English.

## Step 1: Welcome and scope

> I'll set up a private dashboard of everything you own and owe: net worth over time, each account and investment,
> your monthly budget against a simple rule, your goals, where you could get to in 30 years, and how you compare
> with other households. It takes about 15 minutes, rough numbers are fine, and you can answer with screenshots.
> I never need passwords or account numbers; please don't send them. Want to see an example with invented numbers first?

Then ask (one message):
1. **Who's in it**: just me / me and a partner (shared finances) / a family with children. For couples: whose money
   counts (both, or only theirs).
2. **Currency** for totals: EUR / USD / GBP / CHF / other (default: where they live).
3. **What to include** (multi-select): bank and savings accounts; investments; pensions; crypto; gold or other
   metals; property; vehicles; debts (mortgage, loans, credit cards); monthly budget.
4. **How hands-off**: a monthly check-in where I ask for a few numbers (recommended) / I'll ask when I want an update.

For the demo, see `publishing.md`, "Demo".

## Step 2: People

For each adult: first name (as it should appear), birth year, and, optionally, gross yearly income from work (before
tax; it is used only to compare earnings and household income with others). Children: how many under 14, and
14 or older (they change the "income per person" comparison).

> For accounts you hold together, how should the dashboard split them between you two: half each, or another split?

`W person` per adult, `W household --children-under-14 N --children-14-plus N --joint-split a=0.5,b=0.5`.
With one adult, every account is theirs; skip the split.

## Step 3: Inventory

> List your accounts and assets with a rough current value and whose they are, one per line, or drop screenshots of
> your banking and broker apps. For example:
> - ING current account (joint) 2,400
> - ING savings (Sam) 15,000
> - DEGIRO portfolio (Robin) about 32k
> - Pension via work (Sam) 41,000
> - Bitcoin 0.2 (Sam)
> - Car, bought 2022 for 24k
> - Mortgage, 260k left

Mapping rules:

| They say | group | method (default) | notes |
|---|---|---|---|
| current/checking, savings, deposit, cash at home | cash | statement or ask | statement if they'll send exports, ask if they'll type the number |
| brokerage, ETF, shares, funds, robo-advisor, PEA, ISA, Roth IRA | invested | holdings if they share positions, else ask/connector | put the wrapper in the name ("PEA", "ISA") |
| workplace or private pension with a pot value | retirement | ask | add `--monthly-contribution` (employer + own, a month) so it counts as saving |
| defined-benefit or state pension (no pot) | leave out | | say why in one line |
| crypto on an exchange | invested, class crypto | holdings or connector | |
| crypto in their own wallet | invested, class crypto | holdings + public address | see data-sources |
| gold, silver, coins, bars | invested, class gold | holdings (oz or g) | spot or dealer buyback price |
| home, rental, land | property | ask (yearly) or formula growth | |
| car, motorbike, boat | other, class vehicle | formula depreciation | |
| watches, art, money lent to friends | other | ask or fixed | |
| mortgage, car loan, student loan | debt | formula (annuity or linear) | needs balance, rate, term, start |
| credit card balance carried | debt | statement | only if carried month to month |

Ids short and stable (`ing-savings`, `degiro`, `mortgage`). Names as they say them. Owner: a person id or `joint`.
Never put account numbers anywhere. Confirm with a table:

| Account | Whose | Group | Value today | How it updates each month |
|---|---|---|---|---|
| ING current account | Joint | Cash | 2,400 | You send a screenshot or export |
| DEGIRO | Robin | Investments | 32,000 | I refresh prices (needs your positions, next step) |
| Mortgage | Joint | Debt | 260,000 | Worked out from the loan terms |

## Step 4: Detail where it pays off

Only what applies. Say why each helps, so they can skip it.

- **Positions** (the biggest win): name or ticker, quantity, and what they paid in total. A screenshot of the portfolio
  screen is easiest. Uninvested cash goes in `account --cash`. Check: positions plus cash should be within 1 to 2% of
  what their app shows.
- **Regions** of each fund (for "Investments by region"): look up the fund's factsheet and record 4 to 6 regions
  (United States, Europe, Japan, Other developed, Emerging markets). Single shares: their home region at 100%.
  Optional; skip if they don't care.
- **Connectors**: for each institution, check whether a connector to it is among your tools, or search the registry by
  name and category. Suggest matches in one line ("then I can read your positions directly"). Never insist.
  With the IBKR connector on, offer the live tab (SKILL.md, "Live broker data").
- **Crypto in their own wallet**: a public receiving address only; never seed phrases, private keys or xpubs. If they
  paste a seed phrase, tell them to treat that wallet as compromised and move the funds, and don't store it.
- **Gold**: quantity and unit, spot or dealer buyback price.
- **Property**: their estimate; update yearly (`ask`) or a growth assumption (`formula` growth, say it's an assumption).
- **Vehicle**: purchase price and date; 15% a year by default; optional price per km and odometer.
- **Loans**: original amount, rate, term, first payment month, and type: annuity (same payment each month) or linear
  (same capital each month). If they only know today's balance: use it as the principal with the remaining term from
  this month. Several mortgage parts: one account each.
- **Pensions**: pot value, where they see it, and the monthly amount paid in.

## Step 5: History and budget (optional)

**History**: "Do you want the chart to start in the past?" Year-end totals per account or an old spreadsheet become a
CSV (`date`, one column per account id, optional `contributions`, `gift_<person>`, `note`) for `W history`. Every
account that existed on a date needs a value there (the tool warns otherwise).

**Budget**: how they want to feed it:
1. Bank exports each month (recommended): you categorise transactions. Transfers between their own accounts are not
   income or spending; investment deposits are money moved (use `--contribution`), not spending; refunds reduce their
   category; a card bill isn't spending if the card's transactions are counted.
2. A spreadsheet they already keep: they send it monthly, or once with history.
3. Totals they type by category.

Then the **needs and wants map** (`W map`): propose a mapping for every spending category and let them correct it.
Needs: housing, utilities, groceries, insurance, childcare, transport to work, phone, health. Wants: eating out,
shopping, travel, hobbies, subscriptions, gifts. Debt payments: `Loan`. Transfers into savings: `Saving`. Use their
category names (in their language).

## Step 6: Goals and comparisons

1. `W goal --defaults` adds the 50/30/20 budget rule (needs at most 50% of income, wants at most 30%, keep at least
   20%) and an emergency fund of 3 months of spending. Ask if they want different numbers.
2. One or two goals of their own, usually an amount by a date: "€500k net worth by 2032", "€100k invested", "debt-free
   by 2035". For one person in a couple: `--view <name>`.
3. Comparison countries: where they live plus 2 or 3 others (where they're from, where they might move). `W settings
   --set compare_countries=NL,FR,US`. Available: EU countries, Norway, Switzerland, Iceland, the UK where published,
   several Balkan countries, and the US.
4. The projection uses 3%, 6% and 9% a year and their last 12 months of saving by default; offer to change either.

## Step 7: Build, check, publish

1. Today's snapshot with every value; budget months; goals; notes for anything assumed (`W note --add`).
2. `W validate` (fix every ERROR, read WARNINGs), `W summary`: compare net worth with what they'd expect. If it's off,
   look for a missing debt, a double-counted account, or a currency mix-up.
3. Publish (`publishing.md`) and hand over.

## Step 8: Monthly check-in

"Want me to check in every month? I'll update prices and everything automatic myself, then send you a short list of
what I need, usually two or three numbers." Ask which day (a few days after payday) and time, then
`references/scheduling.md`.

## Wrong turns to avoid

- Asking for every detail before anything exists. Build early, refine later.
- Treating a transfer between their own accounts as income or spending.
- Counting the same money twice (a savings pot shown inside the bank app and also listed separately; a pension also
  inside "investments").
- Mixing currencies: values are in the base currency unless you add a suffix with `--fx` (`--set ibkr=12000USD --fx USD=0.86`).
- Storing anything that identifies an account, or anything secret.
