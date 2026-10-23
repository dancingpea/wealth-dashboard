#!/usr/bin/env python3
"""wealth.py - data tool for the wealth-dashboard skill (Python 3.8+, stdlib only).

The dashboard HTML file IS the database: all data lives inside it in
<script type="application/json" id="wealth-data">. Every command takes the
dashboard file (.html) or a bare data file (.json) and writes changes back in
place, re-rendering the page with the current template.

Commands (run any with -h for details):
  new       create a new dashboard (empty, or --from a JSON file)
  export    write the embedded data to a JSON file (or stdout)
  import    replace the embedded data with a JSON file (validated first)
  validate  check the data and print errors / warnings
  settings  change settings (title, owner, currency, locale, language, goal...)
  account   add or update an account
  holding   add, update or remove a holding (position) inside an account
  prices    update holding prices / quantities in bulk
  snapshot  record (or update) the monthly snapshot of every account's value
  history   import past snapshots from a CSV to backfill the chart
  budget    record a month of income and expenses
  inflation set the inflation index (CPI/HICP) or a flat annual rate
  plan      print the update plan: what is automatic and what needs the user
  summary   print a plain-text summary of the latest month
  build     re-render the page with the current template (or switch target)
"""

import argparse
import datetime as dt
import json
import math
import os
import re
import sys

SCHEMA = "wealth-dashboard/1"
GROUPS = ["invested", "cash", "retirement", "property", "other", "debt"]
METHODS = ["connector", "holdings", "statement", "ask", "formula", "fixed"]
FORMULAS = ["depreciation", "annuity", "linear", "growth"]
LANGUAGES = ["en", "fr", "nl", "de", "es"]
HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.normpath(os.path.join(HERE, "..", "assets", "dashboard.html"))
DATA_RE = re.compile(
    r'(<script type="application/json" id="wealth-data">)(.*?)(</script>)', re.S
)
HEAD_MARK = "<!--wd:head-end-->"
ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,47}$")
STALE_DAYS = 35


class UserError(Exception):
    pass


# --------------------------------------------------------------------------- io

def read_any(path):
    """Return (data, kind) where kind is 'json', 'artifact' or 'file'."""
    if not os.path.exists(path):
        raise UserError("File not found: %s" % path)
    with open(path, encoding="utf-8") as f:
        text = f.read()
    if path.lower().endswith(".json"):
        return json.loads(text), "json"
    m = DATA_RE.search(text)
    if not m:
        raise UserError(
            "No embedded wealth data found in %s. Is this a wealth dashboard page?" % path
        )
    data = json.loads(m.group(2))
    kind = "file" if text.lstrip()[:15].lower().startswith("<!doctype") else "artifact"
    return data, kind


def embed_json(data):
    text = json.dumps(data, ensure_ascii=False, indent=1)
    # Make the JSON safe inside <script>: no '<', '>' or '&' can break out.
    return text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def html_escape(s):
    return (
        str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )


def render(data, kind, template=None):
    with open(template or TEMPLATE, encoding="utf-8") as f:
        tpl = f.read()
    title = data.get("settings", {}).get("title") or "Wealth dashboard"
    lang = data.get("settings", {}).get("language") or "en"
    page = tpl.replace("__WD_TITLE__", html_escape(title))
    page = DATA_RE.sub(lambda m: m.group(1) + embed_json(data) + m.group(3), page, count=1)
    if kind == "artifact":
        return page
    head, sep, body = page.partition(HEAD_MARK)
    if not sep:
        head, body = "", page
    return (
        "<!doctype html>\n<html lang=\"%s\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover\">\n"
        "<meta name=\"apple-mobile-web-app-capable\" content=\"yes\">\n"
        "<meta name=\"robots\" content=\"noindex, nofollow\">\n%s\n</head>\n<body>\n%s\n</body>\n</html>\n"
        % (html_escape(lang), head.strip(), body.strip())
    )


def write_any(path, data, kind, template=None):
    data.setdefault("settings", {})["updated"] = today()
    errors, _ = validate(data)
    if errors:
        raise UserError("Not saved - the data has errors:\n  - " + "\n  - ".join(errors))
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        if kind == "json":
            json.dump(data, f, ensure_ascii=False, indent=1)
            f.write("\n")
        else:
            f.write(render(data, kind, template))
    os.replace(tmp, path)


# ------------------------------------------------------------------ helpers

def today():
    return dt.date.today().isoformat()


def parse_date(s, what="date"):
    try:
        return dt.date.fromisoformat(str(s)[:10])
    except ValueError:
        raise UserError("Invalid %s '%s' (use YYYY-MM-DD)" % (what, s))


def month_key(d):
    return "%04d-%02d" % (d.year, d.month)


def months_between(start, end):
    n = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day < start.day:
        n -= 1
    return max(n, 0)


