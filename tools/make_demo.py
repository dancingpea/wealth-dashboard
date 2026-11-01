#!/usr/bin/env python3
"""Build the invented demo household used for the README, the live demo and the demo dashboard.

Writes plugin/skills/wealth-dashboard/assets/demo-state.json. Every person, account and number is made up.
"""
import datetime as dt
import json
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(ROOT, "plugin", "skills", "wealth-dashboard")
sys.path.insert(0, os.path.join(SKILL, "scripts"))
import wealth as W  # noqa: E402

rng = random.Random(11)
END = (2026, 10)


def month_ends(start, end):
    y, m = start
    while (y, m) <= end:
        nxt = dt.date(y + (m == 12), m % 12 + 1, 1)
        yield nxt - dt.timedelta(days=1)
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


dates = list(month_ends((2021, 4), END))
n = len(dates)


def path(mu, sigma, drift_start=1.0):
    v, out = drift_start, []
    for _ in range(n):
        v *= 1 + rng.gauss(mu, sigma)
        out.append(v)
    return out


eq = path(0.0085, 0.036)        # global equities
us = path(0.0100, 0.042)        # US large caps
semi = path(0.0110, 0.075)      # a chip maker
bond = path(0.0012, 0.012)
btc = path(0.015, 0.15)
gold = path(0.010, 0.030)
house = [1.0]
for _ in range(n - 1):
    house.append(house[-1] * (1 + rng.gauss(0.0035, 0.004)))

data = W.new_state("EUR", "Wealth dashboard", "en-GB")
s = data["settings"]
s.update({
    "people": [{"id": "sam", "name": "Sam", "birth_date": "1989-05-12", "gross_income": 74000},
               {"id": "robin", "name": "Robin", "birth_date": "1991-09-03", "gross_income": 52000}],
    "children_under_14": 1, "children_14_plus": 0, "joint_split": {"sam": 0.5, "robin": 0.5},
    "compare_countries": ["NL", "DE", "FR", "US"], "fx": {"EUR": 1.0, "USD": 0.862},
    "projection": {"years": 30, "return_low": 0.03, "return_mid": 0.06, "return_high": 0.09, "inflation": 0.02, "monthly_saving": None},
    "checkin_day": 3, "demo": True,
    "notes": ["Apartment: your own estimate, updated once a year from recent sales nearby",
              "Gold coins: valued at the dealer's buyback price, a little under the market price"],
})

MORTGAGE = {"type": "annuity", "principal": 245000, "annual_rate": 0.031, "years": 30, "start": "2022-10-01"}
STUDENT = {"type": "linear", "principal": 21000, "annual_rate": 0.005, "years": 15, "start": "2019-01-01"}
CAR = {"type": "depreciation", "purchase_price": 26500, "purchase_date": "2022-04-20", "annual_rate": 0.14}
data["accounts"] = [
    {"id": "sam-broker", "name": "Sam's brokerage", "owner": "sam", "group": "invested", "method": "holdings", "institution": "Lumen Broker",
     "class": "equity", "category": "Shares and equity funds", "source": "prices looked up each month", "cash": 0},
    {"id": "robin-fund", "name": "Robin's index fund", "owner": "robin", "group": "invested", "method": "holdings", "institution": "Harbor Invest",
     "class": "equity", "category": "Shares and equity funds", "source": "fund price looked up each month"},
    {"id": "bitcoin", "name": "Bitcoin wallet", "owner": "sam", "group": "invested", "method": "holdings", "class": "crypto", "category": "Crypto",
     "source": "public address balance and BTC price"},
    {"id": "gold", "name": "Gold coins", "owner": "joint", "group": "invested", "method": "holdings", "class": "gold", "category": "Precious metals",
     "source": "dealer buyback price"},
    {"id": "sam-pension", "name": "Sam's workplace pension", "owner": "sam", "group": "retirement", "method": "ask", "institution": "Northpoint Pensions",
     "monthly_contribution": 650, "source": "pension portal, each quarter",
     "regions": {"United States": 0.66, "Europe": 0.17, "Japan": 0.06, "Other developed": 0.07, "Emerging markets": 0.04}},
    {"id": "robin-pension", "name": "Robin's pension", "owner": "robin", "group": "retirement", "method": "ask", "institution": "Civic Pension Fund",
     "monthly_contribution": 430, "source": "yearly statement"},
    {"id": "current", "name": "Joint current account", "owner": "joint", "group": "cash", "method": "statement", "institution": "Northbank", "source": "monthly export"},
    {"id": "savings", "name": "Joint savings", "owner": "joint", "group": "cash", "method": "ask", "institution": "Northbank"},
    {"id": "robin-savings", "name": "Robin's savings", "owner": "robin", "group": "cash", "method": "ask", "institution": "Pebble Bank"},
    {"id": "apartment", "name": "Apartment", "owner": "joint", "group": "property", "method": "ask", "source": "your estimate, yearly"},
    {"id": "car", "name": "Car", "owner": "joint", "group": "other", "method": "formula", "class": "vehicle", "formula": CAR},
    {"id": "mortgage", "name": "Mortgage", "owner": "joint", "group": "debt", "method": "formula", "institution": "Northbank", "class": "mortgage",
     "category": "Mortgage", "formula": MORTGAGE},
    {"id": "student-loan", "name": "Robin's student loan", "owner": "robin", "group": "debt", "method": "formula", "category": "Student loan", "formula": STUDENT},
]

