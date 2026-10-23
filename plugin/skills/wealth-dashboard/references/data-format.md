# Data format (`wealth-dashboard/1`)

The data is one JSON object embedded in the page. Prefer the `wealth.py` commands; use this reference when
you need `export` / edit / `import`, or to understand what the page shows.

```json
{
  "schema": "wealth-dashboard/1",
  "settings": { ... },
  "accounts": [ ... ],
  "holdings": [ ... ],
  "snapshots": [ ... ],
  "budget": { "months": [ ... ] }
}
```

## settings

| Field | Meaning |
|---|---|
| `title` | Page title. Default "Wealth dashboard". |
| `owner` | First name or household name shown under the title (optional). |
| `currency` | Base currency, ISO code (EUR, USD, GBP, CHF...). Every stored value is in this currency. |
| `language` | UI language: `en`, `fr`, `nl`, `de`, `es`. Others fall back to English plus `labels`. |
| `locale` | Number and date format, for example `en-GB`, `en-US`, `fr-FR`, `nl-NL`, `de-CH`. |
| `checkin_day` | Day of month of the scheduled check-in (informational). |
| `goal` | `{"net_worth": 500000, "by": "2030-12-31"}` (optional). Shows a progress bar. |
| `inflation` | `{"annual_rate": 0.02}` or `{"index": {"2026-01": 128.1, ...}, "source": "..."}` (optional). Enables the Real view. |
| `labels` | UI text overrides, `{"netWorth": "Vermögen", ...}`. Keys: see the list below. |
| `group_labels` | Group name overrides, `{"other": "Car and other"}`. |
| `dashboard_url` | Where the dashboard lives (artifact URL or file path), for scheduled runs. |
| `schedule` | Short description of the scheduled check-in (for example "monthly, 3rd, 09:00 Europe/Paris"). |
| `backup` | Where backups go, if any. |
| `demo` | `true` only for the demo; shows an "invented data" banner. |
| `created`, `updated` | Set by the tool. |

UI label keys: netWorth, asOf, hide, show, p1m, pytd, p1y, p5y, pall, period, basis, nominal, real, realNote,
since, invGains, savingOther, totalAssets, debts, investments, cash, savingsRate, contributions, perMonth,
marketGain, returnApprox, avgOver, goal, chartTitle, total, byGroup, showTable, showChart, oneSnapshot,
allocation, tabGroups, tabAccounts, tabClasses, assetsOnly, accountsTitle, account, value, change, share,
estimated, estimatedHint, newAcc, holdingsTitle, holding, quantity, price, cost, gain, ret, weight, oldPrice,
holdingsNote, budgetTitle, last12, income, expenses, saved, avgRate, categories, vsAvg, tapMonth, date, note,
assets, snapshots, disclaimer, madeWith, demo, empty, noDebt, updated, changeIn, g_invested, g_cash,
g_retirement, g_property, g_other, g_debt, c_equity, c_bonds, c_crypto, c_gold, c_cash, c_pension, c_property,
c_vehicle, c_other, c_mixed. Placeholders in braces ({date}, {v}, {p}, {n}, {cur}, {month}) must be kept.
Set with `settings --set label.<key>=<text>`.

## accounts[]

| Field | Meaning |
|---|---|
| `id` | Stable id: lowercase letters, digits, `-`, `_`. Never reuse an id for a different account. |
| `name` | What the person calls it. |
| `group` | `invested`, `cash`, `retirement`, `property`, `other`, `debt`. |
| `method` | `connector`, `holdings`, `formula`, `fixed`, `statement`, `ask`. |
| `class` | Asset class for the allocation view (optional): `equity`, `bonds`, `crypto`, `gold`, `cash`, `pension`, `property`, `vehicle`, `mixed`, `other`, or any word. |
| `institution` | Brand name of the bank, broker or provider (optional). |
| `source` | How to get the value next time, in plain words or a tool call (optional, read by future runs). |
| `cash` | Uninvested cash inside a holdings account, in base currency. |
| `formula` | For `method: formula`. Types below. |
| `closed` | `YYYY-MM-DD`; the account stops appearing after that date but its history stays. |
| `note` | Free text. Never account numbers. |

Formulas (all amounts in base currency, rates as decimals):

| type | fields | value at date D |
|---|---|---|
| `depreciation` | purchase_price, purchase_date, annual_rate, optional per_km, km_at_purchase, km, floor | price × (1 − rate)^years − per_km × (km − km_at_purchase), not below floor |
| `annuity` | principal, annual_rate, years, start | remaining balance of an equal-payment loan after the months since start |
| `linear` | principal, years, start | principal × (1 − months / total months) |
| `growth` | value, date, annual_rate | value × (1 + rate)^years since date |

## holdings[]

| Field | Meaning |
|---|---|
| `id` | Stable id (often the ticker in lowercase). |
| `account` | Id of the account holding it. |
| `name`, `ticker`, `isin` | Identification. `prices --set` accepts the id or the ticker. |
| `class` | Asset class (as above). |
| `quantity`, `unit` | Number of units; unit label optional (oz, g, BTC). |
| `price`, `currency`, `fx` | Price per unit in `currency` (default base). If not base, `fx` = base per 1 unit of currency. |
| `price_date`, `price_source` | When and where the price came from. Prices older than 35 days are flagged. |
| `cost` | Total cost basis in base currency (what was paid, including fees). Optional. |
| `address` | Public blockchain address for automatic quantity (optional). |

Value in base currency = quantity × price × fx. For accounts with method `holdings` (or `connector` with
holdings), `snapshot` computes the account value as the sum of its holdings plus `cash`, unless you pass an
explicit value.

## snapshots[]

```json
{"date": "2026-10-31", "values": {"ing": 3210.55, "broker": 41200.0, "mortgage": 241800.0},
 "contributions": 500, "carried": ["pension"], "note": "bonus month", "fx": {"USD": 0.861}}
```

- One per month (a second `snapshot` in the same month updates it). Sorted by date.
- `values`: every open account's value in base currency on that date. Debts are positive amounts owed.
  An account absent from a snapshot counts as zero on that date.
- `carried`: accounts whose value was copied from an earlier month (shown as "estimated").
- `contributions`: net new money into `invested` accounts since the previous snapshot.

## budget.months[]

```json
{"month": "2026-10", "income": {"Salary": 4200}, "expenses": {"Housing": 1350, "Groceries": 480}, "note": ""}
```

Category names are free text in the person's language. Keep them stable from month to month so the
"vs average" comparison works.

## What the page computes

- Net worth = sum of all non-debt groups − debts.
- Period change (1M, YTD, 1Y, 5Y, All): from the last snapshot on or before the period start to the latest.
- Investment gains = change in the `invested` group − contributions in the period. Return ≈ modified Dietz
  (gains ÷ starting value plus time-weighted contributions).
- Saving and other = net worth change − investment gains (saving, debt repayment, property, pension,
  depreciation).
- Real view: every value restated in money of the latest snapshot date, using the index or the flat rate.
- Savings rate = (income − expenses) ÷ income, averaged over the last 12 budget months.