def years_between(start, end):
    return max((end - start).days, 0) / 365.25


def num(s, what="value"):
    if isinstance(s, (int, float)):
        return float(s)
    t = str(s).strip().replace("_", "").replace(" ", "")
    try:
        v = float(t)
    except ValueError:
        raise UserError("Invalid number for %s: '%s'" % (what, s))
    if math.isnan(v) or math.isinf(v):
        raise UserError("Invalid number for %s: '%s'" % (what, s))
    return v


def kv(item, what):
    if "=" not in item:
        raise UserError("Expected KEY=VALUE for %s, got '%s'" % (what, item))
    k, v = item.split("=", 1)
    return k.strip(), v.strip()


def parse_fx(items):
    fx = {}
    for item in items or []:
        k, v = kv(item, "--fx")
        fx[k.upper()] = num(v, "fx rate " + k)
    return fx


def to_base(raw, base, fx, what):
    """'1234.5' -> 1234.5 ; '1200USD' -> 1200 * fx['USD']"""
    t = str(raw).strip().replace(" ", "").replace("_", "")
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


def r2(v):
    return None if v is None else round(float(v), 2)


def money(v, cur=""):
    if v is None:
        return "-"
    s = "{:,.0f}".format(v)
    return (s + " " + cur).strip()


def pct(v):
    return "-" if v is None else "{:+.1f}%".format(v * 100)


def new_data(currency="EUR", title="Wealth dashboard", owner="", language="en", locale=""):
    return {
        "schema": SCHEMA,
        "settings": {
            "title": title,
            "owner": owner,
            "currency": currency.upper(),
            "language": language,
            "locale": locale or {"en": "en-GB", "fr": "fr-FR", "nl": "nl-NL", "de": "de-DE", "es": "es-ES"}.get(language, "en-GB"),
            "checkin_day": 1,
            "created": today(),
            "updated": today(),
        },
        "accounts": [],
        "holdings": [],
        "snapshots": [],
        "budget": {"months": []},
    }


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


def formula_value(f, on):
    t = f.get("type")
    if t == "depreciation":
        start = parse_date(f["purchase_date"], "purchase_date")
        v = float(f["purchase_price"]) * (1 - float(f.get("annual_rate", 0.15))) ** years_between(start, on)
        if f.get("per_km") and f.get("km") is not None:
            v -= float(f["per_km"]) * max(float(f["km"]) - float(f.get("km_at_purchase", 0)), 0)
        return max(v, float(f.get("floor", 0)))
    if t == "annuity":
        start = parse_date(f["start"], "start")
        p, r, n_total = float(f["principal"]), float(f["annual_rate"]) / 12, int(round(float(f["years"]) * 12))
        n = min(months_between(start, on), n_total)
        if r == 0:
            return p * (1 - n / n_total)
        pmt = p * r / (1 - (1 + r) ** -n_total)
        return max(p * (1 + r) ** n - pmt * ((1 + r) ** n - 1) / r, 0.0)
    if t == "linear":
        start = parse_date(f["start"], "start")
        n_total = int(round(float(f["years"]) * 12))
        n = min(months_between(start, on), n_total)
        return float(f["principal"]) * (1 - n / n_total)
    if t == "growth":
        start = parse_date(f["date"], "date")
        return float(f["value"]) * (1 + float(f.get("annual_rate", 0))) ** years_between(start, on)
    raise UserError("Unknown formula type '%s'" % t)


def computed_value(data, acc, on):
    """Value an account can produce by itself (holdings or formula), else None."""
    base = data["settings"]["currency"]
    if acc.get("method") == "formula" and acc.get("formula"):
        return formula_value(acc["formula"], on)
    hs = account_holdings(data, acc["id"])
    if hs and acc.get("method") in ("holdings", "connector"):
        vals = [holding_value(h, base) for h in hs]
        if any(v is None for v in vals):
            missing = [h.get("id") for h, v in zip(hs, vals) if v is None]
            raise UserError("Holdings without price/quantity/fx in '%s': %s" % (acc["id"], ", ".join(missing)))
        return sum(vals) + float(acc.get("cash", 0) or 0)
    return None


def is_open(acc, on):
    c = acc.get("closed")
    return not c or parse_date(c, "closed") > on


def totals(data, snap):
    accs = accounts_by_id(data)
    out = {g: 0.0 for g in GROUPS}
    for k, v in snap.get("values", {}).items():
        g = accs.get(k, {}).get("group", "other")
        out[g] += float(v)
    assets = sum(out[g] for g in GROUPS if g != "debt")
    out["assets"] = assets
    out["net"] = assets - out["debt"]
    return out


# --------------------------------------------------------------- validation

