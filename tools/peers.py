"""Percentile tables for the "How you compare" section -> tools/reference/peers_raw.csv + peers_meta_raw.csv.

python3 tools/peers.py            (needs web access to the sources below; takes a few minutes)
Then python3 tools/reference_data.py turns them into the skill's reference files (prices brought up to date).

Sources (all public; nothing about the household is sent anywhere):
- Eurostat EU-SILC ilc_di01: equivalised disposable income cut-offs (P1-P5, deciles, P95-P99), every EU-SILC country.
- Eurostat SES earn_ses_annual: gross annual earnings of full-time employees (D1, median, D9) by age band.
- Eurostat tec00131: gross household saving rate.
- ECB HFCS statistical tables (latest wave): net wealth and gross household income deciles, medians by age of the
  reference person, for every HFCS country.
- CBS (Netherlands) 83934NED: wealth deciles (more recent than HFCS, from tax records); 83835NED: households by wealth class and age of main earner.
- US Federal Reserve SCF (latest public extract): weighted percentiles of net worth, net worth without retirement
  accounts, and household income, all households and head under 35.
- US BLS via FRED: usual weekly earnings of full-time wage and salary workers (D1, Q1, median, Q3, D9).

peers.csv: country, metric, population, p, value.  peers_meta.csv: one row per table (country, metric, population) with
country_name, pop_label, currency, ref_month, source, url, note.
Metrics: net_wealth, net_wealth_ex_ret (US only), equiv_income, hh_gross_income, earnings, saving_rate (p empty).
Run yearly (January); the page adjusts each figure from ref_month to today with consumer prices.
"""
import csv, io, json, pathlib, re, subprocess, sys, zipfile, tempfile
ROOT = pathlib.Path(__file__).resolve().parent
OUT = ROOT / "reference" / "peers_raw.csv"
NAMES = {"AT": "Austria", "BE": "Belgium", "BG": "Bulgaria", "CY": "Cyprus", "CZ": "Czechia", "DE": "Germany", "DK": "Denmark",
         "EE": "Estonia", "EL": "Greece", "GR": "Greece", "ES": "Spain", "FI": "Finland", "FR": "France", "HR": "Croatia",
         "HU": "Hungary", "IE": "Ireland", "IT": "Italy", "LT": "Lithuania", "LU": "Luxembourg", "LV": "Latvia", "MT": "Malta",
         "NL": "Netherlands", "PL": "Poland", "PT": "Portugal", "RO": "Romania", "SE": "Sweden", "SI": "Slovenia",
         "SK": "Slovakia", "NO": "Norway", "CH": "Switzerland", "IS": "Iceland", "RS": "Serbia", "ME": "Montenegro",
         "MK": "North Macedonia", "AL": "Albania", "TR": "Türkiye", "UK": "United Kingdom", "US": "United States"}
rows = []


def get(url, binary=False):
    r = subprocess.run(["curl", "-s", "-f", "-L", "-m", "300", "--retry", "2", url], capture_output=True, check=True)
    return r.stdout if binary else r.stdout.decode("utf-8")


def add(country, metric, population, pop_label, p, value, currency, ref_month, source, url, note=""):
    if value is None:
        return
    c = "GR" if country == "EL" else country
    rows.append({"country": c, "country_name": NAMES.get(c, c), "metric": metric, "population": population,
                 "pop_label": pop_label, "p": p, "value": round(float(value), 2), "currency": currency,
                 "ref_month": ref_month, "source": source, "url": url, "note": note})


def eurostat(ds, params):
    url = f"https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{ds}?format=JSON&lang=EN&{params}"
    d = json.loads(get(url))
    dims, size = d["id"], d["size"]
    idx = {k: d["dimension"][k]["category"]["index"] for k in dims}
    out = []
    for pos_s, v in d["value"].items():
        pos, coord = int(pos_s), {}
        for k, n in reversed(list(zip(dims, size))):
            i = pos % n; pos //= n
            coord[k] = next(code for code, j in idx[k].items() if j == i)
        out.append((coord, v))
    return out, url


