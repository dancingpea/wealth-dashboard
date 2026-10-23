#!/usr/bin/env python3
"""Generate the fictional demo data used for the README screenshot and live demo.

Writes plugin/skills/wealth-dashboard/assets/demo-data.json. All people, amounts
and institutions are invented.
"""
import datetime as dt
import json
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(ROOT, "plugin", "skills", "wealth-dashboard")
sys.path.insert(0, os.path.join(SKILL, "scripts"))
import wealth  # noqa: E402

rng = random.Random(7)


def month_ends(start, end):
    y, m = start
    while (y, m) <= end:
        nxt = dt.date(y + (m == 12), m % 12 + 1, 1)
        yield nxt - dt.timedelta(days=1)
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


dates = list(month_ends((2021, 4), (2026, 9)))
n = len(dates)

data = wealth.new_data("EUR", "Wealth dashboard", "Alex (demo)", "en", "en-GB")
data["settings"].update({
    "checkin_day": 20,
    "goal": {"net_worth": 500000, "by": "2030-12-31"},
    "inflation": {"annual_rate": 0.025},
    "demo": True,
})

data["accounts"] = [
    {"id": "brokerage", "name": "Brokerage", "group": "invested", "method": "holdings", "institution": "Lumen Broker",
     "source": "prices via web search", "class": "equity", "cash": 0},
    {"id": "crypto", "name": "Bitcoin wallet", "group": "invested", "method": "holdings", "class": "crypto",
     "source": "on-chain balance + BTC/EUR price"},
    {"id": "gold", "name": "Gold coins", "group": "invested", "method": "holdings", "class": "gold",
     "source": "dealer buyback price"},
    {"id": "current", "name": "Current account", "group": "cash", "method": "statement", "institution": "Northbank",
     "class": "cash", "source": "monthly export"},
    {"id": "savings", "name": "Savings account", "group": "cash", "method": "ask", "institution": "Northbank",
     "class": "cash"},
    {"id": "pension", "name": "Workplace pension", "group": "retirement", "method": "ask", "institution": "Harbor Pensions",
     "class": "pension", "source": "pension portal, quarterly"},
    {"id": "apartment", "name": "Apartment", "group": "property", "method": "ask", "class": "property",
     "source": "yearly estimate from the land registry index"},
    {"id": "car", "name": "Car", "group": "other", "method": "formula", "class": "vehicle",
     "formula": {"type": "depreciation", "purchase_price": 27500, "purchase_date": "2022-03-15", "annual_rate": 0.14}},
    {"id": "mortgage", "name": "Mortgage", "group": "debt", "method": "formula", "institution": "Northbank",
     "formula": {"type": "annuity", "principal": 265000, "annual_rate": 0.031, "years": 30, "start": "2022-09-01"}},
]

# Market paths -------------------------------------------------------------
def path(n, mu, sigma, start):
    v, out = start, []
    for _ in range(n):
        v *= 1 + rng.gauss(mu, sigma)
        out.append(v)
    return out

eq = path(n, 0.0085, 0.038, 1.0)
btc = path(n, 0.016, 0.16, 1.0)
gld = path(n, 0.009, 0.03, 1.0)

snapshots = []
broker_val, broker_contrib_total = 18000.0, 18000.0
btc_qty = 0.31
gold_oz = 6.0
cur, sav = 4200.0, 15000.0
pension = 21000.0
for i, d in enumerate(dates):
    contrib = 0.0
    if i > 0:
        contrib = 650.0 if d.year < 2024 else 900.0
        if d.month == 12:
            contrib += 2500.0  # year-end bonus invested
        r = eq[i] / eq[i - 1] - 1
        broker_val = broker_val * (1 + r) + contrib
        broker_contrib_total += contrib
    if d >= dt.date(2023, 2, 1) and gold_oz < 10:
        gold_oz = 10.0
    btc_price = 52000 * btc[i]
    gold_price = 1650 * gld[i]
    cur = max(1500.0, cur + rng.gauss(60, 650))
    if d < dt.date(2022, 8, 31):
        sav += 700 + rng.gauss(0, 150)
    elif d < dt.date(2022, 9, 30):
        sav = 9000.0  # down payment
    else:
        sav += 260 + rng.gauss(0, 120)
    pension = pension * (1 + (eq[i] / eq[i - 1] - 1) * 0.6 if i else 1) + 420
    vals = {
        "brokerage": broker_val,
        "crypto": btc_qty * btc_price,
        "gold": gold_oz * gold_price,
        "current": cur,
        "savings": sav,
        "pension": pension,
    }
    carried = []
    if d >= dt.date(2022, 9, 1):
        yrs = (d - dt.date(2022, 9, 1)).days / 365.25
        vals["apartment"] = round(318000 * (1.045 ** yrs) / 1000) * 1000
        vals["mortgage"] = wealth.formula_value(data["accounts"][8]["formula"], d)
    if d >= dt.date(2022, 3, 31):
        vals["car"] = wealth.formula_value(data["accounts"][7]["formula"], d)
    snap = {"date": d.isoformat(), "values": {k: round(v, 2) for k, v in vals.items()}}
    if i > 0:
        snap["contributions"] = contrib
    if d.month in (1, 4, 7, 10) and i < n - 1:
        pass
    snapshots.append(snap)

