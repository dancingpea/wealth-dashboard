#!/usr/bin/env python3
"""Turn the raw comparison tables into the skill's reference files, with every figure brought to today's prices.

    python3 tools/peers.py            # once a year: fetch the survey tables (raw)
    python3 tools/reference_data.py   # fetch consumer prices, adjust, write the reference files

Writes plugin/skills/wealth-dashboard/assets/reference/peers.json and peers_meta.json.
Consumer prices: Eurostat HICP (2015=100) per country, euro area for countries without one; US CPI-U via FRED.
All sources are public statistics; nothing about any household is sent anywhere.
"""
import csv
import io
import json
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent
RAW = ROOT / "reference"
OUT = ROOT.parent / "plugin" / "skills" / "wealth-dashboard" / "assets" / "reference"


def get(url):
    r = subprocess.run(["curl", "-s", "-f", "-L", "-m", "120", "--retry", "2", url], capture_output=True, check=True)
    return r.stdout.decode("utf-8")


def hicp(geos):
    q = "&".join("geo=" + g for g in sorted(geos))
    url = ("https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/prc_hicp_minr?format=JSON&lang=EN"
           "&coicop18=TOTAL&unit=I15&sinceTimePeriod=2019-01&" + q)
    d = json.loads(get(url))
    dims, size = d["id"], d["size"]
    idx = {k: d["dimension"][k]["category"]["index"] for k in dims}
    out = {}
    for pos_s, v in d["value"].items():
        pos, coord = int(pos_s), {}
        for k, n in reversed(list(zip(dims, size))):
            i = pos % n
            pos //= n
            coord[k] = next(code for code, j in idx[k].items() if j == i)
        out.setdefault(coord["geo"], {})[coord["time"]] = v
    return out


def us_cpi():
    rows = csv.reader(io.StringIO(get("https://fred.stlouisfed.org/graph/fredgraph.csv?id=CPIAUCNS&cosd=2019-01-01")))
    next(rows)
    return {r[0][:7]: float(r[1]) for r in rows if r[1] not in ("", ".")}


def main():
    rows = list(csv.DictReader(open(RAW / "peers_raw.csv", encoding="utf-8")))
    meta = list(csv.DictReader(open(RAW / "peers_meta_raw.csv", encoding="utf-8")))
    countries = sorted({m["country"] for m in meta} - {"US"})
    geo = {c: ("EL" if c == "GR" else c) for c in countries}
    idx = hicp(set(geo.values()) | {"EA20"})
    idx = {("GR" if g == "EL" else g): v for g, v in idx.items()}
    idx["US"] = us_cpi()
    ea = idx.get("EA20", {})

    def series(c):
        s = idx.get(c) or {}
        return (s, c) if len(s) > 12 else (ea, "EA20")

    def at(s, month):
        ks = sorted(k for k in s if k <= month)
        return s[ks[-1]] if ks else s[min(s)]

    factor, used, now_month = {}, {}, {}
    for m in meta:
        s, area = series(m["country"])
        last = max(s)
        ref = m["ref_month"] or last
        f = s[last] / at(s, ref)
        k = (m["country"], m["metric"], m["population"])
        factor[k] = 1.0 if m["metric"] == "saving_rate" else f
        used[k] = area
        now_month[k] = last
    out_rows = []
    for r in rows:
        k = (r["country"], r["metric"], r["population"])
        if k not in factor:
            continue
        v = float(r["value"])
        out_rows.append({"country": r["country"], "metric": r["metric"], "population": r["population"],
                         "p": int(r["p"]) if r["p"] not in ("", None) else None, "value": round(v * factor[k], 2)})
    out_meta = []
    for m in meta:
        k = (m["country"], m["metric"], m["population"])
        out_meta.append({**{f: m[f] for f in ("country", "country_name", "metric", "population", "pop_label", "currency",
                                               "ref_month", "source", "url", "note")},
                         "prices_month": now_month[k], "price_factor": round(factor[k], 4),
                         "price_index": "Eurostat HICP " + used[k] if used[k] != "US" else "US CPI-U (BLS via FRED)"})
    OUT.mkdir(parents=True, exist_ok=True)
    json.dump(out_rows, open(OUT / "peers.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    json.dump(out_meta, open(OUT / "peers_meta.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print("peers.json %d rows, peers_meta.json %d tables, prices up to %s" % (len(out_rows), len(out_meta), max(now_month.values())))


if __name__ == "__main__":
    main()