def silc():
    data, url = eurostat("ilc_di01", "statinfo=TC&unit=EUR&sinceTimePeriod=2022")
    latest = {}
    for c, v in data:
        latest[c["geo"]] = max(latest.get(c["geo"], "0"), c["time"])
    qmap = {f"D{i}": i * 10 for i in range(1, 10)} | {f"P{i}": i for i in (1, 2, 3, 4, 5, 95, 96, 97, 98, 99)}
    for c, v in data:
        g = c["geo"]
        if len(g) != 2 or c["time"] != latest[g] or c["quant_inc"] not in qmap:
            continue
        y = int(c["time"])
        add(g, "equiv_income", "all", "Everyone (equivalised disposable income per person)", qmap[c["quant_inc"]], v, "EUR",
            f"{y - 1}-07", f"Eurostat EU-SILC {y} (income year {y - 1})", url,
            "Disposable household income after tax and benefits, divided by the OECD-modified scale (1 for the first adult, 0.5 per other person 14+, 0.3 per child under 14).")


def ses():
    data, url = eurostat("earn_ses_annual", "sex=T&nace_r2=B-S_X_O&isco08=TOTAL&worktime=FT&time=2022"
                         "&indic_se=D1_E_EUR&indic_se=MED_E_EUR&indic_se=D9_E_EUR&age=TOTAL&age=Y_LT30&age=Y30-39&age=Y40-49&age=Y50-59&age=Y_GE60")
    pm = {"D1_E_EUR": 10, "MED_E_EUR": 50, "D9_E_EUR": 90}
    lab = {"TOTAL": "Full-time employees, all ages", "Y_LT30": "Full-time employees under 30", "Y30-39": "Full-time employees aged 30-39",
           "Y40-49": "Full-time employees aged 40-49", "Y50-59": "Full-time employees aged 50-59", "Y_GE60": "Full-time employees aged 60+"}
    pop = {"TOTAL": "all", "Y_LT30": "age:0-29", "Y30-39": "age:30-39", "Y40-49": "age:40-49", "Y50-59": "age:50-59", "Y_GE60": "age:60-120"}
    for c, v in data:
        if len(c["geo"]) != 2:
            continue
        add(c["geo"], "earnings", pop[c["age"]], lab[c["age"]], pm[c["indic_se"]], v,
            "EUR", "2022-07", "Eurostat Structure of Earnings Survey 2022", url,
            "Gross annual earnings of full-time employees (firms with 10+ staff; public administration excluded).")


def saving():
    data, url = eurostat("tec00131", "sinceTimePeriod=2020")
    latest = {}
    for c, v in data:
        if len(c["geo"]) == 2 and c["time"] >= latest.get(c["geo"], ("0", 0))[0]:
            latest[c["geo"]] = (c["time"], v)
    for g, (t, v) in latest.items():
        add(g, "saving_rate", "all", "National average", "", v / 100, "pct", f"{t}-07", f"Eurostat gross household saving rate {t}", url,
            "Gross saving as a share of gross disposable income, national accounts (includes pension saving).")


HFCS_INDEX = "https://www.ecb.europa.eu/stats/ecb_surveys/hfcs/html/index.en.html"
HFCS_BANDS = {"16-34": "16-34", "35-44": "35-44", "45-54": "45-54", "55-64": "55-64", "65-74": "65-74", "75+": "75-120"}


