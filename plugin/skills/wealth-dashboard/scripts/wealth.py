#!/usr/bin/env python3
"""wealth.py - data tool for the wealth-dashboard skill (Python 3.8+, standard library only).

All of a household's data lives in one JSON state file (wealth.json). Every command validates and saves it.
From it, `datasets` writes the files the dashboard reads, `store` writes the dashboard's documents, and
`standalone` writes a self-contained HTML page for when no Dashboard artifact is available.

Set up:    new, person, household, settings, account, holding, goal, map, note
Monthly:   prices, snapshot, budget, history, plan, summary, validate
Publish:   datasets, store, published, page, standalone
Other:     migrate (from a v1 page), show

Run any command with -h for its options.
"""

import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import os
import re
import sys

SCHEMA = "wealth-dashboard/2"
HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.normpath(os.path.join(HERE, "..", "assets"))
GROUPS = ["invested", "cash", "retirement", "property", "other", "debt"]
METHODS = ["connector", "holdings", "statement", "ask", "formula", "fixed"]
FORMULAS = ["depreciation", "annuity", "linear", "growth"]
BUCKETS = ["Needs", "Wants", "Loan", "Saving"]
GOAL_KINDS = ["budget", "milestone"]
BUDGET_METRICS = ["needs", "wants", "savings"]
MILESTONE_METRICS = ["net_worth", "invested", "total_assets", "cash", "debt", "cash_months"]
ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,47}$")
IBAN_RE = re.compile(r"\b[A-Z]{2}[0-9]{2}(?:\s?[A-Z0-9]{4}){3,7}\b")
LONGNUM_RE = re.compile(r"\d{9,}")
SEED_RE = re.compile(r"\b(?:[a-z]{3,8}\s+){11,23}[a-z]{3,8}\b")
STALE_DAYS = 35
SYMBOLS = {"EUR": "€", "USD": "$", "GBP": "£", "JPY": "¥", "CHF": "CHF ", "CAD": "C$", "AUD": "A$", "NZD": "NZ$", "SEK": "SEK ",
           "NOK": "NOK ", "DKK": "DKK ", "PLN": "zł ", "CZK": "Kč ", "HUF": "Ft ", "INR": "₹", "SGD": "S$", "HKD": "HK$"}
CATEGORY_DEFAULTS = {("invested", "equity"): "Shares and equity funds", ("invested", "bonds"): "Bonds", ("invested", "crypto"): "Crypto",
                     ("invested", "gold"): "Precious metals", ("invested", "mixed"): "Mixed funds", ("invested", "cash"): "Broker cash",
                     ("invested", None): "Investments", ("retirement", None): "Pensions", ("cash", None): "Cash",
                     ("property", None): "Property", ("other", "vehicle"): "Vehicles", ("other", None): "Other assets",
                     ("debt", "mortgage"): "Mortgage", ("debt", None): "Loans"}
DEFAULT_PARAMS = {"owner": "Household", "range": "LTM", "view": "line", "debt": "net", "bperiod": "12M", "gunit": "pct",
                  "ppen": "without", "pmetric": "total_assets", "preal": "nominal"}


class UserError(Exception):
    pass


# ----------------------------------------------------------------------------- basics

def today():
    return dt.date.today().isoformat()


def parse_date(s, what="date"):
    s = str(s).strip()
    if re.match(r"^\d{4}$", s):
        s += "-07-01"
    elif re.match(r"^\d{4}-\d{2}$", s):
        s += "-01"
    try:
        return dt.date.fromisoformat(s[:10])
    except ValueError:
        raise UserError("Invalid %s '%s' (use YYYY-MM-DD)" % (what, s))


def month_end(ym):
    y, m = int(ym[:4]), int(ym[5:7])
    nxt = dt.date(y + (m == 12), m % 12 + 1, 1)
    return (nxt - dt.timedelta(days=1)).isoformat()