IBAN_RE = re.compile(r"\b[A-Z]{2}[0-9]{2}(?:\s?[A-Z0-9]{4}){3,7}\b")
LONGNUM_RE = re.compile(r"\d{9,}")


def validate(data):
    errors, warnings = [], []
    if not isinstance(data, dict):
        return ["Top level must be an object"], []
    if data.get("schema") != SCHEMA:
        warnings.append("schema is '%s', expected '%s'" % (data.get("schema"), SCHEMA))
    s = data.get("settings") or {}
    if not re.match(r"^[A-Z]{3}$", str(s.get("currency", ""))):
        errors.append("settings.currency must be a 3-letter code like EUR")
    if s.get("language") and s["language"] not in LANGUAGES:
        warnings.append("settings.language '%s' has no built-in labels; English is used unless settings.labels overrides" % s["language"])
    goal = s.get("goal")
    if goal is not None:
        if not isinstance(goal, dict) or "net_worth" not in goal:
            errors.append("settings.goal must be {\"net_worth\": number, \"by\": \"YYYY-MM-DD\"}")
    infl = s.get("inflation")
    if infl:
        if "index" in infl:
            for k, v in (infl.get("index") or {}).items():
                if not re.match(r"^\d{4}-\d{2}$", k) or not isinstance(v, (int, float)) or v <= 0:
                    errors.append("settings.inflation.index entry %s=%s is invalid (use YYYY-MM: positive number)" % (k, v))
        elif "annual_rate" in infl:
            if not isinstance(infl["annual_rate"], (int, float)) or not -0.5 < infl["annual_rate"] < 1:
                errors.append("settings.inflation.annual_rate must be a decimal like 0.02")
        else:
            errors.append("settings.inflation needs 'index' or 'annual_rate'")

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
        if a.get("method") == "formula":
            f = a.get("formula") or {}
            if f.get("type") not in FORMULAS:
                errors.append("account '%s': formula.type must be one of %s" % (aid, ", ".join(FORMULAS)))
            else:
                try:
                    formula_value(f, dt.date.today())
                except (KeyError, ValueError, TypeError, UserError) as e:
                    errors.append("account '%s': formula is incomplete (%s)" % (aid, e))
        for field in ("name", "institution", "source", "note"):
            val = str(a.get(field, "") or "")
            if IBAN_RE.search(val) or LONGNUM_RE.search(val):
                warnings.append("account '%s' %s looks like it contains an account number - remove it" % (aid, field))

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
        cur = (h.get("currency") or s.get("currency", "")).upper()
        if cur != str(s.get("currency", "")).upper() and h.get("price") is not None and h.get("fx") is None:
            warnings.append("holding '%s' is priced in %s but has no fx rate" % (hid, cur))

    seen_dates = set()
    prev = None
    for sn in data.get("snapshots", []):
        d = sn.get("date")
        try:
            dd = parse_date(d)
        except UserError as e:
            errors.append(str(e))
            continue
        if d in seen_dates:
            errors.append("duplicate snapshot date %s" % d)
        seen_dates.add(d)
        if prev and dd < prev:
            errors.append("snapshots must be sorted by date (%s after %s)" % (d, prev))
        prev = dd
        for k, v in (sn.get("values") or {}).items():
            if k not in ids:
                warnings.append("snapshot %s has a value for unknown account '%s'" % (d, k))
            if not isinstance(v, (int, float)):
                errors.append("snapshot %s: value for '%s' must be a number" % (d, k))
        if sn.get("contributions") is not None and not isinstance(sn["contributions"], (int, float)):
            errors.append("snapshot %s: contributions must be a number" % d)
    accs = accounts_by_id(data)
    for sn in data.get("snapshots", [])[-1:]:
        for k, v in (sn.get("values") or {}).items():
            if accs.get(k, {}).get("group") == "debt" and isinstance(v, (int, float)) and v < 0:
                warnings.append("debt '%s' is negative in the latest snapshot; store the amount owed as a positive number" % k)

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
    return errors, warnings


# ------------------------------------------------------------------ commands