def hfcs():
    import openpyxl
    html = get(HFCS_INDEX)
    links = re.findall(r'href="(/home/pdf/research/hfcn/HFCS_Statistical_Tables_Wave_(\d{4})[^"]*\.zip[^"]*)"', html)
    href, wave = max(links, key=lambda l: l[1])
    url = "https://www.ecb.europa.eu" + href
    z = zipfile.ZipFile(io.BytesIO(get(url, binary=True)))
    name = next(n for n in z.namelist() if n.endswith(".xlsx"))
    tmp = pathlib.Path(tempfile.mkdtemp()) / "hfcs.xlsx"
    tmp.write_bytes(z.read(name))
    wb = openpyxl.load_workbook(tmp, read_only=True, data_only=True)
    sheet = lambda prefix: wb[next(s for s in wb.sheetnames if s.startswith(prefix))]
    # reference months: fieldwork midpoint for wealth, income year for income
    ref = {}
    for r in sheet("Reference periods").iter_rows(values_only=True):
        if r and r[0] and r[1] and re.match(r"\d\d/\d\d", str(r[1])):
            ref[r[0]] = (r[1], r[2], str(r[4] or ""))
    def months(country_name):
        f0, f1, inc = ref.get(country_name, ("06/23", "06/23", ""))
        m0 = int(f0[3:]) * 12 + int(f0[:2]); m1 = int(f1[3:]) * 12 + int(f1[:2]); m = (m0 + m1) // 2
        wealth = f"20{m // 12:02d}-{m % 12 + 1:02d}" if m % 12 != 11 else f"20{m // 12:02d}-12"
        y = re.search(r"(20\d\d)", inc)
        income = f"{y.group(1)}-07" if y else f"20{int(f0[3:]) - 1:02d}-07"
        return wealth, income
    long = {"BE": "Belgium", "CZ": "Czech Republic", "DE": "Germany", "EE": "Estonia", "IE": "Ireland", "GR": "Greece", "ES": "Spain",
            "FR": "France", "HR": "Croatia", "IT": "Italy", "CY": "Cyprus", "LV": "Latvia", "LT": "Lithuania", "LU": "Luxembourg",
            "HU": "Hungary", "MT": "Malta", "NL": "Netherlands", "AT": "Austria", "PT": "Portugal", "SI": "Slovenia",
            "SK": "Slovakia", "FI": "Finland"}
    def table(prefix):
        it = sheet(prefix).iter_rows(values_only=True)
        hdr, body = None, []
        for r in it:
            vals = [v for v in r if v not in (None, "")]
            if not vals:
                continue
            if hdr is None and "euro area" in vals:
                hdr = vals; continue
            if hdr and not str(vals[0]).startswith("(") and not str(vals[0]).startswith("Source"):
                body.append(vals)
        return hdr, body
    src = f"ECB HFCS wave {wave}"
    note_w = "Household net wealth: real and financial assets (incl. vehicles) minus debts; public and occupational pension rights excluded."
    hdr, body = table("J3")
    for r in body:
        if not str(r[0]).startswith("p"):
            continue
        p = int(r[0][1:])
        for code, v in zip(hdr, r[1:]):
            if code == "euro area" or code == "NL":
                continue
            add(code, "net_wealth", "all", "All households", p, float(v) * 1000, "EUR", months(long[code])[0], src, url, note_w)
    hdr, body = table("A3")
    for r in body:
        if r[0] == "Age of RP" or (len(r) == len(hdr) + 1 and str(r[0]) in HFCS_BANDS):
            band, vals = (r[1], r[2:]) if r[0] == "Age of RP" else (r[0], r[1:])
            if str(band) not in HFCS_BANDS:
                continue
            band = HFCS_BANDS[str(band)]
            for code, v in zip(hdr, vals):
                if code in ("euro area", "NL"):
                    continue
                add(code, "net_wealth", "age:" + band, f"Households, main earner aged {band.replace('-120', '+')}", 50, float(v) * 1000, "EUR",
                    months(long[code])[0], src + " (median only)", url, note_w)
    hdr, body = table("I3")
    for r in body:
        if not str(r[0]).startswith("p"):
            continue
        p = int(r[0][1:])
        for code, v in zip(hdr, r[1:]):
            if code == "euro area":
                continue
            add(code, "hh_gross_income", "all", "All households", p, float(v) * 1000, "EUR", months(long[code])[1], src, url,
                "Gross household income before tax, all members, survey income year.")
    hdr, body = table("I1")
    for r in body:
        if r[0] == "Age of RP" or str(r[0]) in HFCS_BANDS:
            band, vals = (r[1], r[2:]) if r[0] == "Age of RP" else (r[0], r[1:])
            if str(band) not in HFCS_BANDS:
                continue
            band = HFCS_BANDS[str(band)]
            for code, v in zip(hdr, vals):
                if code == "euro area":
                    continue
                add(code, "hh_gross_income", "age:" + band, f"Households, main earner aged {band.replace('-120', '+')}", 50, float(v) * 1000, "EUR",
                    months(long[code])[1], src + " (median only)", url, "Gross household income before tax.")


def cbs_json(table, path):
    from urllib.parse import quote
    return json.loads(get(f"https://opendata.cbs.nl/ODataApi/odata/{table}/" + quote(path, safe="/?$=&'")))["value"]


