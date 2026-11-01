# Data format (`wealth-dashboard/2`)

The state file `wealth.json` is one JSON object. Prefer the `W` commands; edit the JSON by hand only for bulk
changes, then run `W validate`.

```json
{
  "schema": "wealth-dashboard/2",
  "settings": { ... },
  "accounts": [ ... ],
  "holdings": [ ... ],
  "snapshots": [ ... ],
  "prices": [ ... ],
  "budget": { "months": [ ... ] },
  "budget_map": { "Groceries": "Needs", ... },
  "goals": [ ... ],
  "published": { "snapshots": {"url": "/_blob/...", "sha256": "...", "at": "YYYY-MM-DD"}, ... }
}
```

## settings

| Field | Meaning |
|---|---|
| `title` | Dashboard title. |
| `currency`, `locale` | Base currency (ISO code); every stored amount is in it. Locale is informational for now. |
| `people` | `[{id, name, birth_date, gross_income}]`. `name` shows on the page (not Household, Joint or You). Birth date `YYYY-MM-DD` (a year alone is fine). `gross_income`: yearly pay before tax, for comparisons only. |
| `children_under_14`, `children_14_plus` | For the income-per-person comparison (EU equivalence scale). |
| `joint_split` | `{person_id: share}`; how joint accounts split between people's views. Equal if empty. |
| `compare_countries` | Default countries in "How you compare", e.g. `["NL", "FR", "US"]` (ISO codes; GR for Greece). |
| `fx` | `{"EUR": x, "USD": y}`: base currency per 1 unit (1 when the base is that currency). Updated by `prices --fx`. |
| `projection` | `years`, `return_low`, `return_mid`, `return_high`, `inflation` (decimals), `monthly_saving` (null: last 12 budget months' average). |
| `checkin_day` | Day of month of the scheduled check-in. |
| `notes` | Assumption lines shown on the page. |
| `dashboard_url`, `schedule`, `live`, `demo` | Where the dashboard lives, the check-in description, `"ibkr"` if it has the live tab, demo banner. |

## accounts[]

| Field | Meaning |
|---|---|
| `id` | Stable id: lowercase letters, digits, `-`, `_`. Never reuse one. |
| `name` | What they call it (shows on the page). |
| `owner` | A person id or `joint`. |
| `group` | `invested`, `cash`, `retirement`, `property`, `other`, `debt`. |
| `method` | `connector`, `holdings`, `formula`, `fixed`, `statement`, `ask`. |
| `category` | Label in charts ("Index funds", "Student loan"). Default from group and class. |
| `class` | `equity`, `bonds`, `crypto`, `gold`, `mixed`, `cash`, `vehicle`, `mortgage`, ... |
| `institution`, `source`, `note` | Brand; how to get the value next time; free text. Never account numbers. |
| `cash` | Uninvested cash in a holdings account, base currency. |
| `monthly_contribution` | Paid in each month (pensions): counted as money moved in, so as saving. |
| `formula` | See below. |
| `regions` | `{region: weight}` for an account without positions (a pension fund). |
| `closed` | `YYYY-MM-DD`; history stays. |

Formulas (amounts in base currency, rates as decimals):

| type | fields | value at date D |
|---|---|---|
| `depreciation` | purchase_price, purchase_date, annual_rate, optional per_km, km_at_purchase, km, floor | price × (1 − rate)^years − per_km × km driven, not below floor |
| `annuity` | principal, annual_rate, years, start | balance after the equal payments made since start |
| `linear` | principal, annual_rate, years, start | principal × (1 − payments made / total payments) |
| `growth` | value, date, annual_rate | value × (1 + rate)^years since date |

## holdings[]

`id`, `account`, `name`, `ticker`, `isin`, `class`, `quantity`, `unit`, `price` (in `currency`), `currency`, `fx`
(base per 1 unit of currency), `cost` (total paid, base currency), `price_date`, `price_source`, `address` (public
on-chain), `regions`. Value = quantity × price × fx.

## snapshots[]

```json
{"date": "2026-10-31", "values": {"current": 3210.55, "broker": 41200.0, "mortgage": 241800.0},
 "contributions": {"broker": 950}, "gifts": {"robin": 15000}, "carried": ["pension"], "note": "bonus month"}
```

- One per month; sorted. Debts as positive amounts owed. An account absent on a date counts as zero then.
- `contributions`: money moved into accounts since the previous snapshot (negative = taken out); a number is spread
  over investment accounts by value. Pension `monthly_contribution` is added automatically for accounts updated that
  month.
- `gifts`: gifts and inheritances received, by person id or `joint`.
- `carried`: accounts whose value was kept from an earlier month (shown as estimated).

## prices[], budget, budget_map, goals

- `prices`: `{holding, date, price}`, one per holding per month, written by `prices` and `holding --price`.
- `budget.months`: `{month: "YYYY-MM", income: {category: amount}, expenses: {category: amount}, note}`.
- `budget_map`: expense category → `Needs`, `Wants`, `Loan` or `Saving`. Unmapped counts as Wants.
- `goals`: `{id, kind, label, view, metric, unit, target, from, deadline, note}`.
  - `kind: budget`, `metric` needs | wants | savings, `unit` pct (target = % of income) or amount (a month).
    Needs and wants are limits, savings a minimum. `from` (YYYY-MM) limits the months counted.
  - `kind: milestone`, `metric` net_worth | invested | total_assets | cash | debt (a limit) | cash_months (unit months).
  - `view`: Household or a person's name. `deadline`: `YYYY-MM-DD` or empty.

## Datasets (what `W datasets` writes)

All JSON arrays of rows. The page computes everything else from these.

| Dataset | Columns |
|---|---|
| snapshots | date, owner (name or Joint), group (Invested, Other, Debt), kind (account group), category, item, platform, value (debt negative), updates_via, estimated |
| attribution | month, owner, change, markets, gifts, saved |
| cashflow | month, period_end, revenues, salary, exceptional, spending, other_spending, loan_payment, loan_principal, savings_adjusted, savings_rate |
| spending | month, kind (Needs, Wants, Loan), category, amount |
| loan | month, balance, payment, interest, principal, insurance (all scheduled loans added together) |
| checkin | item, cadence, next, how |
| settings | section, key, value, birth_date, gross_income, note (sections: meta, person, joint_share, household, compare, fx, projection, pension) |
| goals | as above, `unit` pct, amount or months |
| budget_map | kind, category, bucket |
| region_weights | item (account name), region, weight |
| holdings | id, account, owner, name, ticker, class, quantity, unit, price, currency, fx, value, cost, price_date, price_source, is_cash |
| price_history | holding, date, price |
| notes | id, note |
| peers, peers_meta | survey percentiles and their sources (reference data shipped with the skill) |

## What the page computes

- Net worth = assets − debts, per view (Household and each person; joint lines split by `joint_split`).
- Change since 1 January, split into saved (change not explained by markets or gifts), markets (change in investments,
  pensions, property and other assets beyond money moved in) and gifts.
- Budget rule from the last 1, 3 or 12 budget months; goal status, "at this pace" date, and progress.
- Projection: invested assets grow at each return and receive the monthly saving plus pension contributions, less
  scheduled loan principal; other assets stay flat; scheduled loans follow their schedule; also in today's money.
- How you compare: percentiles by country for net worth (all households and the main earner's age group), income per
  person after tax, household gross income, each person's earnings, and the saving rate against the national average.
