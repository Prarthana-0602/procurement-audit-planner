"""Independent self-check: re-derive the first item of each test list from raw sources. Does not import analysis code."""
import csv, glob, json, os, re, sys
from datetime import datetime, timedelta
import openpyxl

OUT = "outputs/analytics-full"
A = json.load(open("outputs/analytics.json"))
R = json.load(open("outputs/rules.json"))
results, failed = {}, False

def pen(x): return round(float(x), 2)

# --- raw spend, loaded independently
raw = {}
for f in sorted(glob.glob("data/spend/*.xlsx")):
    ws = openpyxl.load_workbook(f, read_only=True, data_only=True)["Data to publish"]
    stem = os.path.splitext(os.path.basename(f))[0]
    for n, r in enumerate(ws.iter_rows(values_only=True), 1):
        if r and r[0] == "Service": continue
        if r is None or all(c is None for c in r[:6]): continue
        raw[f"{stem}|Data to publish|{n}"] = {"service": r[0], "narr": r[2], "date": r[3], "amt": r[4], "sup": (r[5] or "")}
excluded = {row["row_id"] for row in csv.DictReader(open(f"{OUT}/excluded_rows.csv"))}

def nm(s):
    s = re.sub(r"[^\w\s]|_", " ", str(s).upper())
    s = re.sub(r"\b(LTD|LIMITED|PLC|LLP)\b", " ", s)
    return " ".join(s.split())

months = len({(v["date"].year, v["date"].month) for k, v in raw.items() if k not in excluded})
FACTOR = 12 / months
def sup_rows(key): return [k for k, v in raw.items() if k not in excluded and nm(v["sup"]) == key]
def sup_total(key): return pen(sum(raw[k]["amt"] for k in sup_rows(key)))

def rule_amount(clause, typ):
    for x in R["rules"]:
        if x["clause"] == clause and x["type"] == typ and x["threshold_low"]: return x["threshold_low"]["amount"]
QT = rule_amount("Appendix B row B1", "procedure"); NT = rule_amount("Appendix B row B1", "advertising")

def first(name): return next(csv.DictReader(open(f"{OUT}/{name}.csv")))
def rec(test, item, expected, recomputed, ok):
    global failed
    results[test] = {"item": item, "expected": expected, "recomputed": recomputed, "result": "pass" if ok else "fail"}
    failed |= not ok

# notices, fresh parse
notices = []
if os.path.exists("data/contracts.csv"):
    with open("data/contracts.csv", encoding="utf-8-sig", newline="") as fh:
        rd = csv.DictReader(fh); sc = [c for c in rd.fieldnames if c.startswith("Supplier [Name|")][0]
        for row in rd:
            if row["Organisation Name"].strip().lower() not in ("west berkshire council", "west berkshire"): continue
            for b in re.split(r"\]\s*\[", row[sc].strip()):
                b = b.strip().strip("[]")
                if b: notices.append((row, b.split("|")[0].strip(), len(re.split(r"\]\s*\[", row[sc].strip()))))
ws_ = datetime.fromisoformat(A["window"]["start"]); we_ = datetime.fromisoformat(A["window"]["end"])
d_ = lambda s: datetime.strptime(s, "%d/%m/%Y")
def nstatus(row):
    if d_(row["Contract start date"]) > we_: return "future"
    if d_(row["Contract end date"]) < ws_: return "expired"
    return "live"

# 1 clustering
r = first("threshold_clustering"); T = float(r["tier"]); v = raw[r["row_id"]]
excl_start = T in {x["threshold_low"]["amount"] for x in R["rules"] if x["threshold_low"] and x["threshold_low"]["inclusive"] is False}
ok = v["sup"] == r["supplier"] and pen(v["amt"]) == pen(r["amount"]) and 0.9 * T <= v["amt"] <= T and (v["amt"] < T or excl_start)
top = A["tests"]["threshold_clustering"]["top20"][0]
ok &= top["row_id"] == r["row_id"] and pen(top["amount"]) == pen(v["amt"])
rec("threshold_clustering", r["row_id"], pen(r["amount"]), pen(v["amt"]), ok)

# 2 split
r = first("split_purchases"); ids = r["row_ids"].split(";"); T = float(r["tier"])
vs = sorted((raw[i] for i in ids), key=lambda x: x["date"]); tot = pen(sum(x["amt"] for x in vs))
span = (vs[-1]["date"] - vs[0]["date"]).days
ok = len(ids) >= 2 and span <= 30 and all(x["amt"] <= T for x in vs) and tot == pen(r["total_gbp"]) and tot >= T and len({nm(x["sup"]) for x in vs}) == 1
ok &= pen(A["tests"]["split_purchases"]["top20"][0]["total_gbp"]) == tot
rec("split_purchases", ids, pen(r["total_gbp"]), tot, ok)