def cbs():
    # deciles of wealth and gross income, all private households incl. students
    t = "83934NED"
    pct = {p["Key"]: int(re.match(r"(\d+)", p["Title"]).group(1)) for p in cbs_json(t, "Percentielen")}
    per = sorted(p["Key"] for p in cbs_json(t, "Perioden"))
    data = cbs_json(t, f"TypedDataSet?$filter=Populatie eq '1050010'")
    url = f"https://opendata.cbs.nl/statline/#/CBS/nl/dataset/{t}/table"
    def latest(field):
        ys = [r["Perioden"] for r in data if r.get(field) is not None]
        return max(ys) if ys else None
    yw = latest("PercentielVermogen_5")
    for r in data:
        p = pct[r["Percentielen"]]
        if r["Perioden"] == yw and r["PercentielVermogen_5"] is not None:
            add("NL", "net_wealth", "all", "All households", p, r["PercentielVermogen_5"] * 1000, "EUR", f"{yw[:4]}-01",
                f"CBS {t} (wealth on 1 Jan {yw[:4]})", url,
                "Household wealth from tax records: savings, investments, home, business assets minus debts; pension rights and cars excluded.")
    # households by wealth class and age of main earner -> percentiles by interpolation
    t2 = "83835NED"
    url2 = f"https://opendata.cbs.nl/statline/#/CBS/nl/dataset/{t2}/table"
    classes = {c["Key"]: c["Title"] for c in cbs_json(t2, "Vermogensklassen")}
    bounds = {}
    for k, title in classes.items():
        s = title.replace(".", "").replace(" ", "")
        nums = [int(x.replace("miljoen", "000000")) for x in re.findall(r"-?\d+(?:miljoen)?", s.replace("1miljoen", "1000000"))]
        if "%-groep" in title or k == "T001125":
            continue
        if title.startswith("Vermogen: tot"):
            bounds[k] = (None, nums[0])
        elif "ofmeer" in s:
            bounds[k] = (nums[0], None)
        elif len(nums) >= 2:
            bounds[k] = (nums[0], nums[1])
    years = sorted(p["Key"] for p in cbs_json(t2, "Perioden"))
    for group, pop, label in (("A025340", "age:0-24", "Households, main earner under 25"),
                              ("A025342", "age:25-34", "Households, main earner aged 25-34"),
                              ("A025347", "age:35-44", "Households, main earner aged 35-44"),
                              ("A025350", "age:45-54", "Households, main earner aged 45-54"),
                              ("A025354", "age:55-64", "Households, main earner aged 55-64"),
                              ("A025358", "age:65-74", "Households, main earner aged 65-74"),
                              ("A042086", "age:75-120", "Households, main earner aged 75+")):
        for y in reversed(years):
            rs = cbs_json(t2, f"TypedDataSet?$filter=KenmerkenVanHuishoudens eq '{group}' and Perioden eq '{y}'")
            cnt = {r["Vermogensklassen"]: r["ParticuliereHuishoudens_1"] for r in rs if r["Vermogensklassen"] in bounds and r["ParticuliereHuishoudens_1"]}
            if cnt:
                break
        order = sorted(cnt, key=lambda k: (bounds[k][0] if bounds[k][0] is not None else -1e12))
        tot = sum(cnt.values()); cum = 0.0; segs = []
        for k in order:
            lo, hi = bounds[k]; segs.append((cum / tot * 100, (cum + cnt[k]) / tot * 100, lo, hi)); cum += cnt[k]
        for p in range(1, 100):
            for a, b, lo, hi in segs:
                if a <= p <= b and lo is not None and hi is not None:
                    add("NL", "net_wealth", pop, label, p, lo + (hi - lo) * (p - a) / (b - a), "EUR", f"{y[:4]}-01",
                        f"CBS {t2} (wealth on 1 Jan {y[:4]}), interpolated within wealth classes", url2,
                        "Household wealth from tax records; pension rights and cars excluded.")
                    break