def add_months(ym, n):
    y, m = int(ym[:4]), int(ym[5:7]) - 1 + n
    return "%04d-%02d" % (y + m // 12, m % 12 + 1)


def months_between(start, end):
    n = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day < start.day:
        n -= 1
    return max(n, 0)


def years_between(start, end):
    return max((end - start).days, 0) / 365.25


def num(s, what="value"):
    if isinstance(s, (int, float)) and not isinstance(s, bool):
        v = float(s)
    else:
        t = str(s).strip().replace("_", "").replace(" ", "").replace(",", "")
        try:
            v = float(t)
        except ValueError:
            raise UserError("Invalid number for %s: '%s'" % (what, s))
    if math.isnan(v) or math.isinf(v):
        raise UserError("Invalid number for %s: '%s'" % (what, s))
    return v


def r2(v):
    return None if v is None else round(float(v), 2)


def kv(item, what):
    if "=" not in item:
        raise UserError("Expected KEY=VALUE for %s, got '%s'" % (what, item))
    k, v = item.split("=", 1)
    return k.strip(), v.strip()


def slug(s):
    s = re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-")
    return (s or "x")[:48]


def parse_fx(items):
    fx = {}
    for item in items or []:
        k, v = kv(item, "--fx")
        fx[k.upper()] = num(v, "fx rate " + k)
    return fx


def to_base(raw, base, fx, what):
    """'1234.5' -> 1234.5 ; '1200USD' -> 1200 * fx['USD'] (base per 1 USD)."""
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return float(raw)
    t = str(raw).strip().replace(" ", "").replace("_", "").replace(",", "")
    m = re.match(r"^(-?[0-9.]+)([A-Za-z]{3})?$", t)
    if not m:
        raise UserError("Invalid amount for %s: '%s' (use 1234.56 or 1234.56USD)" % (what, raw))
    v = num(m.group(1), what)
    cur = (m.group(2) or base).upper()
    if cur != base:
        if cur not in fx:
            raise UserError("Amount for %s is in %s: pass --fx %s=<%s per 1 %s>" % (what, cur, cur, base, cur))
        v *= fx[cur]
    return v


def money(v, cur=""):
    if v is None:
        return "-"
    return ("{:,.0f}".format(v) + " " + cur).strip()


def pct(v):
    return "-" if v is None else "{:+.1f}%".format(v * 100)


# ----------------------------------------------------------------------------- state

def new_state(currency="EUR", title="Wealth dashboard", locale="en-GB"):
    return {
        "schema": SCHEMA,
        "settings": {
            "title": title, "currency": currency.upper(), "locale": locale,
            "people": [], "children_under_14": 0, "children_14_plus": 0, "joint_split": {},
            "compare_countries": [], "fx": {"EUR": 1.0} if currency.upper() == "EUR" else {},
            "projection": {"years": 30, "return_low": 0.03, "return_mid": 0.06, "return_high": 0.09, "inflation": 0.02, "monthly_saving": None},
            "checkin_day": 1, "notes": [], "created": today(), "updated": today(),
        },
        "accounts": [], "holdings": [], "snapshots": [], "prices": [],
        "budget": {"months": []}, "budget_map": {}, "goals": [], "published": {},
    }


def load(path):
    if not os.path.exists(path):
        raise UserError("File not found: %s (create it with: wealth.py new %s)" % (path, path))
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if data.get("schema") != SCHEMA:
        raise UserError("%s is not a wealth-dashboard/2 state file. A v1 dashboard page converts with: wealth.py migrate <page> %s" % (path, path))
    return data


def save(path, data):
    data["settings"]["updated"] = today()
    errors, _ = validate(data)
    if errors:
        raise UserError("Not saved - the data has errors:\n  - " + "\n  - ".join(errors))
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(tmp, path)


def people(data):
    return data["settings"].get("people", [])


def person_by_id(data):
    return {p["id"]: p for p in people(data)}


def owner_name(data, owner):
    if owner in (None, "", "joint"):
        if len(people(data)) <= 1:
            return people(data)[0]["name"] if people(data) else "You"
        return "Joint"
    p = person_by_id(data).get(owner)
    return p["name"] if p else owner


def accounts_by_id(data):
    return {a["id"]: a for a in data.get("accounts", [])}


def account_holdings(data, acc_id):
    return [h for h in data.get("holdings", []) if h.get("account") == acc_id]


def holding_value(h, base):
    q, p = h.get("quantity"), h.get("price")
    if q is None or p is None:
        return None
    fx = 1.0
    if (h.get("currency") or base).upper() != base:
        fx = h.get("fx")
        if fx is None:
            return None
    return float(q) * float(p) * float(fx)


def category_of(acc):
    if acc.get("category"):
        return acc["category"]
    g, c = acc.get("group"), acc.get("class")
    if g == "debt" and (acc.get("formula") or {}).get("type") == "annuity" and "mortgage" in acc.get("name", "").lower():
        c = "mortgage"
    return CATEGORY_DEFAULTS.get((g, c)) or CATEGORY_DEFAULTS.get((g, None)) or "Other assets"


def is_open(acc, on):
    c = acc.get("closed")
    return not c or parse_date(c, "closed") > on


# ----------------------------------------------------------------------------- formulas

def formula_value(f, on):
    t = f.get("type")
    if t == "depreciation":
        start = parse_date(f["purchase_date"], "purchase_date")
        v = float(f["purchase_price"]) * (1 - float(f.get("annual_rate", 0.15))) ** years_between(start, on)
        if f.get("per_km") and f.get("km") is not None:
            v -= float(f["per_km"]) * max(float(f["km"]) - float(f.get("km_at_purchase", 0)), 0)
        return max(v, float(f.get("floor", 0)))
    if t in ("annuity", "linear"):
        sched = loan_schedule(f)
        ym = "%04d-%02d" % (on.year, on.month)
        if not sched or ym < sched[0]["month"]:
            return float(f["principal"])
        bal = float(f["principal"])
        for r in sched:
            if r["month"] <= ym:
                bal = r["balance"]
        return max(bal, 0.0)
    if t == "growth":
        start = parse_date(f["date"], "date")
        return float(f["value"]) * (1 + float(f.get("annual_rate", 0))) ** years_between(start, on)
    raise UserError("Unknown formula type '%s'" % t)


def loan_schedule(f):
    """Monthly rows {month, balance, payment, interest, principal} from the first payment month."""
    p = float(f["principal"])
    r = float(f.get("annual_rate", 0)) / 12
    n = int(round(float(f["years"]) * 12))
    start = parse_date(f["start"], "start")
    first = "%04d-%02d" % (start.year, start.month)
    rows, bal = [], p
    pmt = (p * r / (1 - (1 + r) ** -n)) if (f.get("type") == "annuity" and r > 0) else None
    for i in range(n):
        interest = bal * r
        if f.get("type") == "annuity":
            principal = (pmt - interest) if pmt is not None else p / n
            payment = pmt if pmt is not None else p / n
        else:
            principal = p / n
            payment = principal + interest
        principal = min(principal, bal)
        bal = max(bal - principal, 0.0)
        rows.append({"month": add_months(first, i), "balance": bal, "payment": payment, "interest": interest, "principal": principal})
    return rows


def computed_value(data, acc, on):
    base = data["settings"]["currency"]
    if acc.get("method") == "formula" and acc.get("formula"):
        return formula_value(acc["formula"], on)
    hs = account_holdings(data, acc["id"])
    if hs and acc.get("method") in ("holdings", "connector"):
        vals = [holding_value(h, base) for h in hs]
        missing = [h.get("id") for h, v in zip(hs, vals) if v is None]
        if missing:
            raise UserError("Holdings without price, quantity or exchange rate in '%s': %s" % (acc["id"], ", ".join(missing)))
        return sum(vals) + float(acc.get("cash", 0) or 0)
    return None


def signed(acc, v):
    return -abs(v) if acc.get("group") == "debt" else v


def totals(data, snap):
    accs = accounts_by_id(data)
    out = {g: 0.0 for g in GROUPS}
    for k, v in snap.get("values", {}).items():
        out[accs.get(k, {}).get("group", "other")] += float(v)
    out["assets"] = sum(out[g] for g in GROUPS if g != "debt")
    out["net"] = out["assets"] - out["debt"]
    return out


# ----------------------------------------------------------------------------- validation

def check_private(where, text, warnings):
    t = str(text or "")
    if IBAN_RE.search(t) or LONGNUM_RE.search(t):
        warnings.append("%s looks like it contains an account or card number: remove it" % where)
    if SEED_RE.search(t.lower()):
        warnings.append("%s looks like a wallet seed phrase: remove it and treat the wallet as compromised" % where)


def validate(data):
    errors, warnings = [], []
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        return ["Not a %s state" % SCHEMA], []
    s = data.get("settings") or {}
    base = str(s.get("currency", ""))
    if not re.match(r"^[A-Z]{3}$", base):
        errors.append("settings.currency must be a 3-letter code like EUR")
    pids, pnames = set(), set()
    for p in s.get("people", []):
        if not p.get("id") or not ID_RE.match(p["id"]):
            errors.append("person id '%s' must be lowercase letters, digits, - or _" % p.get("id"))
        if not p.get("name"):
            errors.append("person '%s' has no name" % p.get("id"))
        if p.get("name") in ("Household", "Joint", "You"):
            errors.append("person name '%s' is reserved: pick another" % p.get("name"))
        if p.get("id") in pids or p.get("name") in pnames:
            errors.append("duplicate person '%s'" % p.get("name"))
        pids.add(p.get("id"))
        pnames.add(p.get("name"))
        if p.get("birth_date"):
            try:
                parse_date(p["birth_date"])
            except UserError as e:
                errors.append(str(e))
    for k, v in (s.get("joint_split") or {}).items():
        if k not in pids:
            errors.append("joint_split names unknown person '%s'" % k)
    js = s.get("joint_split") or {}
    if js and abs(sum(float(v) for v in js.values()) - 1) > 0.01:
        warnings.append("joint_split shares add up to %.2f, not 1" % sum(float(v) for v in js.values()))
    for k in ("return_low", "return_mid", "return_high", "inflation"):
        v = (s.get("projection") or {}).get(k)
        if v is not None and not -0.5 < float(v) < 1:
            errors.append("projection.%s must be a decimal like 0.05" % k)

    ids = set()
    for a in data.get("accounts", []):
        aid = a.get("id")
        if not aid or not ID_RE.match(str(aid)):
            errors.append("account id '%s' must be lowercase letters, digits, - or _" % aid)
        if aid in ids:
            errors.append("duplicate account id '%s'" % aid)
        ids.add(aid)
        if not a.get("name"):
            errors.append("account '%s' has no name" % aid)
        if a.get("group") not in GROUPS:
            errors.append("account '%s': group must be one of %s" % (aid, ", ".join(GROUPS)))
        if a.get("method") not in METHODS:
            errors.append("account '%s': method must be one of %s" % (aid, ", ".join(METHODS)))
        if a.get("owner") not in (None, "", "joint") and a.get("owner") not in pids:
            errors.append("account '%s': owner '%s' is not a person (use a person id or joint)" % (aid, a.get("owner")))
        if a.get("method") == "formula":
            f = a.get("formula") or {}
            if f.get("type") not in FORMULAS:
                errors.append("account '%s': formula.type must be one of %s" % (aid, ", ".join(FORMULAS)))
            else:
                try:
                    formula_value(f, dt.date.today())
                except (KeyError, ValueError, TypeError, ZeroDivisionError, UserError) as e:
                    errors.append("account '%s': formula is incomplete (%s)" % (aid, e))
        for w in (a.get("regions") or {}).values():
            if not isinstance(w, (int, float)):
                errors.append("account '%s': region weights must be numbers" % aid)
        for field in ("name", "institution", "source", "note"):
            check_private("account '%s' %s" % (aid, field), a.get(field), warnings)

    hids = set()
    for h in data.get("holdings", []):
        hid = h.get("id")
        if not hid or not ID_RE.match(str(hid)):
            errors.append("holding id '%s' must be lowercase letters, digits, - or _" % hid)
        if hid in hids:
            errors.append("duplicate holding id '%s'" % hid)
        hids.add(hid)
        if h.get("account") not in ids:
            errors.append("holding '%s' points to unknown account '%s'" % (hid, h.get("account")))
        for f in ("quantity", "price", "fx", "cost"):
            if h.get(f) is not None and not isinstance(h.get(f), (int, float)):
                errors.append("holding '%s': %s must be a number" % (hid, f))
        cur = (h.get("currency") or base).upper()
        if cur != base and h.get("price") is not None and h.get("fx") is None:
            warnings.append("holding '%s' is priced in %s but has no exchange rate" % (hid, cur))
        check_private("holding '%s' note" % hid, h.get("note"), warnings)

    prev, seen = None, set()
    for sn in data.get("snapshots", []):
        d = sn.get("date")
        try:
            dd = parse_date(d)
        except UserError as e:
            errors.append(str(e))
            continue
        if d in seen:
            errors.append("duplicate snapshot date %s" % d)
        seen.add(d)
        if prev and dd < prev:
            errors.append("snapshots must be sorted by date (%s after %s)" % (d, prev))
        prev = dd
        for k, v in (sn.get("values") or {}).items():
            if k not in ids:
                warnings.append("snapshot %s has a value for unknown account '%s'" % (d, k))
            if not isinstance(v, (int, float)):
                errors.append("snapshot %s: value for '%s' must be a number" % (d, k))
        c = sn.get("contributions")
        if c is not None and not isinstance(c, (int, float, dict)):
            errors.append("snapshot %s: contributions must be a number or {account: amount}" % d)
    months = set()
    for m in (data.get("budget") or {}).get("months", []):
        k = m.get("month", "")
        if not re.match(r"^\d{4}-\d{2}$", k):
            errors.append("budget month '%s' must be YYYY-MM" % k)
        if k in months:
            errors.append("duplicate budget month %s" % k)
        months.add(k)
        for part in ("income", "expenses"):
            for c, v in (m.get(part) or {}).items():
                if not isinstance(v, (int, float)):
                    errors.append("budget %s %s '%s' must be a number" % (k, part, c))
    for c, b in (data.get("budget_map") or {}).items():
        if b not in BUCKETS:
            errors.append("budget_map '%s' must be one of %s" % (c, ", ".join(BUCKETS)))
    gids = set()
    for g in data.get("goals", []):
        if g.get("id") in gids:
            errors.append("duplicate goal id '%s'" % g.get("id"))
        gids.add(g.get("id"))
        if g.get("kind") not in GOAL_KINDS:
            errors.append("goal '%s': kind must be budget or milestone" % g.get("id"))
        elif g["kind"] == "budget" and g.get("metric") not in BUDGET_METRICS:
            errors.append("goal '%s': budget metric must be one of %s" % (g.get("id"), ", ".join(BUDGET_METRICS)))
        elif g["kind"] == "milestone" and g.get("metric") not in MILESTONE_METRICS:
            errors.append("goal '%s': milestone metric must be one of %s" % (g.get("id"), ", ".join(MILESTONE_METRICS)))
        if g.get("view") not in (None, "", "Household") and g.get("view") not in pnames:
            errors.append("goal '%s': view must be Household or a person's name" % g.get("id"))
    for n in s.get("notes", []):
        check_private("a note", n, warnings)
    return errors, warnings


# ----------------------------------------------------------------------------- set-up commands

def cmd_new(a):
    if os.path.exists(a.file) and not a.force:
        raise UserError("%s already exists (use --force to overwrite)" % a.file)
    if a.from_json:
        with open(a.from_json, encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = new_state(a.currency, a.title, a.locale)
    save(a.file, data)
    print("Created %s" % a.file)


def cmd_person(a):
    data = load(a.file)
    ps = data["settings"].setdefault("people", [])
    p = next((x for x in ps if x["id"] == a.id), None)
    if a.remove:
        if not p:
            raise UserError("No person '%s'" % a.id)
        if any(x.get("owner") == a.id for x in data["accounts"]):
            raise UserError("'%s' still owns accounts: move them first (account --owner)" % a.id)
        ps.remove(p)
        data["settings"].get("joint_split", {}).pop(a.id, None)
        save(a.file, data)
        print("Removed %s" % a.id)
        return
    created = p is None
    if created:
        if not a.name:
            raise UserError("A new person needs --name")
        p = {"id": a.id}
        ps.append(p)
    if a.name:
        old = p.get("name")
        p["name"] = a.name
        if old and old != a.name:
            for g in data.get("goals", []):
                if g.get("view") == old:
                    g["view"] = a.name
    if a.birth is not None:
        p["birth_date"] = parse_date(a.birth, "birth").isoformat() if a.birth else None
    if a.gross is not None:
        p["gross_income"] = num(a.gross, "gross") if a.gross != "" else None
    save(a.file, data)
    print("%s %s" % ("Added" if created else "Updated", p["name"]))


def cmd_household(a):
    data = load(a.file)
    s = data["settings"]
    if a.children_under_14 is not None:
        s["children_under_14"] = int(a.children_under_14)
    if a.children_14_plus is not None:
        s["children_14_plus"] = int(a.children_14_plus)
    if a.joint_split is not None:
        js = {}
        for item in a.joint_split.split(","):
            if item.strip():
                k, v = kv(item, "--joint-split")
                js[k] = num(v, k)
        s["joint_split"] = js
    save(a.file, data)
    print("Household updated")


SETTABLE = {"title": str, "currency": str, "locale": str, "checkin_day": int, "dashboard_url": str, "schedule": str,
            "compare_countries": "list", "demo": "bool", "backup": str}


def cmd_settings(a):
    data = load(a.file)
    s = data["settings"]
    for item in a.set or []:
        k, v = kv(item, "--set")
        if k.startswith("fx."):
            s.setdefault("fx", {})[k[3:].upper()] = num(v, k)
        elif k.startswith("projection."):
            key = k.split(".", 1)[1]
            if key not in ("years", "return_low", "return_mid", "return_high", "inflation", "monthly_saving"):
                raise UserError("Unknown projection setting '%s'" % key)
            s.setdefault("projection", {})[key] = None if v.lower() in ("", "none", "auto") else (int(num(v, k)) if key == "years" else num(v, k))
        elif k in SETTABLE:
            t = SETTABLE[k]
            if t == "list":
                s[k] = [x.strip().upper() for x in v.split(",") if x.strip()]
            elif t == "bool":
                s[k] = v.lower() in ("1", "true", "yes")
            elif t is int:
                s[k] = int(num(v, k))
            else:
                s[k] = v.upper() if k == "currency" else v
        else:
            raise UserError("Unknown setting '%s'" % k)
    save(a.file, data)
    print("Settings updated")


def cmd_note(a):
    data = load(a.file)
    notes = data["settings"].setdefault("notes", [])
    if a.clear:
        notes.clear()
    for t in a.add or []:
        if t not in notes:
            notes.append(t)
    for t in a.remove or []:
        if t in notes:
            notes.remove(t)
    save(a.file, data)
    print("%d notes" % len(notes))


def parse_regions(items):
    out = {}
    for item in items or []:
        k, v = kv(item, "--region")
        out[k] = num(v, "region " + k)
    tot = sum(out.values())
    if out and abs(tot - 1) > 0.02 and abs(tot - 100) < 2:
        out = {k: v / 100 for k, v in out.items()}
    return out


def cmd_account(a):
    data = load(a.file)
    accs = data.setdefault("accounts", [])
    acc = next((x for x in accs if x["id"] == a.id), None)
    if a.remove:
        if not acc:
            raise UserError("No account '%s'" % a.id)
        if any(a.id in (s.get("values") or {}) for s in data.get("snapshots", [])):
            raise UserError("'%s' has history. Close it instead: --closed YYYY-MM-DD" % a.id)
        accs.remove(acc)
        data["holdings"] = [h for h in data.get("holdings", []) if h.get("account") != a.id]
        save(a.file, data)
        print("Removed account %s" % a.id)
        return
    created = acc is None
    if created:
        acc = {"id": a.id}
        accs.append(acc)
    for field in ("name", "group", "method", "institution", "source", "note", "closed", "owner", "category"):
        v = getattr(a, field)
        if v is not None:
            if v == "":
                acc.pop(field, None)
            else:
                acc[field] = v
    if a.asset_class is not None:
        acc["class"] = a.asset_class
    if a.cash is not None:
        acc["cash"] = num(a.cash, "cash")
    if a.monthly_contribution is not None:
        acc["monthly_contribution"] = num(a.monthly_contribution, "monthly contribution")
    if a.formula is not None:
        acc["formula"] = json.loads(a.formula)
        acc.setdefault("method", "formula")
    for item in a.formula_set or []:
        k, v = kv(item, "--formula-set")
        acc.setdefault("formula", {})[k] = v if k in ("type", "start", "date", "purchase_date") else num(v, k)
    if a.region:
        acc["regions"] = parse_regions(a.region)
    acc.setdefault("method", "ask")
    if acc.get("owner") is None:
        acc["owner"] = people(data)[0]["id"] if len(people(data)) == 1 else "joint"
    save(a.file, data)
    print("%s account %s" % ("Added" if created else "Updated", a.id))


def cmd_holding(a):
    data = load(a.file)
    hs = data.setdefault("holdings", [])
    h = next((x for x in hs if x["id"] == a.id), None)
    if a.remove:
        if not h:
            raise UserError("No holding '%s'" % a.id)
        hs.remove(h)
        save(a.file, data)
        print("Removed holding %s" % a.id)
        return
    created = h is None
    if created:
        if not a.account:
            raise UserError("A new holding needs --account")
        h = {"id": a.id}
        hs.append(h)
    for field in ("account", "name", "ticker", "isin", "address", "unit", "note", "price_source"):
        v = getattr(a, field)
        if v is not None:
            if v == "":
                h.pop(field, None)
            else:
                h[field] = v
    if a.asset_class is not None:
        h["class"] = a.asset_class
    if a.currency is not None:
        h["currency"] = a.currency.upper()
    for field in ("quantity", "price", "fx", "cost"):
        v = getattr(a, field)
        if v is not None:
            if v == "":
                h.pop(field, None)
            else:
                h[field] = num(v, field)
    if a.region:
        h["regions"] = parse_regions(a.region)
    if a.price is not None and a.price != "":
        h["price_date"] = (a.date or today())
        record_price(data, h, h["price_date"])
    save(a.file, data)
    print("%s holding %s" % ("Added" if created else "Updated", a.id))


def cmd_goal(a):
    data = load(a.file)
    goals = data.setdefault("goals", [])
    if a.defaults:
        have = {g["id"] for g in goals}
        for g in default_goals():
            if g["id"] not in have:
                goals.append(g)
        save(a.file, data)
        print("Default goals added (50/30/20 budget, 3 months of spending in cash)")
        return
    if not a.id:
        raise UserError("--id is required")
    g = next((x for x in goals if x["id"] == a.id), None)
    if a.remove:
        if not g:
            raise UserError("No goal '%s'" % a.id)
        goals.remove(g)
        save(a.file, data)
        print("Removed goal %s" % a.id)
        return
    created = g is None
    if created:
        g = {"id": a.id, "view": "Household"}
        goals.append(g)
    for field in ("kind", "label", "view", "metric", "unit", "note"):
        v = getattr(a, field)
        if v is not None:
            g[field] = v
    if a.target is not None:
        g["target"] = num(a.target, "target")
    if a.start is not None:
        g["from"] = a.start[:7] if a.start else ""
    if a.deadline is not None:
        g["deadline"] = parse_date(a.deadline, "deadline").isoformat() if a.deadline else ""
    g.setdefault("label", a.id.replace("-", " ").capitalize())
    if g.get("kind") == "milestone" and not g.get("unit"):
        g["unit"] = "months" if g.get("metric") == "cash_months" else "amount"
    if g.get("kind") == "budget" and not g.get("unit"):
        g["unit"] = "pct"
    if g.get("unit") == "eur":
        g["unit"] = "amount"
    save(a.file, data)
    print("%s goal %s" % ("Added" if created else "Updated", a.id))


def default_goals():
    return [
        {"id": "needs", "kind": "budget", "label": "Needs", "view": "Household", "metric": "needs", "unit": "pct", "target": 50, "from": "", "deadline": "",
         "note": "50/30/20 rule: essentials at most half of income"},
        {"id": "wants", "kind": "budget", "label": "Wants", "view": "Household", "metric": "wants", "unit": "pct", "target": 30, "from": "", "deadline": "",
         "note": "50/30/20 rule: everything you choose to spend at most 30%"},
        {"id": "savings", "kind": "budget", "label": "Savings", "view": "Household", "metric": "savings", "unit": "pct", "target": 20, "from": "", "deadline": "",
         "note": "50/30/20 rule: keep at least 20% of income"},
        {"id": "emergency-fund", "kind": "milestone", "label": "Emergency fund", "view": "Household", "metric": "cash_months", "unit": "months", "target": 3,
         "from": "", "deadline": "", "note": "Cash covering at least 3 months of spending"},
    ]


def cmd_map(a):
    data = load(a.file)
    m = data.setdefault("budget_map", {})
    for item in a.set or []:
        k, v = kv(item, "--set")
        b = v.capitalize()
        if b not in BUCKETS:
            raise UserError("'%s' must map to one of %s" % (k, ", ".join(BUCKETS)))
        m[k] = b
    for k in a.remove or []:
        m.pop(k, None)
    save(a.file, data)
    unmapped = sorted({c for mo in data["budget"]["months"] for c in mo.get("expenses", {})} - set(m))
    print("Map has %d categories%s" % (len(m), ("; not mapped yet (count as Wants): " + ", ".join(unmapped)) if unmapped else ""))


# ----------------------------------------------------------------------------- monthly commands

def record_price(data, h, date):
    if h.get("price") is None:
        return
    hist = data.setdefault("prices", [])
    ym = str(date)[:7]
    hist[:] = [p for p in hist if not (p["holding"] == h["id"] and p["date"][:7] == ym)]
    hist.append({"holding": h["id"], "date": str(date)[:10], "price": h["price"]})
    hist.sort(key=lambda p: (p["holding"], p["date"]))


def find_holding(data, key):
    k = key.lower()
    for h in data.get("holdings", []):
        if h["id"] == key or str(h.get("ticker", "")).lower() == k:
            return h
    raise UserError("No holding with id or ticker '%s'" % key)


def cmd_prices(a):
    data = load(a.file)
    fx = parse_fx(a.fx)
    base = data["settings"]["currency"]
    d = parse_date(a.date or today()).isoformat()
    n = 0
    for item in a.set or []:
        k, v = kv(item, "--set")
        h = find_holding(data, k)
        h["price"] = num(v, "price of " + k)
        h["price_date"] = d
        if a.source:
            h["price_source"] = a.source
        n += 1
    for item in a.qty or []:
        k, v = kv(item, "--qty")
        find_holding(data, k)["quantity"] = num(v, "quantity of " + k)
        n += 1
    for h in data.get("holdings", []):
        cur = (h.get("currency") or base).upper()
        if cur != base and cur in fx:
            h["fx"] = fx[cur]
    for cur, rate in fx.items():
        data["settings"].setdefault("fx", {})[cur] = rate
    for h in data.get("holdings", []):
        if h.get("price_date") == d:
            record_price(data, h, d)
    save(a.file, data)
    print("Updated %d holding fields%s" % (n, (" and exchange rates " + ", ".join(sorted(fx))) if fx else ""))


def contributions_by_account(data, prev, snap):
    """Money moved into each account between two snapshots (positive = in)."""
    accs = accounts_by_id(data)
    out = {}
    c = snap.get("contributions")
    if isinstance(c, dict):
        for k, v in c.items():
            out[k] = out.get(k, 0.0) + float(v)
    elif isinstance(c, (int, float)) and c:
        inv = [k for k, v in snap["values"].items() if accs.get(k, {}).get("group") == "invested" and v > 0]
        tot = sum(snap["values"][k] for k in inv)
        for k in inv:
            out[k] = out.get(k, 0.0) + float(c) * (snap["values"][k] / tot if tot else 1 / len(inv))
    if prev:
        snaps = data.get("snapshots", [])
        for k, acc in accs.items():
            if not acc.get("monthly_contribution") or k in out or k not in snap["values"] or k not in prev.get("values", {}):
                continue
            if k in snap.get("carried", []):
                continue  # value not updated: the money paid in shows up when it is
            if k in prev.get("carried", []):
                real = [x for x in snaps if x["date"] < snap["date"] and k in x.get("values", {}) and k not in x.get("carried", [])]
                since = real[-1]["date"] if real else prev["date"]
            else:
                since = prev["date"]
            months = months_between(parse_date(since), parse_date(snap["date"])) or 1
            out[k] = float(acc["monthly_contribution"]) * months
    return out


def build_snapshot(data, on, explicit, history=False, keep_month=False, allow_missing=False, contrib=None, gifts=None, note=None, fx=None):
    base = data["settings"]["currency"]
    date_s = on.isoformat()
    accs = accounts_by_id(data)
    snaps = data.setdefault("snapshots", [])
    same = None if keep_month else next((s for s in snaps if s["date"][:7] == date_s[:7]), None)
    earlier = [s for s in snaps if s["date"] <= date_s and s is not same]
    prev = earlier[-1] if earlier else None
    values, carried, missing = {}, [], []
    for aid, acc in accs.items():
        if not is_open(acc, on):
            continue
        if aid in explicit:
            values[aid] = explicit[aid]
            continue
        if history:
            if acc.get("method") == "formula" and acc.get("formula"):
                values[aid] = formula_value(acc["formula"], on)
            continue
        cv = computed_value(data, acc, on)
        if cv is not None:
            values[aid] = cv
            continue
        if same and aid in same.get("values", {}):
            values[aid] = same["values"][aid]
            if aid in same.get("carried", []):
                carried.append(aid)
            continue
        if prev and aid in prev.get("values", {}):
            values[aid] = prev["values"][aid]
            if acc.get("method") != "fixed":
                carried.append(aid)
            continue
        missing.append(aid)
    if missing and not allow_missing:
        raise UserError("No value for: %s. Pass --set ID=VALUE, or --allow-missing to leave them out." % ", ".join(missing))
    snap = {"date": date_s, "values": {k: r2(v) for k, v in values.items()}}
    if carried:
        snap["carried"] = sorted(carried)
    if contrib is None and same is not None:
        contrib = same.get("contributions")
    if contrib is not None:
        snap["contributions"] = contrib
    if gifts is None and same is not None:
        gifts = same.get("gifts")
    if gifts:
        snap["gifts"] = gifts
    notes = [n for n in [(same or {}).get("note"), note] if n]
    if notes:
        snap["note"] = " | ".join(dict.fromkeys(notes))
    if same is not None:
        snaps.remove(same)
    snaps.append(snap)
    snaps.sort(key=lambda s: s["date"])
    return snap, carried, missing


def gaps(data, snap):
    snaps = data.get("snapshots", [])
    before = [x for x in snaps if x["date"] < snap["date"]]
    after = [x for x in snaps if x["date"] > snap["date"]]
    if not before or not after:
        return []
    return sorted(k for k in before[-1].get("values", {}) if k in after[0].get("values", {}) and k not in snap["values"])


def parse_contrib(items, single, base, fx):
    if single is not None:
        return r2(to_base(single, base, fx, "contributions"))
    if not items:
        return None
    out = {}
    for item in items:
        k, v = kv(item, "--contribution")
        out[k] = r2(to_base(v, base, fx, k))
    return out


def parse_gifts(data, items):
    if not items:
        return None
    pids = {p["id"] for p in people(data)}
    out = {}
    for item in items:
        k, v = kv(item, "--gift")
        if k not in pids and k != "joint":
            raise UserError("--gift owner must be a person id or joint, got '%s'" % k)
        out[k] = num(v, "gift")
    return out


def cmd_snapshot(a):
    data = load(a.file)
    base = data["settings"]["currency"]
    fx = parse_fx(a.fx)
    on = parse_date(a.date or today())
    accs = accounts_by_id(data)
    for item in a.formula or []:
        k, v = kv(item, "--formula")
        if "." not in k:
            raise UserError("--formula expects ACCOUNT.FIELD=VALUE, e.g. car.km=84200")
        aid, field = k.split(".", 1)
        if aid not in accs:
            raise UserError("Unknown account '%s'" % aid)
        accs[aid].setdefault("formula", {})[field] = num(v, k)
    explicit = {}
    for item in a.set or []:
        k, v = kv(item, "--set")
        if k not in accs:
            raise UserError("Unknown account '%s' (add it first with the account command)" % k)
        explicit[k] = abs(to_base(v, base, fx, k)) if accs[k].get("group") == "debt" else to_base(v, base, fx, k)
    contrib = parse_contrib(a.contribution, a.contributions, base, fx)
    snap, carried, missing = build_snapshot(data, on, explicit, history=a.history, keep_month=a.keep_month,
                                            allow_missing=a.allow_missing or a.history, contrib=contrib,
                                            gifts=parse_gifts(data, a.gift), note=a.note, fx=fx)
    for k in fx:
        data["settings"].setdefault("fx", {})[k] = fx[k]
    save(a.file, data)
    t = totals(data, snap)
    print("Snapshot %s saved: net worth %s %s" % (snap["date"], money(t["net"]), base))
    if carried:
        print("Kept from an earlier month (shown as estimated): " + ", ".join(sorted(carried)))
    if missing:
        print("Left out (no value): " + ", ".join(missing))
    g = gaps(data, snap)
    if g:
        print("WARNING: missing on this date, so counted as 0: %s. Add them with --set." % ", ".join(g))


def cmd_history(a):
    """CSV columns: date, then one column per account id; optional contributions, gifts_<person>, note."""
    data = load(a.file)
    base = data["settings"]["currency"]
    fx = parse_fx(a.fx)
    accs = accounts_by_id(data)
    with open(a.csv, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows or "date" not in rows[0]:
        raise UserError("The CSV needs a 'date' column (YYYY-MM-DD) and at least one row")
    unknown = [c for c in rows[0] if c not in accs and c not in ("date", "contributions", "note") and not c.startswith("gift_")]
    if unknown:
        raise UserError("Unknown columns in CSV header: %s (use account ids)" % ", ".join(unknown))
    for row in rows:
        on = parse_date(row["date"])
        explicit = {}
        for k, v in row.items():
            if k in accs and v not in (None, ""):
                x = to_base(v, base, fx, k)
                explicit[k] = abs(x) if accs[k].get("group") == "debt" else x
        gifts = {k[5:]: num(v, k) for k, v in row.items() if k.startswith("gift_") and v not in (None, "")} or None
        c = row.get("contributions") or None
        build_snapshot(data, on, explicit, history=True, allow_missing=True, contrib=r2(num(c)) if c else None, gifts=gifts, note=row.get("note") or None)
    save(a.file, data)
    print("Imported %d past snapshots (%s to %s)" % (len(rows), rows[0]["date"], rows[-1]["date"]))
    for sn in data["snapshots"]:
        g = gaps(data, sn)
        if g:
            print("WARNING %s: missing, so counted as 0: %s" % (sn["date"], ", ".join(g)))


def cmd_budget(a):
    data = load(a.file)
    if not re.match(r"^\d{4}-\d{2}$", a.month):
        raise UserError("--month must be YYYY-MM")
    base = data["settings"]["currency"]
    fx = parse_fx(a.fx)
    months = data.setdefault("budget", {}).setdefault("months", [])
    m = next((x for x in months if x["month"] == a.month), None)
    if m is None or a.replace:
        if m is not None:
            months.remove(m)
        m = {"month": a.month, "income": {}, "expenses": {}}
        months.append(m)
    if a.json:
        with open(a.json, encoding="utf-8") as f:
            src = json.load(f)
        for part in ("income", "expenses"):
            for c, v in (src.get(part) or {}).items():
                m.setdefault(part, {})[c] = r2(to_base(v, base, fx, c))
    for item in a.income or []:
        c, v = kv(item, "--income")
        m.setdefault("income", {})[c] = r2(to_base(v, base, fx, c))
    for item in a.expense or []:
        c, v = kv(item, "--expense")
        m.setdefault("expenses", {})[c] = r2(to_base(v, base, fx, c))
    if a.note:
        m["note"] = a.note
    months.sort(key=lambda x: x["month"])
    save(a.file, data)
    cf = cashflow_rows(data)
    row = next(r for r in cf if r["month"] == a.month)
    unmapped = sorted(set(m.get("expenses", {})) - set(data.get("budget_map", {})))
    print("Budget %s: income %s, spending %s, kept %s (%s)" % (a.month, money(row["revenues"]), money(row["spending"] - row["loan_principal"]),
                                                              money(row["savings_adjusted"]), "-" if not row["revenues"] else "{:.0%}".format(row["savings_adjusted"] / row["revenues"])))
    if unmapped:
        print("Not in the needs/wants map yet (count as Wants until mapped): " + ", ".join(unmapped))


# ----------------------------------------------------------------------------- derived rows

def scheduled_debts(data):
    return [a for a in data["accounts"] if a.get("group") == "debt" and a.get("method") == "formula"
            and (a.get("formula") or {}).get("type") in ("annuity", "linear")]


def loan_rows(data):
    agg = {}
    for acc in scheduled_debts(data):
        for r in loan_schedule(acc["formula"]):
            o = agg.setdefault(r["month"], {"month": r["month"], "balance": 0.0, "payment": 0.0, "interest": 0.0, "principal": 0.0, "insurance": 0.0})
            for k in ("balance", "payment", "interest", "principal"):
                o[k] += r[k]
    rows = [agg[k] for k in sorted(agg)]
    for r in rows:
        for k in ("balance", "payment", "interest", "principal", "insurance"):
            r[k] = round(r[k], 2)
    return rows


def cashflow_rows(data):
    bm = data.get("budget_map", {})
    principal = {r["month"]: r["principal"] for r in loan_rows(data)}
    out = []
    for m in data["budget"]["months"]:
        inc = sum(float(v) for v in m.get("income", {}).values())
        spend = loan_pay = 0.0
        for c, v in m.get("expenses", {}).items():
            b = bm.get(c, "Wants")
            if b == "Saving":
                continue
            spend += float(v)
            if b == "Loan":
                loan_pay += float(v)
        lp = min(loan_pay, principal.get(m["month"], 0.0)) if loan_pay else 0.0
        out.append({"month": m["month"], "period_end": month_end(m["month"]), "revenues": r2(inc), "salary": r2(inc), "exceptional": 0.0,
                    "spending": r2(spend), "other_spending": 0.0, "loan_payment": r2(loan_pay), "loan_principal": r2(lp),
                    "savings_adjusted": r2(inc - spend + lp), "savings_rate": round((inc - spend + lp) / inc, 4) if inc else None})
    return out


def spending_rows(data):
    bm = data.get("budget_map", {})
    out = []
    for m in data["budget"]["months"]:
        for c, v in m.get("expenses", {}).items():
            b = bm.get(c, "Wants")
            if b == "Saving":
                continue
            out.append({"month": m["month"], "kind": b, "category": c, "amount": r2(v)})
    return out


def attribution_rows(data):
    accs = accounts_by_id(data)
    snaps = data["snapshots"]
    owners = sorted({owner_name(data, a.get("owner")) for a in accs.values()})
    out = []
    for i, cur in enumerate(snaps):
        ym = cur["date"][:7]
        if i == 0:
            for o in owners:
                out.append({"month": ym, "owner": o, "change": 0.0, "markets": 0.0, "gifts": 0.0, "saved": 0.0})
            continue
        prev = snaps[i - 1]
        flows = contributions_by_account(data, prev, cur)
        gifts = cur.get("gifts") or {}
        by = {o: {"change": 0.0, "markets": 0.0, "gifts": 0.0} for o in owners}
        for aid in set(cur["values"]) | set(prev.get("values", {})):
            acc = accs.get(aid)
            if not acc:
                continue
            o = owner_name(data, acc.get("owner"))
            now = signed(acc, cur["values"].get(aid, 0.0))
            was = signed(acc, prev.get("values", {}).get(aid, 0.0))
            dv = now - was
            by[o]["change"] += dv
            if acc.get("group") in ("cash", "debt"):
                continue
            if aid not in prev.get("values", {}) or aid not in cur["values"]:
                continue  # opened or closed: money moved, not a market move
            by[o]["markets"] += dv - flows.get(aid, 0.0)
        for k, v in gifts.items():
            o = owner_name(data, k)
            if o in by:
                by[o]["gifts"] += float(v)
        for o, x in by.items():
            out.append({"month": ym, "owner": o, "change": r2(x["change"]), "markets": r2(x["markets"]), "gifts": r2(x["gifts"]),
                        "saved": r2(x["change"] - x["markets"] - x["gifts"])})
    return out


def updates_via(acc):
    m = acc.get("method")
    src = acc.get("source")
    base = {"connector": "Connector", "holdings": "Prices", "statement": "Statement", "ask": "Your number", "formula": "Formula", "fixed": "Fixed"}.get(m, m)
    return base + (" · " + src if src else "")


def snapshot_rows(data):
    accs = accounts_by_id(data)
    out = []
    for sn in data["snapshots"]:
        carried = set(sn.get("carried", []))
        for aid, v in sn["values"].items():
            acc = accs.get(aid)
            if not acc:
                continue
            g = acc.get("group")
            out.append({"date": sn["date"], "owner": owner_name(data, acc.get("owner")),
                        "group": "Debt" if g == "debt" else "Invested" if g in ("invested", "retirement") else "Other",
                        "kind": g, "category": category_of(acc), "item": acc["name"], "platform": acc.get("institution", ""),
                        "value": r2(signed(acc, v)), "updates_via": updates_via(acc), "estimated": aid in carried})
    return out


def holding_rows(data):
    base = data["settings"]["currency"]
    accs = accounts_by_id(data)
    out = []
    for h in data.get("holdings", []):
        acc = accs.get(h["account"], {})
        v = holding_value(h, base)
        if v is None:
            continue
        out.append({"id": h["id"], "account": acc.get("name", h["account"]), "owner": owner_name(data, acc.get("owner")),
                    "name": h.get("name") or h.get("ticker") or h["id"], "ticker": h.get("ticker", ""), "class": h.get("class") or acc.get("class") or "other",
                    "quantity": h.get("quantity"), "unit": h.get("unit", ""), "price": h.get("price"), "currency": (h.get("currency") or base).upper(),
                    "fx": h.get("fx") if (h.get("currency") or base).upper() != base else 1, "value": r2(v), "cost": r2(h.get("cost")),
                    "price_date": h.get("price_date", ""), "price_source": h.get("price_source", ""), "is_cash": False})
    for acc in data["accounts"]:
        if abs(float(acc.get("cash") or 0)) >= 1 and account_holdings(data, acc["id"]):
            out.append({"id": acc["id"] + "-cash", "account": acc["name"], "owner": owner_name(data, acc.get("owner")), "name": "Cash in " + acc["name"],
                        "ticker": "", "class": "cash", "quantity": None, "unit": "", "price": None, "currency": base, "fx": 1,
                        "value": r2(acc["cash"]), "cost": r2(acc["cash"]), "price_date": "", "price_source": "", "is_cash": True})
    return out


def region_rows(data):
    base = data["settings"]["currency"]
    out = []
    for acc in data["accounts"]:
        w = dict(acc.get("regions") or {})
        if not w:
            hs = account_holdings(data, acc["id"])
            tot = 0.0
            for h in hs:
                v = holding_value(h, base) or 0.0
                if h.get("regions"):
                    for reg, f in h["regions"].items():
                        w[reg] = w.get(reg, 0.0) + v * f
                    tot += v
            if tot:
                total_v = sum((holding_value(h, base) or 0.0) for h in hs) + float(acc.get("cash", 0) or 0)
                w = {k: v / total_v for k, v in w.items()}
        for reg, f in w.items():
            out.append({"item": acc["name"], "region": reg, "weight": round(float(f), 4)})
    return out


def settings_rows(data):
    s = data["settings"]
    base = s["currency"]
    rows = [{"section": "meta", "key": "title", "value": s.get("title", "Wealth dashboard")},
            {"section": "meta", "key": "currency", "value": base},
            {"section": "meta", "key": "symbol", "value": SYMBOLS.get(base, base + " ")},
            {"section": "meta", "key": "locale", "value": s.get("locale", "en-GB")},
            {"section": "meta", "key": "updated", "value": s.get("updated", today())}]
    for p in people(data):
        rows.append({"section": "person", "key": p["name"], "value": None, "birth_date": p.get("birth_date"), "gross_income": p.get("gross_income")})
    js = s.get("joint_split") or {}
    pmap = person_by_id(data)
    for pid, v in js.items():
        if pid in pmap:
            rows.append({"section": "joint_share", "key": pmap[pid]["name"], "value": float(v)})
    rows.append({"section": "household", "key": "children_under_14", "value": int(s.get("children_under_14", 0) or 0)})
    rows.append({"section": "household", "key": "children_14_plus", "value": int(s.get("children_14_plus", 0) or 0)})
    rows.append({"section": "compare", "key": "countries", "value": ",".join(s.get("compare_countries") or [])})
    fx = dict(s.get("fx") or {})
    if base == "EUR":
        fx["EUR"] = 1.0
    if base == "USD":
        fx["USD"] = 1.0
    for cur in ("EUR", "USD"):
        if fx.get(cur):
            rows.append({"section": "fx", "key": cur, "value": float(fx[cur])})
    for k, v in (s.get("projection") or {}).items():
        rows.append({"section": "projection", "key": k, "value": v})
    pen = sum(float(a.get("monthly_contribution") or 0) for a in data["accounts"] if a.get("group") == "retirement" and is_open(a, dt.date.today()))
    rows.append({"section": "pension", "key": "monthly_contribution", "value": round(pen, 2)})
    for r in rows:
        r.setdefault("birth_date", None)
        r.setdefault("gross_income", None)
        r.setdefault("note", "")
    return rows


def goal_rows(data):
    out = []
    for g in data.get("goals", []):
        out.append({"id": g["id"], "kind": g["kind"], "label": g.get("label", g["id"]), "view": g.get("view") or "Household", "metric": g["metric"],
                    "unit": "amount" if g.get("unit") == "eur" else g.get("unit", "pct"), "target": g.get("target"), "from": g.get("from", "") or "",
                    "deadline": g.get("deadline", "") or "", "note": g.get("note", "") or ""})
    return out


def budget_map_rows(data):
    cats = []
    for m in data["budget"]["months"]:
        for c in m.get("expenses", {}):
            if c not in cats:
                cats.append(c)
    for c in data.get("budget_map", {}):
        if c not in cats:
            cats.append(c)
    bm = data.get("budget_map", {})
    order = {"Needs": 0, "Wants": 1, "Loan": 2, "Saving": 3}
    rows = [{"kind": "Spending", "category": c, "bucket": bm.get(c, "Wants (not mapped)")} for c in cats]
    return sorted(rows, key=lambda r: (order.get(r["bucket"], 1), r["category"].lower()))


def next_checkin(data, ref=None):
    ref = ref or dt.date.today()
    day = max(1, min(28, int(data["settings"].get("checkin_day", 1) or 1)))
    d = dt.date(ref.year, ref.month, day)
    if d <= ref:
        d = dt.date(ref.year + (ref.month == 12), ref.month % 12 + 1, day)
    return d.isoformat()


def plan_items(data):
    on = dt.date.today()
    auto, user = [], []
    for acc in data["accounts"]:
        if not is_open(acc, on):
            continue
        m, name = acc.get("method"), acc["name"]
        hs = account_holdings(data, acc["id"])
        src = (" (" + acc["source"] + ")") if acc.get("source") else ""
        if m == "connector":
            auto.append((name, "Pulled from your connected account" + src, "connector"))
        elif m == "holdings":
            addr = [h for h in hs if h.get("address")]
            auto.append((name, "Prices looked up for %d position%s%s%s" % (len(hs), "" if len(hs) == 1 else "s",
                                                                          "; on-chain balance read" if addr else "", src), "prices"))
        elif m == "formula":
            f = acc.get("formula", {})
            if f.get("per_km"):
                user.append((name, "Odometer reading (km); the value is worked out from it", "odometer"))
            else:
                auto.append((name, "Worked out by formula (%s)" % f.get("type"), "formula"))
        elif m == "statement":
            user.append((name, "Latest statement, export or screenshot" + src, "statement"))
        elif m == "ask":
            what = {"property": "Current estimated value", "other": "Current estimated value", "debt": "Amount still owed",
                    "retirement": "Current pot value"}.get(acc.get("group"), "Current balance")
            user.append((name, what + src, "ask"))
    if data["budget"]["months"]:
        user.append(("Budget", "Last month's income and spending (bank export, screenshot or totals)", "budget"))
    if any(a.get("group") == "invested" for a in data["accounts"]):
        user.append(("Contributions", "Money you added to or took out of investment accounts since the last update", "contributions"))
    return auto, user


def checkin_rows(data):
    nxt = next_checkin(data)
    auto, user = plan_items(data)
    rows = [{"item": n, "cadence": "Monthly", "next": nxt, "how": "Automatic: " + h} for n, h, _ in auto]
    rows += [{"item": n, "cadence": "Monthly", "next": nxt, "how": "You: " + h} for n, h, _ in user]
    rows.append({"item": "How you compare", "cadence": "Yearly", "next": "", "how": "Survey tables come with the skill; updated with new versions"})
    return rows


def notes_rows(data):
    out, accs = [], accounts_by_id(data)
    for n in data["settings"].get("notes", []):
        out.append({"id": "note-%d" % len(out), "note": n})
    sym = SYMBOLS.get(data["settings"]["currency"], data["settings"]["currency"] + " ")
    for acc in data["accounts"]:
        f = acc.get("formula") or {}
        t = f.get("type")
        if acc.get("method") != "formula" or not t:
            continue
        if t == "depreciation":
            txt = "%s: bought for %s%s in %s, losing %d%% of its value a year" % (acc["name"], sym, "{:,.0f}".format(float(f["purchase_price"])),
                                                                              str(f["purchase_date"])[:7], round(float(f.get("annual_rate", 0.15)) * 100))
            if f.get("per_km"):
                txt += ", less %s%s per km driven" % (sym, f["per_km"])
        elif t == "annuity":
            txt = "%s: %s%s over %s years at %.2f%% from %s, equal monthly payments; the balance follows the schedule" % (
                acc["name"], sym, "{:,.0f}".format(float(f["principal"])), f["years"], float(f.get("annual_rate", 0)) * 100, str(f["start"])[:7])
        elif t == "linear":
            txt = "%s: %s%s repaid in equal parts over %s years from %s" % (acc["name"], sym, "{:,.0f}".format(float(f["principal"])), f["years"], str(f["start"])[:7])
        else:
            txt = "%s: %s%s on %s, growing %.1f%% a year (an assumption, not a valuation)" % (acc["name"], sym, "{:,.0f}".format(float(f["value"])),
                                                                                           str(f["date"])[:7], float(f.get("annual_rate", 0)) * 100)
        out.append({"id": "formula-" + acc["id"], "note": txt})
    for acc in data["accounts"]:
        if acc.get("monthly_contribution"):
            out.append({"id": "contrib-" + acc["id"], "note": "%s: %s%s a month paid in, counted as saving" % (acc["name"], sym, "{:,.0f}".format(float(acc["monthly_contribution"])))})
    if data["snapshots"]:
        last = data["snapshots"][-1]
        for aid in last.get("carried", []):
            acc = accs.get(aid)
            if acc:
                src = next((s["date"] for s in reversed(data["snapshots"]) if aid in s["values"] and aid not in s.get("carried", [])), None)
                out.append({"id": "carried-" + aid, "note": "%s: kept at its value from %s until you give a new one" % (acc["name"], src or "an earlier month")})
    for h in data.get("holdings", []):
        if h.get("cost") is None:
            out.append({"id": "nocost-" + h["id"], "note": "%s: purchase cost unknown, so no gain is shown for it" % (h.get("name") or h["id"])})
    bm = data.get("budget_map", {})
    if any(v == "Loan" for v in bm.values()) and not scheduled_debts(data):
        out.append({"id": "loan-noschedule", "note": "Loan payments count fully as spending: add the loan's terms to split out the principal, which is saving"})
    return out


def price_rows(data):
    return [{"holding": p["holding"], "date": p["date"], "price": p["price"]} for p in data.get("prices", [])]


def reference(name):
    with open(os.path.join(ASSETS, "reference", name), encoding="utf-8") as f:
        return json.load(f)


DATASETS = [
    ("snapshots", "Holdings by month", "Every asset and debt line on each update date, by owner, with how it updates. Built by the monthly check-in from prices, statements, your numbers and formulas."),
    ("attribution", "Saved, markets and gifts", "For each update and owner, the change in net worth split into money saved, market and value moves (investments, property, vehicles), and gifts."),
    ("cashflow", "Monthly income and spending", "Household income, spending and what was left over each budget month; loan principal counted as saving."),
    ("spending", "Spending by category", "Each budget month's spending by category, marked as needs, wants or loan payments."),
    ("loan", "Loan schedules", "Month-by-month balance, payment and interest of every loan with known terms, added together."),
    ("checkin", "What updates when", "Each item the monthly check-in updates, whether it is automatic or needs you, and when it runs next."),
    ("settings", "Settings", "Household members, joint-account split, currency, exchange rates, comparison countries, projection returns and pension contributions."),
    ("goals", "Goals", "Budget goals (needs, wants, savings) and milestones (net worth, invested, assets, cash, debt, months of cash), with optional start and deadline."),
    ("budget_map", "Needs and wants", "Which spending categories count as needs, wants, loan payments or saving."),
    ("region_weights", "Regions held", "For each account, the share of its value in each region, from the funds and shares it holds."),
    ("holdings", "Investment positions", "Each position's quantity, price, value and purchase cost, from the latest update."),
    ("price_history", "Prices at each update", "The price of each position recorded at every monthly update."),
    ("notes", "Assumptions", "How values that are not read from a statement or a price are worked out."),
    ("peers", "Survey percentiles", "Percentile thresholds of household wealth, income and earnings by country and age band, brought to recent prices. Public statistics shipped with the skill."),
    ("peers_meta", "Survey sources", "Source, year, population and notes for each comparison table."),
]


def dataset_rows(data, ds):
    return {
        "snapshots": snapshot_rows, "attribution": attribution_rows, "cashflow": cashflow_rows, "spending": spending_rows,
        "loan": loan_rows, "checkin": checkin_rows, "settings": settings_rows, "goals": goal_rows, "budget_map": budget_map_rows,
        "region_weights": region_rows, "holdings": holding_rows, "price_history": price_rows, "notes": notes_rows,
        "peers": lambda d: reference("peers.json"), "peers_meta": lambda d: reference("peers_meta.json"),
    }[ds](data)


def all_datasets(data):
    return {ds: dataset_rows(data, ds) for ds, _, _ in DATASETS}


# ----------------------------------------------------------------------------- publishing

def sha(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def cmd_datasets(a):
    data = load(a.file)
    os.makedirs(a.outdir, exist_ok=True)
    published = data.get("published", {})
    manifest, changed = {}, []
    for ds, title, desc in DATASETS:
        rows = dataset_rows(data, ds)
        path = os.path.join(a.outdir, ds + ".json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, separators=(",", ":"))
        h = sha(rows)
        manifest[ds] = {"file": path, "name": ds + ".json", "sha256": h, "rows": len(rows), "title": title}
        if published.get(ds, {}).get("sha256") != h:
            changed.append(ds)
    with open(os.path.join(a.outdir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=1)
    print("Wrote %d dataset files to %s" % (len(manifest), a.outdir))
    print("Changed since the last publish (upload these): " + (", ".join(changed) if changed else "none"))


def page_text(live=None):
    def rd(name):
        with open(os.path.join(ASSETS, "page", name), encoding="utf-8") as f:
            return f.read()
    body = rd("body.html")
    scripts = ["<script>\n" + rd("script.js") + "</script>"]
    if live == "ibkr":
        body = body.replace("<!--WD:LIVE_TAB-->", '<button class="pt-tab" role="tab" id="tab-live" data-tab="live" aria-selected="false">Live IBKR</button>')
        body = body.replace("<!--WD:LIVE_SECTION-->", rd("live-ibkr.html"))
        scripts.insert(0, "<script>\n" + rd("live-ibkr.js") + "</script>")
    else:
        body = body.replace("<!--WD:LIVE_TAB-->\n", "").replace("<!--WD:LIVE_SECTION-->\n", "")
    return "<style>\n" + rd("style.css") + "</style>\n" + body + "\n".join(scripts) + "\n"


def cmd_page(a):
    text = page_text(a.live)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump({"text": text}, f, ensure_ascii=False)
    print("Wrote %s (%d KB page%s)" % (a.out, len(text.encode("utf-8")) // 1024, ", live " + a.live if a.live else ""))


LIVE_IBKR = [
    ("ibkr_positions", "IBKR positions", "get_account_positions", "Every open position with quantity, price, value, average cost and profit, in its own currency. Reads your IBKR open positions."),
    ("ibkr_balances", "IBKR balances", "get_account_balances", "Cash, position value, net value and exchange rate per currency, plus the account total in its base currency. Reads your IBKR account balances."),
    ("ibkr_performance", "IBKR performance, 12 months", "get_pa_performance_all_periods", "Daily account value and cumulative time-weighted return over the last 12 months. Reads your IBKR performance history."),
    ("ibkr_history", "IBKR weekly prices, 6 months", "get_account_positions", "Weekly closing prices for each open position over six months, one price-history call per position. Reads your IBKR positions and market data."),
]


def cmd_store(a):
    """Write the dashboard's documents as JSON files plus batch.json, the list of writes for one ArtifactData batch."""
    data = load(a.file)
    with open(a.urls, encoding="utf-8") as f:
        urls = json.load(f)
    versions = {}
    if a.versions:
        with open(a.versions, encoding="utf-8") as f:
            versions = json.load(f)
    published = data.get("published", {})
    os.makedirs(a.outdir, exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    writes = []

    def doc(collection, doc_id, body):
        path = os.path.join(a.outdir, "%s__%s.json" % (collection.replace("/", "_"), doc_id.replace(".", "_")))
        with open(path, "w", encoding="utf-8") as f:
            json.dump(body, f, ensure_ascii=False)
        key = collection + "/" + doc_id
        w = {"op": "set", "collection": collection, "doc_id": doc_id, "file_path": os.path.abspath(path)}
        if key in versions:
            w["if_version"] = int(versions[key])
        writes.append(w)

    if not a.only_datasets:
        doc("dash", "meta", {"title": data["settings"].get("title", "Wealth dashboard")})
        doc("dash", "params", dict(DEFAULT_PARAMS))
    for ds, title, desc in DATASETS:
        url = urls.get(ds) or (None if a.only_changed else published.get(ds, {}).get("url"))
        if not url:
            if a.only_changed:
                continue
            raise UserError("No uploaded file for dataset '%s': upload it and add its url to %s" % (ds, a.urls))
        body = {"title": title, "description": desc, "source": {"kind": "file", "url": url, "name": ds + ".json", "format": "json"},
                "updated": {"at": now, "by": a.by}}
        if ds in ("peers", "peers_meta"):
            body["schedule"] = "Yearly, with new versions of the wealth-dashboard skill"
            body["staleAfterHours"] = 24 * 400
        else:
            body["schedule"] = "Monthly, by your scheduled check-in"
            body["staleAfterHours"] = 24 * 40
        doc("datasets", ds, body)
    if a.live == "ibkr" and not a.only_datasets:
        for ds, title, tool, desc in LIVE_IBKR:
            doc("datasets", ds, {"title": title, "description": desc, "source": {"kind": "query", "connector": a.connector, "tool": tool, "args": {}}})
    if not a.only_datasets:
        doc("files", "index.html", {"text": page_text(a.live)})
    with open(os.path.join(a.outdir, "batch.json"), "w", encoding="utf-8") as f:
        json.dump(writes, f, indent=1)
    print("Wrote %d documents and %s" % (len(writes), os.path.join(a.outdir, "batch.json")))
    print("Use them as the `writes` of one ArtifactData batch (file_path entries; add if_version for documents that already exist).")


def cmd_published(a):
    data = load(a.file)
    with open(a.manifest, encoding="utf-8") as f:
        manifest = json.load(f)
    with open(a.urls, encoding="utf-8") as f:
        urls = json.load(f)
    pub = data.setdefault("published", {})
    replaced = []
    for ds, url in urls.items():
        if ds not in manifest:
            continue
        old = pub.get(ds, {}).get("url")
        if old and old != url:
            replaced.append(old)
        pub[ds] = {"url": url, "sha256": manifest[ds]["sha256"], "at": today()}
    if a.dashboard_url:
        data["settings"]["dashboard_url"] = a.dashboard_url
    if a.live:
        data["settings"]["live"] = a.live
    save(a.file, data)
    print("Recorded %d published datasets" % len(urls))
    if replaced:
        print("Old files you can now delete from the dashboard's assets: " + ", ".join(replaced))


def cmd_standalone(a):
    data = load(a.file)
    sets = all_datasets(data)
    payload = {"key": slug(data["settings"].get("title", "wealth")) + "-" + hashlib.sha1(json.dumps(data["settings"].get("people", [])).encode()).hexdigest()[:6],
               "params": dict(DEFAULT_PARAMS), "datasets": sets}
    blob = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")

    def rd(*p):
        with open(os.path.join(ASSETS, *p), encoding="utf-8") as f:
            return f.read()
    title = data["settings"].get("title", "Wealth dashboard")
    esc = title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    banner = ""
    if data["settings"].get("demo"):
        banner = '<div class="wd-banner"><span>Demo: every person, account and number on this page is invented.</span></div>\n'
    head = ("<title>%s</title>\n<meta name=\"claude:viewport-fit-sides\" content=\"cover\">\n<meta name=\"robots\" content=\"noindex, nofollow\">\n"
            "<link rel=\"preconnect\" href=\"https://fonts.googleapis.com\">\n<link rel=\"preconnect\" href=\"https://fonts.gstatic.com\" crossorigin>\n"
            "<link rel=\"stylesheet\" href=\"https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=Source+Serif+4:opsz,wght@8..60,400&display=swap\">\n"
            "<style>\n%s</style>\n" % (esc, rd("standalone", "tokens.css")))
    page = page_text(None)
    body = (banner + '<div id="dash-root">\n' + page + "</div>\n"
            '<script type="application/json" id="wd-data">' + blob + "</script>\n"
            '<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js"></script>\n'
            "<script>\n" + rd("standalone", "shim.js") + "</script>\n")
    # the page's own scripts must run after the shim and d3: move them to the end
    scripts = re.findall(r"<script>\n.*?</script>", page, flags=re.S)
    for s in scripts:
        body = body.replace(s, "", 1)
    body += "\n".join(scripts) + "\n"
    if a.target == "artifact":
        out = head + body
    else:
        out = ("<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
               "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover\">\n" + head + "</head>\n<body>\n" + body + "</body>\n</html>\n")
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(out)
    print("Wrote %s (%s, %d KB)" % (a.out, a.target, len(out.encode("utf-8")) // 1024))


# ----------------------------------------------------------------------------- reports

def cmd_validate(a):
    data = load(a.file)
    errors, warnings = validate(data)
    for e in errors:
        print("ERROR   " + e)
    for w in warnings:
        print("WARNING " + w)
    if not errors and not warnings:
        print("OK - %d people, %d accounts, %d holdings, %d snapshots, %d budget months, %d goals" % (
            len(people(data)), len(data["accounts"]), len(data["holdings"]), len(data["snapshots"]), len(data["budget"]["months"]), len(data["goals"])))
    return 1 if errors else 0


def cmd_plan(a):
    data = load(a.file)
    s = data["settings"]
    last = data["snapshots"][-1]["date"] if data["snapshots"] else "none yet"
    print("UPDATE PLAN - %s (%s), last update %s, next check-in %s" % (s.get("title"), s["currency"], last, next_checkin(data)))
    if s.get("dashboard_url"):
        print("Dashboard: %s" % s["dashboard_url"])
    auto, user = plan_items(data)
    on = dt.date.today()
    stale = [h for h in data["holdings"] if not h.get("price_date") or (on - parse_date(h["price_date"])).days > 20]
    print("\nAUTOMATIC (do these first):")
    for n, h, _ in auto:
        print("  - %s: %s" % (n, h))
    if stale:
        print("  - Prices to refresh: " + ", ".join(h.get("ticker") or h["id"] for h in stale))
    fx_needed = sorted({(h.get("currency") or s["currency"]).upper() for h in data["holdings"]} - {s["currency"]})
    want = sorted(set(fx_needed) | ({"EUR", "USD"} - {s["currency"]}))
    print("  - Exchange rates (%s per 1 unit): %s" % (s["currency"], ", ".join(want) if want else "none needed"))
    print("\nNEEDS THE USER (ask in one message):")
    for n, h, _ in user:
        print("  - %s: %s" % (n, h))
    return 0


def cmd_summary(a):
    data = load(a.file)
    s = data["settings"]
    cur = s["currency"]
    snaps = data["snapshots"]
    if not snaps:
        print("No snapshots yet.")
        return 0
    last = snaps[-1]
    t = totals(data, last)
    print("%s - as of %s (%s)" % (s.get("title"), last["date"], cur))
    print("Net worth: %s (assets %s, debts %s)" % (money(t["net"]), money(t["assets"]), money(t["debt"])))
    att = attribution_rows(data)
    if len(snaps) > 1:
        p = snaps[-2]
        tp = totals(data, p)
        ch = t["net"] - tp["net"]
        rows = [r for r in att if r["month"] == last["date"][:7]]
        print("Change since %s: %s (%s): saved %s, markets %s, gifts %s" % (
            p["date"], money(ch), pct(ch / abs(tp["net"])) if tp["net"] else "-", money(sum(r["saved"] for r in rows)),
            money(sum(r["markets"] for r in rows)), money(sum(r["gifts"] for r in rows))))
    y0 = [x for x in snaps if x["date"] < last["date"][:4] + "-01-01"]
    if y0:
        ty = totals(data, y0[-1])
        print("Since 1 January: %s (%s)" % (money(t["net"] - ty["net"]), pct((t["net"] - ty["net"]) / abs(ty["net"])) if ty["net"] else "-"))
    names = {"invested": "Investments", "cash": "Cash", "retirement": "Pensions", "property": "Property", "other": "Other", "debt": "Debts"}
    print("By group: " + ", ".join("%s %s" % (names[g], money(t[g])) for g in GROUPS if t[g]))
    if len(people(data)) > 1:
        accs = accounts_by_id(data)
        js = s.get("joint_split") or {}
        for p in people(data):
            share = js.get(p["id"], 1 / len(people(data)))
            v = 0.0
            for aid, val in last["values"].items():
                acc = accs.get(aid, {})
                o = acc.get("owner")
                f = 1 if o == p["id"] else share if o in (None, "", "joint") else 0
                v += f * signed(acc, val)
            print("  %s: %s" % (p["name"], money(v)))
    if last.get("carried"):
        accs = accounts_by_id(data)
        print("Estimated (kept from an earlier month): " + ", ".join(accs.get(k, {}).get("name", k) for k in last["carried"]))
    on = parse_date(last["date"])
    stale = [h for h in data["holdings"] if not h.get("price_date") or (on - parse_date(h["price_date"])).days > STALE_DAYS]
    if stale:
        print("Prices older than %d days: %s" % (STALE_DAYS, ", ".join(h.get("ticker") or h["id"] for h in stale)))
    cf = cashflow_rows(data)
    if cf:
        r = cf[-1]
        print("Budget %s: income %s, spending %s, kept %s%s" % (r["month"], money(r["revenues"]), money(r["spending"] - r["loan_principal"]),
                                                               money(r["savings_adjusted"]), (" (%.0f%%)" % (r["savings_adjusted"] / r["revenues"] * 100)) if r["revenues"] else ""))
    unmapped = sorted({c for m in data["budget"]["months"] for c in m.get("expenses", {})} - set(data.get("budget_map", {})))
    if unmapped:
        print("Spending categories not mapped to needs/wants yet: " + ", ".join(unmapped))
    return 0


def cmd_show(a):
    data = load(a.file)
    s = data["settings"]
    print("%s · %s · %s" % (s.get("title"), s["currency"], ", ".join(p["name"] for p in people(data)) or "no people yet"))
    for acc in data["accounts"]:
        print("  %-18s %-10s %-10s %-9s %s" % (acc["id"], acc["group"], acc["method"], owner_name(data, acc.get("owner")), acc["name"]))
    for g in data["goals"]:
        print("  goal %-14s %s %s %s %s" % (g["id"], g["kind"], g["metric"], g.get("target"), g.get("deadline") or ""))
    return 0


def cmd_migrate(a):
    """Convert a v1 dashboard page (or its JSON) into a v2 state file."""
    with open(a.v1, encoding="utf-8") as f:
        text = f.read()
    if a.v1.lower().endswith(".json"):
        old = json.loads(text)
    else:
        m = re.search(r'<script type="application/json" id="wealth-data">(.*?)</script>', text, re.S)
        if not m:
            raise UserError("No v1 data found in %s" % a.v1)
        old = json.loads(m.group(1))
    s = old.get("settings", {})
    data = new_state(s.get("currency", "EUR"), s.get("title", "Wealth dashboard"), s.get("locale", "en-GB"))
    pid = slug(s.get("owner") or "me")
    data["settings"]["people"] = [{"id": pid, "name": (s.get("owner") or "Me").replace(" (demo)", "")}]
    if s.get("goal", {}).get("net_worth"):
        data["goals"].append({"id": "net-worth", "kind": "milestone", "label": "Net worth goal", "view": "Household", "metric": "net_worth",
                              "unit": "amount", "target": s["goal"]["net_worth"], "from": "", "deadline": s["goal"].get("by", ""), "note": ""})
    if s.get("inflation", {}).get("annual_rate") is not None:
        data["settings"]["projection"]["inflation"] = s["inflation"]["annual_rate"]
    for acc in old.get("accounts", []):
        acc = dict(acc)
        acc["owner"] = pid
        data["accounts"].append(acc)
    data["holdings"] = old.get("holdings", [])
    for h in data["holdings"]:
        if h.get("price") is not None and h.get("price_date"):
            record_price(data, h, h["price_date"])
    data["snapshots"] = old.get("snapshots", [])
    data["budget"] = old.get("budget", {"months": []})
    data["goals"] = default_goals() + data["goals"]
    save(a.out, data)
    print("Migrated to %s. Check people, owners and the needs/wants map next." % a.out)


# ----------------------------------------------------------------------------- cli

def main(argv=None):
    p = argparse.ArgumentParser(prog="wealth.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    x = sub.add_parser("new", help="create a state file")
    x.add_argument("file")
    x.add_argument("--currency", default="EUR")
    x.add_argument("--title", default="Wealth dashboard")
    x.add_argument("--locale", default="en-GB")
    x.add_argument("--from", dest="from_json", help="start from this state JSON")
    x.add_argument("--force", action="store_true")
    x.set_defaults(fn=cmd_new)

    x = sub.add_parser("person", help="add, update or remove a household member")
    x.add_argument("file")
    x.add_argument("--id", required=True)
    x.add_argument("--name")
    x.add_argument("--birth", help="YYYY-MM-DD or YYYY (for age-group comparisons)")
    x.add_argument("--gross", help="gross yearly income from work, in base currency")
    x.add_argument("--remove", action="store_true")
    x.set_defaults(fn=cmd_person)

    x = sub.add_parser("household", help="children and the joint-account split")
    x.add_argument("file")
    x.add_argument("--children-under-14", dest="children_under_14")
    x.add_argument("--children-14-plus", dest="children_14_plus")
    x.add_argument("--joint-split", dest="joint_split", help="PERSON=SHARE,... e.g. sam=0.6,robin=0.4 (empty: equal)")
    x.set_defaults(fn=cmd_household)

    x = sub.add_parser("settings", help="change settings")
    x.add_argument("file")
    x.add_argument("--set", action="append", metavar="KEY=VALUE",
                   help="title, currency, locale, checkin_day, dashboard_url, schedule, backup, demo, compare_countries=NL,FR,US, "
                        "fx.EUR=<base per 1 EUR>, fx.USD=<base per 1 USD>, projection.years|return_low|return_mid|return_high|inflation|monthly_saving")
    x.set_defaults(fn=cmd_settings)

    x = sub.add_parser("note", help="assumption notes shown on the dashboard")
    x.add_argument("file")
    x.add_argument("--add", action="append")
    x.add_argument("--remove", action="append")
    x.add_argument("--clear", action="store_true")
    x.set_defaults(fn=cmd_note)

    x = sub.add_parser("account", help="add or update an account")
    x.add_argument("file")
    x.add_argument("--id", required=True)
    x.add_argument("--name")
    x.add_argument("--owner", help="person id, or joint")
    x.add_argument("--group", choices=GROUPS)
    x.add_argument("--method", choices=METHODS)
    x.add_argument("--category", help="label for charts, e.g. 'Index funds' (default from group and class)")
    x.add_argument("--class", dest="asset_class", help="equity, bonds, crypto, gold, mixed, cash, vehicle, ...")
    x.add_argument("--institution")
    x.add_argument("--source", help="how to update it, in plain words or a tool call")
    x.add_argument("--note")
    x.add_argument("--cash", help="uninvested cash inside a holdings account, in base currency")
    x.add_argument("--monthly-contribution", dest="monthly_contribution", help="money paid in each month (pensions), counted as saving")
    x.add_argument("--formula", help='JSON, e.g. \'{"type":"annuity","principal":300000,"annual_rate":0.04,"years":30,"start":"2021-06-01"}\'')
    x.add_argument("--formula-set", action="append", metavar="FIELD=VALUE")
    x.add_argument("--region", action="append", metavar="REGION=WEIGHT", help="for a fund account without positions")
    x.add_argument("--closed", help="YYYY-MM-DD the account was closed (keeps history)")
    x.add_argument("--remove", action="store_true")
    x.set_defaults(fn=cmd_account)

    x = sub.add_parser("holding", help="add, update or remove a position")
    x.add_argument("file")
    x.add_argument("--id", required=True)
    x.add_argument("--account")
    x.add_argument("--name")
    x.add_argument("--ticker")
    x.add_argument("--isin")
    x.add_argument("--class", dest="asset_class")
    x.add_argument("--quantity")
    x.add_argument("--unit")
    x.add_argument("--price")
    x.add_argument("--currency")
    x.add_argument("--fx", help="base currency per 1 unit of the price currency")
    x.add_argument("--cost", help="total purchase cost in base currency")
    x.add_argument("--region", action="append", metavar="REGION=WEIGHT")
    x.add_argument("--address", help="public on-chain address")
    x.add_argument("--price-source", dest="price_source")
    x.add_argument("--date")
    x.add_argument("--note")
    x.add_argument("--remove", action="store_true")
    x.set_defaults(fn=cmd_holding)

    x = sub.add_parser("goal", help="add, update or remove a goal")
    x.add_argument("file")
    x.add_argument("--id")
    x.add_argument("--kind", choices=GOAL_KINDS)
    x.add_argument("--label")
    x.add_argument("--view", help="Household or a person's name")
    x.add_argument("--metric", choices=BUDGET_METRICS + MILESTONE_METRICS)
    x.add_argument("--unit", choices=["pct", "amount", "months"])
    x.add_argument("--target")
    x.add_argument("--from", dest="start", help="YYYY-MM: budget goal counts from this month")
    x.add_argument("--deadline", help="YYYY-MM-DD (empty to clear)")
    x.add_argument("--note")
    x.add_argument("--defaults", action="store_true", help="add the 50/30/20 budget goals and a 3-month emergency fund")
    x.add_argument("--remove", action="store_true")
    x.set_defaults(fn=cmd_goal)

    x = sub.add_parser("map", help="map spending categories to Needs, Wants, Loan or Saving")
    x.add_argument("file")
    x.add_argument("--set", action="append", metavar="CATEGORY=BUCKET")
    x.add_argument("--remove", action="append", metavar="CATEGORY")
    x.set_defaults(fn=cmd_map)

    x = sub.add_parser("prices", help="update prices / quantities / exchange rates")
    x.add_argument("file")
    x.add_argument("--set", action="append", metavar="ID_OR_TICKER=PRICE")
    x.add_argument("--qty", action="append", metavar="ID_OR_TICKER=QUANTITY")
    x.add_argument("--fx", action="append", metavar="CUR=RATE", help="base per 1 CUR, e.g. USD=0.92")
    x.add_argument("--date")
    x.add_argument("--source")
    x.set_defaults(fn=cmd_prices)

    x = sub.add_parser("snapshot", help="record this month's values")
    x.add_argument("file")
    x.add_argument("--date")
    x.add_argument("--set", action="append", metavar="ACCOUNT=VALUE")
    x.add_argument("--fx", action="append", metavar="CUR=RATE")
    x.add_argument("--formula", action="append", metavar="ACCOUNT.FIELD=VALUE", help="e.g. car.km=84200")
    x.add_argument("--contribution", action="append", metavar="ACCOUNT=AMOUNT", help="money moved into (or, negative, out of) an account since the last update")
    x.add_argument("--contributions", help="a single total moved into investment accounts (spread by value)")
    x.add_argument("--gift", action="append", metavar="PERSON=AMOUNT", help="gifts or inheritances received (person id or joint)")
    x.add_argument("--note")
    x.add_argument("--keep-month", action="store_true")
    x.add_argument("--allow-missing", action="store_true")
    x.add_argument("--history", action="store_true", help="a past date: only the values given, plus formulas")
    x.set_defaults(fn=cmd_snapshot)

    x = sub.add_parser("history", help="import past snapshots from a CSV (date + one column per account id)")
    x.add_argument("file")
    x.add_argument("csv")
    x.add_argument("--fx", action="append", metavar="CUR=RATE")
    x.set_defaults(fn=cmd_history)

    x = sub.add_parser("budget", help="record a month of income and spending")
    x.add_argument("file")
    x.add_argument("--month", required=True)
    x.add_argument("--income", action="append", metavar="CATEGORY=AMOUNT")
    x.add_argument("--expense", action="append", metavar="CATEGORY=AMOUNT")
    x.add_argument("--json", help='{"income": {...}, "expenses": {...}}')
    x.add_argument("--fx", action="append", metavar="CUR=RATE")
    x.add_argument("--note")
    x.add_argument("--replace", action="store_true")
    x.set_defaults(fn=cmd_budget)

    for name, fn, h in (("validate", cmd_validate, "check the data"), ("plan", cmd_plan, "what the next update needs"),
                        ("summary", cmd_summary, "plain-text recap of the latest update"), ("show", cmd_show, "list people, accounts and goals")):
        x = sub.add_parser(name, help=h)
        x.add_argument("file")
        x.set_defaults(fn=fn)

    x = sub.add_parser("datasets", help="write the dashboard's dataset files and a manifest")
    x.add_argument("file")
    x.add_argument("outdir")
    x.set_defaults(fn=cmd_datasets)

    x = sub.add_parser("store", help="write the dashboard's documents for one ArtifactData batch")
    x.add_argument("file")
    x.add_argument("outdir")
    x.add_argument("--urls", required=True, help='JSON {dataset: "/_blob/<id>"} of the files you uploaded')
    x.add_argument("--versions", help='JSON {"datasets/snapshots": 3, ...} of documents that already exist')
    x.add_argument("--only-changed", action="store_true", help="only datasets listed in --urls (monthly update)")
    x.add_argument("--only-datasets", action="store_true", help="leave the page, title and filters alone")
    x.add_argument("--live", choices=["ibkr"], help="add the live IBKR tab and its four live queries")
    x.add_argument("--connector", default="Interactive Brokers (IBKR)", help="the IBKR connector's name as it appears in your tools")
    x.add_argument("--by", default="Claude")
    x.set_defaults(fn=cmd_store)

    x = sub.add_parser("published", help="record what was published (hashes and file urls)")
    x.add_argument("file")
    x.add_argument("--manifest", required=True)
    x.add_argument("--urls", required=True)
    x.add_argument("--dashboard-url", dest="dashboard_url")
    x.add_argument("--live", choices=["ibkr"])
    x.set_defaults(fn=cmd_published)

    x = sub.add_parser("page", help="write the page document {text} on its own")
    x.add_argument("out")
    x.add_argument("--live", choices=["ibkr"])
    x.set_defaults(fn=cmd_page)

    x = sub.add_parser("standalone", help="write a self-contained HTML dashboard")
    x.add_argument("file")
    x.add_argument("out")
    x.add_argument("--target", choices=["file", "artifact"], default="file")
    x.set_defaults(fn=cmd_standalone)

    x = sub.add_parser("migrate", help="convert a v1 dashboard page into a v2 state file")
    x.add_argument("v1")
    x.add_argument("out")
    x.set_defaults(fn=cmd_migrate)

    a = p.parse_args(argv)
    try:
        return a.fn(a) or 0
    except UserError as e:
        print("Error: %s" % e, file=sys.stderr)
        return 2
    except json.JSONDecodeError as e:
        print("Error: invalid JSON (%s)" % e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