snapshots[-1]["carried"] = ["pension"]
snapshots[17]["note"] = "Bought the apartment"
data["snapshots"] = snapshots

# Holdings consistent with the latest brokerage value --------------------
final = snapshots[-1]["values"]["brokerage"]
weights = [("vwce", "FTSE All-World ETF", "VWCE", "IE00BK5BQT80", "equity", 0.55, "EUR", 1.0, 1.38),
           ("cspx", "S&P 500 ETF", "CSPX", "IE00B5BMR087", "equity", 0.22, "EUR", 1.0, 1.52),
           ("msft", "Microsoft", "MSFT", "US5949181045", "equity", 0.08, "USD", 0.86, 1.61),
           ("asml", "ASML Holding", "ASML", "NL0010273215", "equity", 0.07, "EUR", 1.0, 0.94),
           ("govt", "Euro Govt Bond ETF", "IBGS", "IE00B14X4Q57", "bonds", 0.08, "EUR", 1.0, 0.97)]
prices = {"vwce": 141.62, "cspx": 652.10, "msft": 512.40, "asml": 744.80, "govt": 147.55}
cash_left = round(final * 0.0, 2)
holdings = []
for hid, name, tic, isin, cls, w, cur_, fx, gain_mult in weights:
    p = prices[hid]
    val = final * w
    qty = round(val / (p * fx), 4)
    holdings.append({"id": hid, "account": "brokerage", "name": name, "ticker": tic, "isin": isin, "class": cls,
                     "quantity": qty, "price": p, "currency": cur_, **({"fx": fx} if cur_ != "EUR" else {}),
                     "cost": round(qty * p * fx / gain_mult, 2), "price_date": "2026-09-30"})
# put rounding residue into account cash so the account total matches exactly
hv = sum(wealth.holding_value(h, "EUR") for h in holdings)
data["accounts"][0]["cash"] = max(0.0, round(final - hv, 2))
last = snapshots[-1]["values"]
btc_price = round(last["crypto"] / btc_qty, 2)
gold_price = round(last["gold"] / gold_oz, 2)
holdings.append({"id": "btc", "account": "crypto", "name": "Bitcoin", "ticker": "BTC", "class": "crypto",
                 "quantity": btc_qty, "unit": "BTC", "price": btc_price, "cost": 13950.0, "price_date": "2026-09-30",
                 "address": "bc1q-demo-address-not-real"})
holdings.append({"id": "gold-coins", "account": "gold", "name": "Gold coins (1 oz)", "ticker": "XAU", "class": "gold",
                 "quantity": gold_oz, "unit": "oz", "price": gold_price, "cost": 10350.0, "price_date": "2026-09-30",
                 "price_source": "dealer buyback price"})
last["crypto"] = round(btc_qty * btc_price, 2)
last["gold"] = round(gold_oz * gold_price, 2)
data["holdings"] = holdings

# Budget: last 14 months --------------------------------------------------
months = []
for d in dates[-14:]:
    k = "%04d-%02d" % (d.year, d.month)
    salary = 4650 if d.year < 2026 else 4890
    inc = {"Salary": salary}
    if d.month == 12:
        inc["Bonus"] = 2900
    if d.month == 5:
        inc["Holiday allowance"] = round(salary * 12 * 0.08)
    if rng.random() < 0.35:
        inc["Side income"] = round(rng.uniform(80, 420))
    exp = {
        "Housing": 1295,
        "Groceries": round(rng.uniform(430, 560)),
        "Transport": round(rng.uniform(150, 260)),
        "Utilities": round(rng.uniform(170, 230)),
        "Eating out": round(rng.uniform(120, 340)),
        "Subscriptions": 64,
        "Shopping": round(rng.uniform(90, 420)),
        "Health": round(rng.uniform(20, 160)),
    }
    if d.month in (7, 8):
        exp["Travel"] = round(rng.uniform(900, 1700))
    elif rng.random() < 0.25:
        exp["Travel"] = round(rng.uniform(150, 450))
    if d.month == 12:
        exp["Gifts"] = round(rng.uniform(250, 480))
    months.append({"month": k, "income": inc, "expenses": exp})
data["budget"] = {"months": months}

errors, warnings = wealth.validate(data)
assert not errors, errors
out = os.path.join(SKILL, "assets", "demo-data.json")
with open(out, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=1)
    f.write("\n")
t = wealth.totals(data, data["snapshots"][-1])
print("Wrote %s: %d snapshots, net worth %.0f, warnings: %s" % (out, len(snapshots), t["net"], warnings))