# 3 off_contract
if A["tests"]["off_contract"]["status"] == "ran":
    r = first("off_contract"); k = r["norm_supplier"]; tot = sup_total(k)
    matched = any(nm(n[1]) == k for n in notices)
    ok = tot == pen(r["gbp"]) and pen(tot * FACTOR) == pen(r["annualised_estimate"]) and tot * FACTOR > NT and not matched
    ok &= pen(A["tests"]["off_contract"]["top20"][0]["annualised_estimate"]) == pen(tot * FACTOR)
    rec("off_contract", k, pen(r["annualised_estimate"]), pen(tot * FACTOR), ok)
else: results["off_contract"] = {"result": "skipped"}

# 4 duplicates
r = first("duplicates"); ids = r["row_ids"].split(";"); vs = sorted((raw[i] for i in ids), key=lambda x: x["date"])
ok = len({nm(x["sup"]) for x in vs}) == 1 and len({pen(x["amt"]) for x in vs}) == 1
gaps = [(vs[i + 1]["date"] - vs[i]["date"]).days for i in range(len(vs) - 1)]
ok &= all(g <= 7 for g in gaps)
same = len({x["date"] for x in vs}) == 1
ok &= (same == (r["group"] == "same_timestamp")) and pen(vs[0]["amt"] * (len(vs) - 1)) == pen(r["gbp_repeat"])
rec("duplicates", ids, pen(r["gbp_repeat"]), pen(vs[0]["amt"] * (len(vs) - 1)), ok)

# 5 expired
if A["tests"]["expired_notice_spend"]["status"] == "ran":
    r = first("expired_notice_spend"); k = r["norm_supplier"]
    ms = [n for n in notices if nm(n[1]) == k]
    ok = bool(ms) and all(nstatus(n[0]) == "expired" for n in ms) and sup_total(k) == pen(r["gbp"])
    latest = max(d_(n[0]["Contract end date"]) for n in ms).date().isoformat()
    ok &= latest == r["latest_notice_end"] and latest < A["window"]["start"]
    rec("expired_notice_spend", k, r["latest_notice_end"], latest, ok)
else: results["expired_notice_spend"] = {"result": "skipped"}

# 6 spend_vs_award
if A["tests"]["spend_vs_award"]["status"] == "ran":
    if A["tests"]["spend_vs_award"]["count"] == 0: results["spend_vs_award"] = {"result": "skipped", "reason": "no flagged items"}
    else:
        r = first("spend_vs_award"); k = r["norm_supplier"]
        ms = [n for n in notices if nm(n[1]) == k and nstatus(n[0]) == "live"]
        row, _, nsup = ms[0]
        yrs = (d_(row["Contract end date"]) - d_(row["Contract start date"])).days / 365.25
        ratio = sup_total(k) * FACTOR / (float(row["Awarded Value"]) / yrs)
        ok = len({n[0]["Notice Identifier"] for n in ms}) == 1 and nsup == 1 and abs(ratio - float(r["ratio"])) < 1e-3 and ratio >= 1.25
        rec("spend_vs_award", row["Notice Identifier"], float(r["ratio"]), round(ratio, 4), ok)
else: results["spend_vs_award"] = {"result": "skipped"}

# 7 high value
r = first("high_value_suppliers"); k = r["norm_supplier"]; tot = sup_total(k)
ok = tot == pen(r["gbp"]) and pen(tot * FACTOR) == pen(r["annualised_estimate"]) and tot * FACTOR > QT
ok &= pen(A["tests"]["high_value_suppliers"]["top20"][0]["annualised_estimate"]) == pen(tot * FACTOR)
rec("high_value_suppliers", k, pen(r["annualised_estimate"]), pen(tot * FACTOR), ok)

out = {"status": "failed" if failed else "passed", "generated_at": datetime.now().isoformat(timespec="seconds"),
       "quote_tier": QT, "notice_tier": NT, "annualise_factor": FACTOR, "tests": results}
json.dump(out, open("outputs/analytics-selfcheck.json", "w"), indent=1, default=str)
A["selfcheck"]["status"] = out["status"]; json.dump(A, open("outputs/analytics.json", "w"), indent=1)
print(out["status"], {k: v["result"] for k, v in results.items()})
sys.exit(1 if failed else 0)