# ---- simulate account values -------------------------------------------------
snaps = []
broker = 13000.0
fund = 4000.0
pen_s, pen_r = 11000.0, 7000.0
cur_acc, sav, rsav = 3800.0, 16000.0, 4200.0
btc_qty, gold_oz = 0.27, 6.0
for i, d in enumerate(dates):
    ym = "%04d-%02d" % (d.year, d.month)
    contrib = {}
    if i:
        r_mix = 0.6 * (eq[i] / eq[i - 1]) + 0.25 * (us[i] / us[i - 1]) + 0.08 * (semi[i] / semi[i - 1]) + 0.07 * (bond[i] / bond[i - 1]) - 1
        add_b = (700 if d.year < 2024 else 950) + (2500 if d.month == 12 else 0)
        broker = broker * (1 + r_mix) + add_b
        add_f = 300 if d.year < 2025 else 400
        fund = fund * (eq[i] / eq[i - 1]) + add_f
        contrib = {"sam-broker": float(add_b), "robin-fund": float(add_f)}
        pen_s = pen_s * (1 + (eq[i] / eq[i - 1] - 1) * 0.8) + 650
        pen_r = pen_r * (1 + (eq[i] / eq[i - 1] - 1) * 0.5 + 0.001) + 430
        cur_acc = max(1800.0, cur_acc + rng.gauss(40, 700))
        if d < dt.date(2022, 9, 1):
            sav += 900 + rng.gauss(0, 150)
        elif d < dt.date(2022, 10, 1):
            sav = 6000.0  # deposit for the apartment
        else:
            sav += 320 + rng.gauss(0, 140)
        rsav += 120 + rng.gauss(0, 60)
        if ym == "2024-03":
            rsav += 15000
        if ym == "2023-02":
            gold_oz = 10.0
            contrib["gold"] = 4 * 1650 * gold[i]
    vals = {"sam-broker": broker, "robin-fund": fund, "bitcoin": btc_qty * 48000 * btc[i], "gold": gold_oz * 1580 * gold[i],
            "sam-pension": pen_s, "robin-pension": pen_r, "current": cur_acc, "savings": sav, "robin-savings": rsav,
            "student-loan": W.formula_value(STUDENT, d)}
    if d >= dt.date(2022, 4, 30):
        vals["car"] = W.formula_value(CAR, d)
    if d >= dt.date(2022, 9, 30):
        vals["apartment"] = round(298000 * house[i] / house[17] / 1000) * 1000
        vals["mortgage"] = W.formula_value(MORTGAGE, d)
    snap = {"date": d.isoformat(), "values": {k: round(v, 2) for k, v in vals.items()}}
    if contrib:
        snap["contributions"] = {k: round(v, 2) for k, v in contrib.items()}
    if ym == "2024-03":
        snap["gifts"] = {"robin": 15000}
        snap["note"] = "Robin's inheritance"
    if ym == "2022-09":
        snap["note"] = "Bought the apartment"
    snaps.append(snap)
