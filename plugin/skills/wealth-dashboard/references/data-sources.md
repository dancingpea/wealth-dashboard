# Getting the numbers

How to get each kind of value, from most automatic to least. Record where a value came from in the
account's `--source` (or the holding's `--price-source`) so the next run repeats it without asking.

## Connectors (the person's own connected apps)

- First check which tools you already have: a broker, bank, budgeting or spreadsheet connector may be there.
- If you can search a connector registry, search with the institution's name plus a category word (for
  example ["interactive brokers", "broker"], ["revolut", "bank"], ["plaid", "bank aggregator"],
  ["google sheets"]). Suggest only what matches. Don't assume a connector exists for a given bank.
- A connected broker usually offers an account summary (net liquidation value or total value) and positions.
  Use the summary as the account value (`snapshot --set`) and positions to refresh holdings (`prices --qty`,
  new positions via `holding`). Convert to base currency.
- Connectors can fail or need re-authorising. Retry once; then fall back to asking, and say which connection
  needs attention.
- Only read. Never place orders, move money or change settings through a connector as part of this skill.

## Screenshots, statements and exports

- Screenshots: read the balance and its date. Ignore and never repeat account numbers or names of other
  people. If two numbers could be "the balance" (available vs booked, value vs invested), ask.
- PDF statements: the closing balance at the period end is the value. For investment statements, take the
  total value, and positions if listed.
- CSV exports: the balance after the last transaction, if the file has a balance column. Otherwise ask for
  the balance; summing transactions rarely reproduces it.
- Budget from transactions: group by month, map merchants to categories, then check the result with the
  person the first time ("I put Albert Heijn under Groceries and Tikkie transfers under Other: OK?"). Keep
  a stable mapping in your head for the session; mention new or ambiguous merchants.

## Market prices (holdings)

- Search for the instrument by ISIN or by ticker plus exchange (for example "IE00BK5BQT80 price",
  "VWCE Xetra price"). Prefer the exchange, the fund issuer, or a major financial data site.
- Use the latest close (or the price on the snapshot date for a past update). Check the currency of the
  quote matches the holding's currency; a London listing may be in GBX (pence): divide by 100 for GBP.
- Record the date: `prices --set VWCE=142.30 --date 2026-10-31 --source "Xetra close"`.
- FX: see "Exchange rates" below.
- If you can't find a reliable price, keep the old one and say which one is stale. The page flags prices
  older than 35 days.
- Funds without a ticker (pension funds, some mutual funds): search by ISIN or the fund's name; if nothing is
  public, use the account value from a statement instead of holdings.

## Crypto

- Prices: latest price in base currency from a major exchange or price site, by symbol.
- Self-custody Bitcoin address: fetch
  `https://mempool.space/api/address/<address>` (or `https://blockstream.info/api/address/<address>`) with
  your web fetch tool. Balance in BTC = (chain_stats.funded_txo_sum − chain_stats.spent_txo_sum) / 100,000,000.
  Add mempool_stats the same way if there are unconfirmed transactions. Update with
  `prices --qty btc=<balance>`.
- Other chains: use a public block explorer page for the address if your fetch tool can read it; otherwise ask
  for the balance. Never ask for or store seed phrases, private keys or extended public keys.
- If the fetch is blocked, ask the person for the balance and keep the address for the next try.

## Precious metals

- Store quantity with a unit: `--unit oz` (troy ounce) or `--unit g`. 1 troy ounce = 31.1035 g.
- Spot: search the gold (or silver) spot price per troy ounce in base currency. Per gram = per oz / 31.1035.
- Dealer buyback: search the dealer's buyback page for the exact coin or bar if the person chose that; buyback
  is usually a few percent below spot.

## Pensions

- Defined-contribution pots: value from the provider portal or annual statement. Usually updated quarterly
  or yearly; carry forward in between (it shows as estimated, which is correct).
- Record the amount paid in each month (employer plus own) with `account --monthly-contribution`: it is counted as
  saving in the "saved, markets, gifts" split and in the projection. If the pension is fully invested in one public
  fund, you can also value it between statements as units × the fund's price (ask how many units they hold).
- Defined-benefit and state pensions show an expected yearly income, not a pot. Leave them out of net worth
  unless the person insists; if they do, ask them which value they want to use and note it as their estimate.
- Don't count the same money twice if a pension is also visible in a broker account.

## Property

- Default: the person's own estimate, refreshed when they want (yearly is plenty). Optional sources to
  mention: recent sales of similar homes, the official house price index for their country or region, a
  municipal valuation where one exists.
- Growth formula only if they want it: `{"type":"growth","value":350000,"date":"2026-10-31","annual_rate":0.03}`.
  Make sure they understand it's an assumption, not a valuation.

## Vehicles

- Formula: `{"type":"depreciation","purchase_price":24000,"purchase_date":"2023-06-01","annual_rate":0.15}`.
  15% per year is a reasonable default for cars; adjust if they know better.
- Mileage-based: add `"per_km":0.05,"km_at_purchase":12000,"km":40000`. Each check-in, update the odometer
  with `snapshot --formula car.km=41250`.
- A yearly reality check against similar used listings is optional; if they give a better value, set it with
  `snapshot --set car=...` and adjust `annual_rate` so the formula lands near it.

## Loans

- Annuity (equal monthly payments): `{"type":"annuity","principal":280000,"annual_rate":0.038,"years":30,"start":"2022-05-01"}`.
  `principal` is the original amount and `start` the month of the first payment. If they only know today's balance,
  use today's balance as principal, the remaining term as years, and this month as start.
- Linear (same capital repaid each month, interest on top): `{"type":"linear","principal":200000,"annual_rate":0.035,"years":25,"start":"2024-01-01"}`.
- The schedule feeds the "Debt repayment" card and the projection, and splits loan payments in the budget: map the
  budget category that holds the payment to `Loan`, so its interest counts as needs and its principal as saved.
- Several loan parts (common for Dutch mortgages): one account per part, all in group `debt`.
- Extra repayments, rate resets or refinancing: update the formula to the new balance and terms from that
  date (same rule as above).
- Compare with a statement once a year if they have one.

## Exchange rates

- Always "base currency per 1 unit of the other currency": with a EUR base, `--fx USD=0.861` means 1 USD = 0.861 EUR.
- Use a reference rate for the same date (ECB euro reference rates for EUR; otherwise a major source).
- Each monthly run passes the rates of every position currency to `W prices --fx`, plus EUR and USD when the base is
  something else: the comparison section converts the household's figures into euros and dollars with them.

## Regions (for "Investments by region")

- Funds: the "geographic breakdown" on the issuer's factsheet (iShares, Vanguard, Amundi, Xtrackers, etc.). Group into
  United States, Europe, Japan, Other developed, Emerging markets (or finer if they like), weights adding up to 1.
- Single shares: the company's home country region at 1.
- Pensions invested in a known fund: the same, recorded on the account (`account --region`).
- Refresh once a year at most; region weights move slowly.

## The comparison section

- The survey tables ship with the skill (`assets/reference/`), already brought to recent prices. Nothing about the
  household is sent anywhere: the page places their figures in those tables in the browser.
- New survey waves come with new versions of the skill. Nothing to do monthly.