def scf():
    import pandas as pd, numpy as np
    html = get("https://www.federalreserve.gov/econres/scfindex.htm")
    y = max(re.findall(r'/econres/files/scfp(20\d\d)s\.zip', html))
    url = f"https://www.federalreserve.gov/econres/files/scfp{y}s.zip"
    z = zipfile.ZipFile(io.BytesIO(get(url, binary=True)))
    tmp = pathlib.Path(tempfile.mkdtemp()) / "scf.dta"
    tmp.write_bytes(z.read(z.namelist()[0]))
    d = pd.read_stata(tmp, columns=["wgt", "agecl", "networth", "retqliq", "income"])
    d["nw_ex"] = d["networth"] - d["retqliq"]
    def wpct(x, w, ps):
        o = np.argsort(x); x, w = x[o], w[o]; c = (np.cumsum(w) - 0.5 * w) / w.sum() * 100
        return np.interp(ps, c, x)
    ps = list(range(1, 100))
    src = f"US Federal Reserve SCF {y}"
    for pop, mask, label in (("all", d["agecl"] > 0, "All households"), ("age:0-34", d["agecl"] == 1, "Households, head under 35"),
                             ("age:35-44", d["agecl"] == 2, "Households, head aged 35-44"), ("age:45-54", d["agecl"] == 3, "Households, head aged 45-54"),
                             ("age:55-64", d["agecl"] == 4, "Households, head aged 55-64"), ("age:65-74", d["agecl"] == 5, "Households, head aged 65-74"),
                             ("age:75-120", d["agecl"] == 6, "Households, head aged 75+")):
        s = d[mask]
        for metric, col, ref_m, note in (
                ("net_wealth", "networth", f"{y}-07", "Net worth incl. retirement accounts (401k, IRA) and vehicles; Social Security and DB pensions excluded."),
                ("net_wealth_ex_ret", "nw_ex", f"{y}-07", "Net worth without retirement accounts: compare with your wealth without pensions."),
                ("hh_gross_income", "income", f"{int(y) - 1}-07", "Household income before tax, previous calendar year.")):
            for p, v in zip(ps, wpct(s[col].to_numpy(float), s["wgt"].to_numpy(float), ps)):
                add("US", metric, pop, label, p, v, "USD", ref_m, src, url, note)


def bls():
    ids = {10: "LEU0252911200A", 25: "LEU0252911300A", 50: "LEU0252881500A", 75: "LEU0252911400A", 90: "LEU0252911500A"}
    for p, sid in ids.items():
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}&cosd=2020-01-01"
        last = [r for r in csv.reader(io.StringIO(get(url))) if r and r[1] not in ("", ".")][-1]
        add("US", "earnings", "all", "Full-time wage and salary workers, all ages", p, float(last[1]) * 52, "USD", f"{last[0][:4]}-07",
            f"US BLS Current Population Survey {last[0][:4]} (via FRED)", f"https://fred.stlouisfed.org/series/{sid}",
            "Usual weekly earnings x 52, before tax.")
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=PSAVERT&cosd=2025-01-01"
    rs = [r for r in csv.reader(io.StringIO(get(url))) if r and r[1] not in ("", ".")][1:]
    last12 = rs[-12:]
    add("US", "saving_rate", "all", "National average", "", sum(float(r[1]) for r in last12) / len(last12) / 100, "pct",
        last12[-1][0][:7], "US BEA personal saving rate, last 12 months (via FRED)", "https://fred.stlouisfed.org/series/PSAVERT",
        "Personal saving as a share of disposable personal income (net of depreciation).")


if __name__ == "__main__":
    failed = []
    for f in (silc, ses, saving, hfcs, cbs, scf, bls):
        try:
            n0 = len(rows); f(); print(f.__name__, len(rows) - n0, "rows")
        except Exception as e:
            failed.append(f"{f.__name__}: {str(e)[:120]}")
    if failed:
        print("FAILED:", failed)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    META = OUT.with_name("peers_meta_raw.csv")
    if failed and OUT.exists() and META.exists():
        # keep last year's tables for any source that failed this time
        meta_old = {(r["country"], r["metric"], r["population"]): r for r in csv.DictReader(open(META))}
        have = {(r["country"], r["metric"], r["population"]) for r in rows}
        for r in csv.DictReader(open(OUT)):
            k = (r["country"], r["metric"], r["population"])
            if k not in have and k in meta_old:
                rows.append({**meta_old[k], "p": r["p"], "value": r["value"]})
    meta = {}
    for r in rows:
        meta.setdefault((r["country"], r["metric"], r["population"]), r)
    with open(OUT, "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["country", "metric", "population", "p", "value"])
        for r in rows: w.writerow([r["country"], r["metric"], r["population"], r["p"], r["value"]])
    mf = ["country", "country_name", "metric", "population", "pop_label", "currency", "ref_month", "source", "url", "note"]
    with open(META, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=mf, extrasaction="ignore"); w.writeheader(); w.writerows(meta.values())
    print(len(rows), "rows ->", OUT, "and", len(meta), "tables ->", META, "| failed:", failed or "none")