# pensions only update each quarter: carry the last two months
for sn in snaps[-2:]:
    sn["values"]["sam-pension"] = snaps[-3]["values"]["sam-pension"]
    sn["carried"] = ["sam-pension"]
data["snapshots"] = snaps
last = snaps[-1]["values"]

# ---- positions consistent with the last snapshot --------------------------------
REG_ALLWORLD = {"United States": 0.63, "Europe": 0.15, "Japan": 0.06, "Other developed": 0.06, "Emerging markets": 0.10}
REG_WORLD = {"United States": 0.71, "Europe": 0.16, "Japan": 0.06, "Other developed": 0.07}
REG_US = {"United States": 1.0}
REG_EU = {"Europe": 1.0}
paths = {"vwce": eq, "cspx": us, "msft": us, "asml": semi, "ibgs": bond, "iwda": eq, "btc": btc, "gold": gold}
spec = [  # id, account, name, ticker, isin, class, weight in account, currency, fx, end price, gain multiple, regions
    ("vwce", "sam-broker", "FTSE All-World ETF", "VWCE", "IE00BK5BQT80", "equity", 0.52, "EUR", 1.0, 142.10, 1.36, REG_ALLWORLD),
    ("cspx", "sam-broker", "S&P 500 ETF", "CSPX", "IE00B5BMR087", "equity", 0.22, "EUR", 1.0, 655.40, 1.49, REG_US),
    ("msft", "sam-broker", "Microsoft", "MSFT", "US5949181045", "equity", 0.08, "USD", 0.862, 515.80, 1.58, REG_US),
    ("asml", "sam-broker", "ASML Holding", "ASML", "NL0010273215", "equity", 0.10, "EUR", 1.0, 748.20, 0.93, REG_EU),
    ("ibgs", "sam-broker", "Euro Government Bond ETF", "IBGS", "IE00B14X4Q57", "bonds", 0.08, "EUR", 1.0, 147.95, 0.97, REG_EU),
    ("iwda", "robin-fund", "MSCI World ETF", "IWDA", "IE00B4L5Y983", "equity", 1.0, "EUR", 1.0, 112.30, 1.24, REG_WORLD),
]
holdings, prices = [], []
end_date = dates[-1].isoformat()
for hid, acc, name, tic, isin, cls, w, cur, fx, p_end, mult, reg in spec:
    value = last[acc] * w
    qty = round(value / (p_end * fx), 4)
    holdings.append({"id": hid, "account": acc, "name": name, "ticker": tic, "isin": isin, "class": cls, "quantity": qty, "price": p_end,
                     "currency": cur, **({"fx": fx} if cur != "EUR" else {}), "cost": round(qty * p_end * fx / mult, 2), "price_date": end_date,
                     "price_source": "exchange close", "regions": reg})
data["accounts"][0]["cash"] = 0
hv = sum(W.holding_value(h, "EUR") for h in holdings if h["account"] == "sam-broker")
data["accounts"][0]["cash"] = round(max(0.0, last["sam-broker"] - hv), 2)
btc_price = round(last["bitcoin"] / btc_qty, 2)
gold_price = round(last["gold"] / gold_oz, 2)
holdings.append({"id": "btc", "account": "bitcoin", "name": "Bitcoin", "ticker": "BTC", "class": "crypto", "quantity": btc_qty, "unit": "BTC",
                 "price": btc_price, "currency": "EUR", "cost": 12400.0, "price_date": end_date, "price_source": "exchange price",
                 "address": "bc1q-demo-address-not-real"})
holdings.append({"id": "gold-coins", "account": "gold", "name": "Gold coins (1 oz)", "ticker": "XAU", "class": "gold", "quantity": gold_oz, "unit": "oz",
                 "price": gold_price, "currency": "EUR", "cost": 16900.0, "price_date": end_date, "price_source": "dealer buyback price"})