def cmd_new(a):
    if os.path.exists(a.file) and not a.force:
        raise UserError("%s already exists (use --force to overwrite)" % a.file)
    if a.from_json:
        with open(a.from_json, encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = new_data(a.currency, a.title, a.owner or "", a.language, a.locale or "")
    kind = "json" if a.file.lower().endswith(".json") else a.target
    write_any(a.file, data, kind)
    print("Created %s (%s)" % (a.file, kind))


def cmd_export(a):
    data, _ = read_any(a.file)
    text = json.dumps(data, ensure_ascii=False, indent=1)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print("Wrote %s" % a.out)
    else:
        print(text)


def cmd_import(a):
    _, kind = read_any(a.file)
    with open(a.json_file, encoding="utf-8") as f:
        data = json.load(f)
    write_any(a.file, data, kind)
    print("Imported %s into %s" % (a.json_file, a.file))


def cmd_validate(a):
    data, _ = read_any(a.file)
    errors, warnings = validate(data)
    for e in errors:
        print("ERROR   " + e)
    for w in warnings:
        print("WARNING " + w)
    if not errors and not warnings:
        print("OK - %d accounts, %d holdings, %d snapshots, %d budget months" % (
            len(data.get("accounts", [])), len(data.get("holdings", [])),
            len(data.get("snapshots", [])), len((data.get("budget") or {}).get("months", []))))
    return 1 if errors else 0


def cmd_settings(a):
    data, kind = read_any(a.file)
    s = data.setdefault("settings", {})
    for item in a.set or []:
        k, v = kv(item, "--set")
        if k in ("checkin_day",):
            s[k] = int(num(v, k))
        elif k == "currency":
            s[k] = v.upper()
        elif k == "goal_net_worth":
            s.setdefault("goal", {})["net_worth"] = num(v, k)
        elif k == "goal_by":
            parse_date(v, "goal_by")
            s.setdefault("goal", {})["by"] = v
        elif k == "goal":
            if v.lower() in ("", "none", "null"):
                s.pop("goal", None)
            else:
                raise UserError("Use goal_net_worth=... and goal_by=YYYY-MM-DD, or goal=none")
        elif k.startswith("label."):
            s.setdefault("labels", {})[k[6:]] = v
        elif k.startswith("group_label."):
            s.setdefault("group_labels", {})[k[12:]] = v
        elif k in ("title", "owner", "language", "locale", "dashboard_url", "schedule", "backup"):
            s[k] = v
        else:
            raise UserError("Unknown setting '%s'" % k)
    write_any(a.file, data, kind)
    print("Settings updated")


def cmd_account(a):
    data, kind = read_any(a.file)
    accs = data.setdefault("accounts", [])
    acc = next((x for x in accs if x["id"] == a.id), None)
    if a.remove:
        if not acc:
            raise UserError("No account '%s'" % a.id)
        if any(a.id in (s.get("values") or {}) for s in data.get("snapshots", [])):
            raise UserError("'%s' has history. Close it instead: --closed YYYY-MM-DD" % a.id)
        accs.remove(acc)
        data["holdings"] = [h for h in data.get("holdings", []) if h.get("account") != a.id]
        write_any(a.file, data, kind)
        print("Removed account %s" % a.id)
        return
    created = acc is None
    if created:
        acc = {"id": a.id}
        accs.append(acc)
    for field in ("name", "group", "method", "institution", "source", "note", "closed"):
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
    if a.formula is not None:
        acc["formula"] = json.loads(a.formula)
        acc.setdefault("method", "formula")
    for item in a.formula_set or []:
        k, v = kv(item, "--formula-set")
        acc.setdefault("formula", {})[k] = v if k in ("type", "start", "date", "purchase_date") else num(v, k)
    acc.setdefault("method", "ask")
    write_any(a.file, data, kind)
    print("%s account %s" % ("Added" if created else "Updated", a.id))


def cmd_holding(a):
    data, kind = read_any(a.file)
    hs = data.setdefault("holdings", [])
    h = next((x for x in hs if x["id"] == a.id), None)
    if a.remove:
        if not h:
            raise UserError("No holding '%s'" % a.id)
        hs.remove(h)
        write_any(a.file, data, kind)
        print("Removed holding %s" % a.id)
        return
    created = h is None
    if created:
        if not a.account:
            raise UserError("New holding needs --account")
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
    if a.price is not None:
        h["price_date"] = a.date or today()
    write_any(a.file, data, kind)
    print("%s holding %s" % ("Added" if created else "Updated", a.id))


def find_holding(data, key):
    k = key.lower()
    for h in data.get("holdings", []):
        if h["id"] == key or str(h.get("ticker", "")).lower() == k:
            return h
    raise UserError("No holding with id or ticker '%s'" % key)


def cmd_prices(a):
    data, kind = read_any(a.file)
    fx = parse_fx(a.fx)
    base = data["settings"]["currency"]
    d = a.date or today()
    parse_date(d)
    changed = []
    for item in a.set or []:
        k, v = kv(item, "--set")
        h = find_holding(data, k)
        h["price"] = num(v, "price of " + k)
        h["price_date"] = d
        if a.source:
            h["price_source"] = a.source
        changed.append(h["id"])
    for item in a.qty or []:
        k, v = kv(item, "--qty")
        h = find_holding(data, k)
        h["quantity"] = num(v, "quantity of " + k)
        changed.append(h["id"])
    for h in data.get("holdings", []):
        cur = (h.get("currency") or base).upper()
        if cur != base and cur in fx:
            h["fx"] = fx[cur]
    write_any(a.file, data, kind)
    print("Updated %d holding fields%s" % (len(changed), (" and fx " + ", ".join(sorted(fx))) if fx else ""))


def build_snapshot(data, on, explicit, history=False, keep_month=False, allow_missing=False,
                   contrib=None, note=None, fx=None):
    """Create or update the snapshot for date `on`. Returns (snap, carried, missing)."""
    base = data["settings"]["currency"]
    date_s = on.isoformat()
    accs = accounts_by_id(data)
    snaps = data.setdefault("snapshots", [])
    same = None
    if not keep_month:
        same = next((s for s in snaps if s["date"][:7] == date_s[:7]), None)
    if history:
        same_exact = same
        same = None
    earlier = [s for s in snaps if s["date"] <= date_s and s is not same and not (history and s is same_exact)]
    prev = earlier[-1] if earlier else None

    values, carried, missing = {}, [], []
    for aid, acc in accs.items():
        if not is_open(acc, on):
            continue
        if aid in explicit:
            values[aid] = explicit[aid]
            continue
        if history:
            # Past dates: only formulas know their old value; holdings use today's prices.
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
        raise UserError(
            "No value for: %s. Pass --set ID=VALUE, or --allow-missing to leave them out." % ", ".join(missing)
        )
    snap = {"date": date_s, "values": {k: r2(v) for k, v in values.items()}}
    if carried:
        snap["carried"] = sorted(carried)
    if contrib is None and same is not None:
        contrib = same.get("contributions")
    if contrib is not None:
        snap["contributions"] = r2(to_base(contrib, base, fx or {}, "contributions"))
    notes = [n for n in [(same or {}).get("note"), note] if n]
    if notes:
        snap["note"] = " | ".join(dict.fromkeys(notes))
    if fx:
        snap["fx"] = fx
    old = same if not history else (same_exact if not keep_month else None)
    if old is not None:
        snaps.remove(old)
    snaps.append(snap)
    snaps.sort(key=lambda s: s["date"])
    return snap, carried, missing


def gaps(data, snap):
    """Accounts present both before and after this snapshot but missing from it (they count as 0)."""
    snaps = data.get("snapshots", [])
    before = [x for x in snaps if x["date"] < snap["date"]]
    after = [x for x in snaps if x["date"] > snap["date"]]
    if not before or not after:
        return []
    return sorted(k for k in before[-1].get("values", {})
                  if k in after[0].get("values", {}) and k not in snap["values"])


def cmd_snapshot(a):
    data, kind = read_any(a.file)
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
        explicit[k] = to_base(v, base, fx, k)
    snap, carried, missing = build_snapshot(
        data, on, explicit, history=a.history, keep_month=a.keep_month,
        allow_missing=a.allow_missing or a.history, contrib=a.contributions, note=a.note, fx=fx)
    write_any(a.file, data, kind)
    t = totals(data, snap)
    print("Snapshot %s saved: net worth %s %s" % (snap["date"], money(t["net"]), base))
    if carried:
        print("Carried forward (not updated yet): " + ", ".join(sorted(carried)))
    if missing:
        print("Left out (no value): " + ", ".join(missing))
    g = gaps(data, snap)
    if g:
        print("WARNING: missing on this date, so counted as 0: %s. Add them with --set." % ", ".join(g))


def cmd_history(a):
    """CSV columns: date, then one column per account id; optional contributions and note."""
    import csv
    data, kind = read_any(a.file)
    base = data["settings"]["currency"]
    fx = parse_fx(a.fx)
    accs = accounts_by_id(data)
    with open(a.csv, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise UserError("The CSV has no rows")
    cols = [c for c in rows[0].keys() if c not in ("date", "contributions", "note")]
    unknown = [c for c in cols if c not in accs]
    if "date" not in rows[0]:
        raise UserError("The CSV needs a 'date' column (YYYY-MM-DD)")
    if unknown:
        raise UserError("Unknown account ids in CSV header: %s" % ", ".join(unknown))
    n = 0
    for row in rows:
        on = parse_date(row["date"])
        explicit = {k: to_base(v, base, fx, k) for k, v in row.items() if k in accs and v not in (None, "")}
        c = row.get("contributions") or None
        build_snapshot(data, on, explicit, history=True, allow_missing=True, contrib=c, note=row.get("note") or None)
        n += 1
    write_any(a.file, data, kind)
    for sn in data["snapshots"]:
        g = gaps(data, sn)
        if g:
            print("WARNING %s: missing, so counted as 0: %s" % (sn["date"], ", ".join(g)))
    print("Imported %d historical snapshots (%s to %s)" % (n, rows[0]["date"], rows[-1]["date"]))


def cmd_budget(a):
    data, kind = read_any(a.file)
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
    write_any(a.file, data, kind)
    inc = sum(m.get("income", {}).values())
    exp = sum(m.get("expenses", {}).values())
    rate = (inc - exp) / inc if inc else None
    print("Budget %s: income %s, expenses %s, saved %s (%s)" % (
        a.month, money(inc), money(exp), money(inc - exp), "-" if rate is None else "{:.0%}".format(rate)))


def cmd_inflation(a):
    data, kind = read_any(a.file)
    s = data["settings"]
    if a.off:
        s.pop("inflation", None)
    elif a.rate is not None:
        s["inflation"] = {"annual_rate": num(a.rate, "rate")}
    else:
        infl = s.get("inflation") or {}
        if "index" not in infl:
            infl = {"index": {}}
        for item in a.set or []:
            k, v = kv(item, "--set")
            if not re.match(r"^\d{4}-\d{2}$", k):
                raise UserError("Index month must be YYYY-MM, got '%s'" % k)
            infl["index"][k] = num(v, k)
        infl["index"] = dict(sorted(infl["index"].items()))
        if a.source:
            infl["source"] = a.source
        s["inflation"] = infl
    write_any(a.file, data, kind)
    print("Inflation settings updated")


def stale_holdings(data, ref):
    out = []
    for h in data.get("holdings", []):
        pd = h.get("price_date")
        if not pd or (ref - parse_date(pd)).days > STALE_DAYS:
            out.append(h)
    return out


def cmd_plan(a):
    data, _ = read_any(a.file)
    s = data["settings"]
    on = dt.date.today()
    snaps = data.get("snapshots", [])
    last = snaps[-1] if snaps else None
    print("UPDATE PLAN - %s (%s)" % (s.get("title", "Wealth dashboard"), s["currency"]))
    print("Last snapshot: %s" % (last["date"] if last else "none yet"))
    if s.get("dashboard_url"):
        print("Dashboard: %s" % s["dashboard_url"])
    auto, user = [], []
    for acc in data.get("accounts", []):
        if not is_open(acc, on):
            continue
        m, name = acc.get("method"), "%s [%s]" % (acc.get("name"), acc["id"])
        src = (" - " + acc["source"]) if acc.get("source") else ""
        hs = account_holdings(data, acc["id"])
        if m == "connector":
            auto.append("%s: pull balances%s from the connector%s" % (name, " and positions" if hs else "", src))
        elif m == "holdings":
            addr = [h for h in hs if h.get("address")]
            line = "%s: refresh prices for %d holding(s)" % (name, len(hs))
            if addr:
                line += "; read on-chain balance for %s" % ", ".join(h["id"] for h in addr)
            auto.append(line + src)
        elif m == "formula":
            f = acc.get("formula", {})
            if f.get("per_km"):
                user.append("%s: current odometer reading (km) - value is computed" % name)
            else:
                auto.append("%s: computed by formula (%s)" % (name, f.get("type")))
        elif m == "fixed":
            pass
        elif m == "statement":
            user.append("%s: upload the latest statement/export or a screenshot%s" % (name, src))
        else:
            what = {"property": "current estimated value", "other": "current estimated value",
                    "debt": "outstanding balance"}.get(acc.get("group"), "current balance")
            user.append("%s: %s%s" % (name, what, src))
    if s.get("inflation", {}).get("index") is not None:
        auto.append("Inflation: add the latest monthly index value (%s)" % s["inflation"].get("source", "CPI"))
    if (data.get("budget") or {}).get("months"):
        user.append("Budget: last month's income and expenses (bank export, screenshot, or totals)")
    user.append("Contributions: net amount you added to (or withdrew from) investment accounts since the last update")
    print("\nAUTOMATIC (do these first):")
    for x in auto or ["(nothing automatic)"]:
        print("  - " + x)
    print("\nNEEDS THE USER (ask in one message):")
    for x in user:
        print("  - " + x)
    return 0


def cmd_summary(a):
    data, _ = read_any(a.file)
    s = data["settings"]
    cur = s["currency"]
    snaps = data.get("snapshots", [])
    if not snaps:
        print("No snapshots yet.")
        return 0
    last = snaps[-1]
    t = totals(data, last)
    print("%s - as of %s (%s)" % (s.get("title", "Wealth dashboard"), last["date"], cur))
    print("Net worth: %s  (assets %s, debts %s)" % (money(t["net"]), money(t["assets"]), money(t["debt"])))
    if len(snaps) > 1:
        p = snaps[-2]
        tp = totals(data, p)
        ch = t["net"] - tp["net"]
        inv_ch = t["invested"] - tp["invested"]
        c = last.get("contributions") or 0
        print("Change since %s: %s (%s)" % (p["date"], money(ch), pct(ch / abs(tp["net"])) if tp["net"] else "-"))
        print("Investments: %s, change %s of which contributions %s and market %s" % (
            money(t["invested"]), money(inv_ch), money(c), money(inv_ch - c)))
    ld = parse_date(last["date"])
    y0 = [x for x in snaps if x["date"] < "%d-01-01" % ld.year]
    if y0:
        ty = totals(data, y0[-1])
        print("Year to date: %s (%s)" % (money(t["net"] - ty["net"]), pct((t["net"] - ty["net"]) / abs(ty["net"])) if ty["net"] else "-"))
    names = {"invested": "Investments", "cash": "Cash", "retirement": "Pensions", "property": "Property", "other": "Other", "debt": "Debts"}
    print("By group: " + ", ".join(
        "%s %s" % (names[g], money(t[g])) for g in GROUPS if t[g]))
    if last.get("carried"):
        accs = accounts_by_id(data)
        print("Estimated (carried from an earlier month): " + ", ".join(
            accs.get(k, {}).get("name", k) for k in last["carried"]))
    st = stale_holdings(data, ld)
    if st:
        print("Prices older than %d days: %s" % (STALE_DAYS, ", ".join(h.get("ticker") or h["id"] for h in st)))
    months = (data.get("budget") or {}).get("months", [])
    if months:
        m = months[-1]
        inc = sum(m.get("income", {}).values())
        exp = sum(m.get("expenses", {}).values())
        print("Budget %s: income %s, expenses %s, saved %s%s" % (
            m["month"], money(inc), money(exp), money(inc - exp),
            (" (%.0f%%)" % ((inc - exp) / inc * 100)) if inc else ""))
    g = s.get("goal")
    if g and g.get("net_worth"):
        print("Goal: %s by %s - %.0f%% reached" % (money(g["net_worth"]), g.get("by", "-"), t["net"] / g["net_worth"] * 100))
    return 0


def cmd_build(a):
    data, kind = read_any(a.file)
    target = a.target or (kind if kind != "json" else "file")
    out = a.out or (a.file if kind != "json" else os.path.splitext(a.file)[0] + ".html")
    write_any(out, data, target, a.template)
    print("Built %s (%s)" % (out, target))


# ---------------------------------------------------------------------- cli

def main(argv=None):
    p = argparse.ArgumentParser(prog="wealth.py", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    x = sub.add_parser("new", help="create a new dashboard")
    x.add_argument("file")
    x.add_argument("--currency", default="EUR")
    x.add_argument("--title", default="Wealth dashboard")
    x.add_argument("--owner")
    x.add_argument("--language", default="en", help="UI language: en, fr, nl, de, es")
    x.add_argument("--locale", help="number/date format, e.g. fr-FR, en-US")
    x.add_argument("--target", choices=["artifact", "file"], default="file",
                   help="artifact = page fragment for publishing as a Claude artifact; file = standalone HTML")
    x.add_argument("--from", dest="from_json", help="start from this JSON data file")
    x.add_argument("--force", action="store_true")
    x.set_defaults(fn=cmd_new)

    x = sub.add_parser("export", help="write embedded data as JSON")
    x.add_argument("file")
    x.add_argument("--out")
    x.set_defaults(fn=cmd_export)

    x = sub.add_parser("import", help="replace embedded data with a JSON file")
    x.add_argument("file")
    x.add_argument("json_file")
    x.set_defaults(fn=cmd_import)

    x = sub.add_parser("validate", help="check the data")
    x.add_argument("file")
    x.set_defaults(fn=cmd_validate)

    x = sub.add_parser("settings", help="change settings")
    x.add_argument("file")
    x.add_argument("--set", action="append", metavar="KEY=VALUE",
                   help="title, owner, currency, language, locale, checkin_day, goal_net_worth, goal_by, "
                        "goal=none, dashboard_url, schedule, backup, label.<key>, group_label.<group>")
    x.set_defaults(fn=cmd_settings)

    x = sub.add_parser("account", help="add or update an account")
    x.add_argument("file")
    x.add_argument("--id", required=True)
    x.add_argument("--name")
    x.add_argument("--group", choices=GROUPS)
    x.add_argument("--method", choices=METHODS)
    x.add_argument("--class", dest="asset_class", help="asset class, e.g. equity, bonds, crypto, gold, cash")
    x.add_argument("--institution")
    x.add_argument("--source", help="how to update it, in plain words (for future runs)")
    x.add_argument("--note")
    x.add_argument("--cash", help="uninvested cash inside a holdings account, in base currency")
    x.add_argument("--formula", help='JSON, e.g. \'{"type":"annuity","principal":300000,"annual_rate":0.04,"years":30,"start":"2021-06-01"}\'')
    x.add_argument("--formula-set", action="append", metavar="FIELD=VALUE")
    x.add_argument("--closed", help="YYYY-MM-DD the account was closed (keeps history)")
    x.add_argument("--remove", action="store_true", help="delete an account that has no history")
    x.set_defaults(fn=cmd_account)

    x = sub.add_parser("holding", help="add, update or remove a holding")
    x.add_argument("file")
    x.add_argument("--id", required=True)
    x.add_argument("--account")
    x.add_argument("--name")
    x.add_argument("--ticker")
    x.add_argument("--isin")
    x.add_argument("--class", dest="asset_class")
    x.add_argument("--quantity")
    x.add_argument("--unit", help="unit label for quantity, e.g. oz, g, BTC")
    x.add_argument("--price", help="price per unit in the holding's currency")
    x.add_argument("--currency", help="currency the price is quoted in (default: base)")
    x.add_argument("--fx", help="base currency per 1 unit of the holding currency")
    x.add_argument("--cost", help="total cost basis in base currency")
    x.add_argument("--address", help="public on-chain address for automatic quantity")
    x.add_argument("--price-source", dest="price_source", help="where the price comes from")
    x.add_argument("--date", help="price date (default today)")
    x.add_argument("--note")
    x.add_argument("--remove", action="store_true")
    x.set_defaults(fn=cmd_holding)

    x = sub.add_parser("prices", help="update prices / quantities in bulk")
    x.add_argument("file")
    x.add_argument("--set", action="append", metavar="ID_OR_TICKER=PRICE")
    x.add_argument("--qty", action="append", metavar="ID_OR_TICKER=QUANTITY")
    x.add_argument("--fx", action="append", metavar="CUR=RATE", help="base per 1 CUR, e.g. USD=0.92")
    x.add_argument("--date")
    x.add_argument("--source")
    x.set_defaults(fn=cmd_prices)

    x = sub.add_parser("snapshot", help="record this month's values")
    x.add_argument("file")
    x.add_argument("--date", help="YYYY-MM-DD (default today)")
    x.add_argument("--set", action="append", metavar="ACCOUNT=VALUE", help="value in base currency, or e.g. 1200USD with --fx")
    x.add_argument("--fx", action="append", metavar="CUR=RATE")
    x.add_argument("--formula", action="append", metavar="ACCOUNT.FIELD=VALUE", help="e.g. car.km=84200")
    x.add_argument("--contributions", help="net new money into investment accounts since the last snapshot")
    x.add_argument("--note")
    x.add_argument("--keep-month", action="store_true", help="add a second snapshot in the same month instead of updating it")
    x.add_argument("--allow-missing", action="store_true")
    x.add_argument("--history", action="store_true",
                   help="past date: use only the values given (plus formulas); no carrying, no current prices")
    x.set_defaults(fn=cmd_snapshot)

    x = sub.add_parser("history", help="import past snapshots from a CSV (date + one column per account)")
    x.add_argument("file")
    x.add_argument("csv")
    x.add_argument("--fx", action="append", metavar="CUR=RATE")
    x.set_defaults(fn=cmd_history)

    x = sub.add_parser("budget", help="record a month of income and expenses")
    x.add_argument("file")
    x.add_argument("--month", required=True, help="YYYY-MM")
    x.add_argument("--income", action="append", metavar="CATEGORY=AMOUNT")
    x.add_argument("--expense", action="append", metavar="CATEGORY=AMOUNT")
    x.add_argument("--json", help='file with {"income": {...}, "expenses": {...}}')
    x.add_argument("--fx", action="append", metavar="CUR=RATE")
    x.add_argument("--note")
    x.add_argument("--replace", action="store_true", help="replace the month instead of merging")
    x.set_defaults(fn=cmd_budget)

    x = sub.add_parser("inflation", help="set inflation index values or a flat rate")
    x.add_argument("file")
    x.add_argument("--set", action="append", metavar="YYYY-MM=INDEX")
    x.add_argument("--rate", help="flat annual rate instead of an index, e.g. 0.02")
    x.add_argument("--source", help="e.g. 'Eurostat HICP, euro area (2015=100)'")
    x.add_argument("--off", action="store_true")
    x.set_defaults(fn=cmd_inflation)

    x = sub.add_parser("plan", help="print the update plan")
    x.add_argument("file")
    x.set_defaults(fn=cmd_plan)

    x = sub.add_parser("summary", help="print a summary of the latest month")
    x.add_argument("file")
    x.set_defaults(fn=cmd_summary)

    x = sub.add_parser("build", help="re-render with the current template")
    x.add_argument("file")
    x.add_argument("--target", choices=["artifact", "file"])
    x.add_argument("--out")
    x.add_argument("--template", help=argparse.SUPPRESS)
    x.set_defaults(fn=cmd_build)

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