data["holdings"] = holdings
for h in holdings:
    pth = paths.get(h["id"], paths.get(h["id"].split("-")[0]))
    if h["id"] == "gold-coins":
        pth = gold
    for i in range(n - 30, n):
        prices.append({"holding": h["id"], "date": dates[i].isoformat(), "price": round(h["price"] * pth[i] / pth[-1], 2)})
data["prices"] = sorted(prices, key=lambda p: (p["holding"], p["date"]))

# ---- budget: last 24 months -------------------------------------------------------
sched = {r["month"]: r for r in W.loan_schedule(MORTGAGE)}
st_sched = {r["month"]: r for r in W.loan_schedule(STUDENT)}
months = []
for d in dates[-24:]:
    ym = "%04d-%02d" % (d.year, d.month)
    raise_ = 1.04 if d.year >= 2026 else 1.0
    inc = {"Sam's salary": round(3480 * raise_), "Robin's salary": round(2520 * raise_), "Child benefit": 290}
    if d.month == 12:
        inc["Bonus"] = 3200
    if d.month == 5:
        inc["Holiday allowance"] = 3900
    if rng.random() < 0.2:
        inc["Refunds and other"] = round(rng.uniform(60, 420))
    exp = {
        "Mortgage payment": round(sched[ym]["payment"], 2),
        "Student loan": round(st_sched[ym]["payment"], 2),
        "Utilities": round(rng.uniform(210, 290)),
        "Groceries": round(rng.uniform(640, 820)),
        "Insurance": 265,
        "Childcare": 980,
        "Transport": round(rng.uniform(190, 330)),
        "Phone and internet": 92,
        "Eating out": round(rng.uniform(220, 560)),
        "Shopping": round(rng.uniform(220, 720)),
        "Subscriptions": 58,
        "Sports and hobbies": round(rng.uniform(60, 180)),
        "Transfer to savings": 400,
    }
    if d.month in (7, 8):
        exp["Travel"] = round(rng.uniform(1100, 2200))
    elif rng.random() < 0.25:
        exp["Travel"] = round(rng.uniform(150, 500))
    if d.month == 12:
        exp["Gifts"] = round(rng.uniform(300, 560))
    months.append({"month": ym, "income": inc, "expenses": exp})
data["budget"] = {"months": months}
data["budget_map"] = {"Mortgage payment": "Loan", "Student loan": "Loan", "Utilities": "Needs", "Groceries": "Needs", "Insurance": "Needs",
                      "Childcare": "Needs", "Transport": "Needs", "Phone and internet": "Needs", "Eating out": "Wants", "Shopping": "Wants",
                      "Subscriptions": "Wants", "Sports and hobbies": "Wants", "Travel": "Wants", "Gifts": "Wants", "Transfer to savings": "Saving"}

data["goals"] = W.default_goals() + [
    {"id": "net-worth-750k", "kind": "milestone", "label": "€750k net worth", "view": "Household", "metric": "net_worth", "unit": "amount", "target": 750000,
     "from": "", "deadline": "2031-12-31", "note": ""},
    {"id": "one-million", "kind": "milestone", "label": "€1m of assets", "view": "Household", "metric": "total_assets", "unit": "amount", "target": 1000000,
     "from": "", "deadline": "", "note": ""},
    {"id": "robin-invested", "kind": "milestone", "label": "Robin: €200k invested", "view": "Robin", "metric": "invested", "unit": "amount", "target": 200000,
     "from": "", "deadline": "2028-12-31", "note": ""},
]

errors, warnings = W.validate(data)
assert not errors, errors
out = os.path.join(SKILL, "assets", "demo-state.json")
with open(out, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=1)
    f.write("\n")
t = W.totals(data, data["snapshots"][-1])
print("Wrote %s: %d snapshots, net worth %.0f, assets %.0f, debt %.0f, warnings %s" % (out, len(snaps), t["net"], t["assets"], t["debt"], warnings))
