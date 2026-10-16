#!/usr/bin/env python3
"""Test the four QA checks. Builds a good pack from the audit-program fixtures in a temporary
project root, checks everything passes, then plants one fault at a time (a bad figure, a
missing row, ...) and checks the right check fails. Quote checks use the real PDF and rules.
Run from the project root:   .venv/bin/python scripts/checks/test_checks.py
"""
import csv
import io
import json
import re
import shutil
import sys
import tempfile
import contextlib
from pathlib import Path

import openpyxl

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(PROJECT / ".claude/skills/audit-program"))
import build_pack  # noqa: E402
import check_numbers, check_quotes, check_samples, check_trace, run_checks  # noqa: E402

FX = PROJECT / ".claude/skills/audit-program/fixtures"
FAILS = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  {detail}"))
    if not cond:
        FAILS.append(name)


CHALLENGES = """# Challenges

| # | Round | Type | Risk | Challenge (citation and ask) | Planner response | Status | Checked in |
|---|---|---|---|---|---|---|---|
| 1 | 1 | sample | R-01 | [metric:$.tests.off_contract.count] T-01 draws only the top suppliers. Ask: add a spread test. | accepted | resolved | v2 T-04 |
| 2 | 1 | rating | R-02 | [history:OP-01] Score may be low. Ask: auditor to confirm. | for the auditor | for the auditor | - |
"""


def make_root(tmp, name):
    root = tmp / name
    (root / "outputs").mkdir(parents=True)
    for f in FX.iterdir():
        if f.name in ("make_fixtures.py", "__pycache__"):
            continue
        (shutil.copytree if f.is_dir() else shutil.copy)(f, root / "outputs" / f.name)
    o = root / "outputs"
    argv = ["--plan", o / "audit-plan.json", "--ratings", o / "risk-ratings.json", "--register", o / "risk-register.md",
            "--comments", o / "auditor-comments.md", "--analytics", o / "analytics.json", "--rules", o / "rules.json",
            "--history", o / "history.json", "--analytics-full", o / "analytics-full", "--out-dir", o]
    with contextlib.redirect_stdout(io.StringIO()):
        rc = build_pack.main([str(x) for x in argv])
    assert rc == 0, "fixture pack did not build"
    (o / "challenges.md").write_text(CHALLENGES, encoding="utf-8")
    # the council workbook: title row, header at excel row 2, data from row 3 (as the row ids say)
    (root / "data/spend").mkdir(parents=True)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Data to publish"
    ws.append(["West Berkshire Council: expenditure over £500"])
    ws.append(["Service", "Expenditure category", "Narrative", "Date", "Net amount", "Supplier name"])
    with open(o / "analytics-full/cleaned_spend.csv", newline="") as fh:
        for r in csv.DictReader(fh):
            ws.append([r["service"], r["category"], r["narrative"], r["date"], float(r["amount"]), r["supplier"]])
    wb.save(root / "data/spend/wb.xlsx")
    return root


def edit(root, rel, fn):
    p = root / rel
    p.write_text(fn(p.read_text(encoding="utf-8")), encoding="utf-8")


def run(mod, root, **kw):
    return mod.check(root, **kw)


tmp = Path(tempfile.mkdtemp())
try:
    real_quotes = check_quotes.check
    stub = lambda root: {"name": "check_quotes", "status": "PASS", "summary": "stub: quotes are tested below on the real PDF", "items": []}
    run_checks.check_quotes.check = stub  # the fixture rules are not the real rules
    good = make_root(tmp, "good")
    res = run_checks.run(good)
    check("good fixture: all four checks pass", all(r["status"] == "PASS" for r in res), [(r["name"], r["items"][:2]) for r in res if r["items"]])
    table = run_checks.render(res)
    check("run_checks prints one table and a verdict", table.count("| check_") == 4 and "VERDICT: ALL CHECKS PASS" in table, table)

    def planted(name, mod, fault, expect, **kw):
        root = make_root(tmp, re.sub(r"\W", "-", name))
        fault(root)
        r = run(mod, root, **kw)
        check(f"{name}: {mod.__name__} fails", r["status"] == "FAIL" and any(expect in i for i in r["items"]), r["items"][:3])
        others = [x["name"] for x in run_checks.run(root) if x["status"] == "FAIL"]
        check(f"{name}: run_checks verdict names it", mod.__name__ in others, others)

    # ---- check_numbers
    planted("planted bad figure with £", check_numbers, lambda r: edit(r, "outputs/planning-memo.md", lambda t: t + "\nA total of £99,999 was reviewed.\n"), "£99,999")
    planted("planted bad figure, three digits", check_numbers, lambda r: edit(r, "outputs/audit-program.md", lambda t: t + "\nAbout 4821 suppliers.\n"), "4821")
    root = make_root(tmp, "num-skips")
    edit(root, "outputs/planning-memo.md", lambda t: t + "\nSee wb|Data to publish|12 and T-01, clause 6.16, page 123, built 2026-10-16 09:02 UTC, 2024/25, [metric:$.tests.off_contract.count], `samples/T-01.csv`. A total of £90,000 and 30 payments.\n")
    check("numbers: row ids, ids, dates, years, clause/page refs, code and cited values are skipped or found",
          run(check_numbers, root)["status"] == "PASS", run(check_numbers, root)["items"])
    planted("missing document", check_numbers, lambda r: (r / "outputs/planning-memo.md").unlink(), "planning-memo.md not found")

    # ---- check_samples
    def sampled(r):
        with open(r / "outputs/samples/T-01.csv", newline="") as fh:
            return next(csv.DictReader(fh))["row_id"]

    def drop_spend_row(r):
        rid = sampled(r)
        edit(r, "outputs/analytics-full/cleaned_spend.csv", lambda t: "\n".join(l for l in t.splitlines() if not l.startswith(rid + ",")) + "\n")
    planted("planted missing row (cleaned spend)", check_samples, drop_spend_row, "not in cleaned_spend.csv")

    def bad_sheet_amount(r):
        n = int(sampled(r).rsplit("|", 1)[1])
        p = r / "data/spend/wb.xlsx"
        wb = openpyxl.load_workbook(p); ws = wb.active
        ws.cell(row=n, column=5).value = 1.0
        wb.save(p)
    planted("planted amount change in the workbook", check_samples, bad_sheet_amount, "workbook row has")

    def bad_sheet_supplier(r):
        n = int(sampled(r).rsplit("|", 1)[1])
        p = r / "data/spend/wb.xlsx"
        wb = openpyxl.load_workbook(p); ws = wb.active
        ws.cell(row=n, column=6).value = "Someone Else"
        wb.save(p)
    planted("planted supplier change in the workbook", check_samples, bad_sheet_supplier, "Someone Else")

    def row_not_in_sheet(r):  # the row exists in the spend file and samples, but the workbook has no such row
        rid = sampled(r)
        new = "wb|Data to publish|99"
        for f in [r / "outputs/analytics-full/cleaned_spend.csv", *(r / "outputs/samples").glob("*.csv")]:
            f.write_text(f.read_text().replace(rid + ",", new + ","))
    planted("planted row beyond the sheet", check_samples, row_not_in_sheet, "no such row in the workbook")
    planted("planted changed supplier in a sample", check_samples,
            lambda r: edit(r, "outputs/samples/T-02.csv", lambda t: t.replace("Supplier Number 0 Ltd", "Supplier Number 9 Ltd", 1)), "differ from cleaned_spend.csv")
    planted("row id in the program that does not exist", check_samples,
            lambda r: edit(r, "outputs/audit-program.md", lambda t: t + "\nSee wb|Data to publish|777.\n"), "wb|Data to publish|777")
    planted("workbook missing", check_samples, lambda r: (r / "data/spend/wb.xlsx").unlink(), "workbook not found")

    # ---- check_trace
    def edit_plan(fn):
        def f(r):
            p = r / "outputs/audit-plan.json"; d = json.loads(p.read_text()); fn(d); p.write_text(json.dumps(d))
        return f
    planted("rule dropped from not-tested list", check_trace, edit_plan(lambda d: d.update(rules_not_tested=[{"rule_ids": ["CPR-04"], "reason": "x"}])), "CPR-05: not cited")
    planted("not-tested rule has no reason", check_trace, edit_plan(lambda d: d["rules_not_tested"][0].update(reason="")), "CPR-04: not cited")
    planted("control with no test", check_trace, edit_plan(lambda d: d["risks"][0]["tests"][0].update(control_ids=["C-01"])), "C-02: control has no test")
    planted("approved risk missing from the plan", check_trace, edit_plan(lambda d: d["risks"].pop(1)), "R-02: approved but has no entry")
    planted("risk missing from the program", check_trace,
            lambda r: edit(r, "outputs/audit-program.md", lambda t: t.replace("## R-02:", "## R-two:")), "R-02: missing from audit-program.md")
    planted("risk missing from the matrix", check_trace,
            lambda r: edit(r, "outputs/risk-control-matrix.md", lambda t: "\n".join(l for l in t.splitlines() if not l.startswith("| R-02 |"))), "R-02: missing from risk-control-matrix.md")
    planted("open challenge", check_trace, lambda r: edit(r, "outputs/challenges.md", lambda t: t.replace("| resolved |", "| open |")), "status is still open")
    planted("challenge without evidence", check_trace,
            lambda r: edit(r, "outputs/challenges.md", lambda t: t.replace("[metric:$.tests.off_contract.count] T-01 draws only the top suppliers. Ask: add a spread test.", "Looks thin. Ask: do more.")), "no evidence cited")
    planted("no challenges file", check_trace, lambda r: (r / "outputs/challenges.md").unlink(), "challenges.md not found")
    planted("undecided risk (scope gate)", check_trace,
            lambda r: edit(r, "outputs/auditor-comments.md", lambda t: t.replace("| Approve | Reviewer: Test. |", "|  |  |")), "R-01: undecided")
    planted("rejection without a reason", check_trace,
            lambda r: edit(r, "outputs/auditor-comments.md", lambda t: t.replace("Covered by a separate AP review.", "")), "rejected without a comment")
    root = make_root(tmp, "interim")
    edit(root, "outputs/challenges.md", lambda t: t.replace("| resolved |", "| open |"))
    check("interim run skips the challenges closure only", run(check_trace, root, interim=True)["status"] == "PASS" and run(check_trace, root)["status"] == "FAIL")

    # ---- check_quotes: real PDF and rules
    run_checks.check_quotes.check = real_quotes
    rules = json.load(open(PROJECT / "outputs/rules.json"))
    q = next(r for r in rules["rules"] if r["rule_id"] == "CPR-59")["verbatim_quote"]

    def quote_root(name, register_line, mutate_rules=None):
        r = tmp / name
        (r / "outputs").mkdir(parents=True); (r / "data").mkdir()
        shutil.copy(PROJECT / "data/contract-rules.pdf", r / "data/contract-rules.pdf")
        d = json.loads(json.dumps(rules))
        if mutate_rules:
            mutate_rules(d)
        (r / "outputs/rules.json").write_text(json.dumps(d))
        (r / "outputs/risk-register.md").write_text("# Register\n\n" + register_line + "\n\n<!-- risk-register-state\n{}\n-->\n")
        return r
    ok = check_quotes.check(quote_root("q-ok", f"Rule CPR-59 requires “{q[:70]}” on spend."))
    check("quotes: current rules.json passes the verifier; a matching register excerpt passes", ok["status"] == "PASS" and "1 register excerpt" in ok["summary"], ok["items"])
    bad = check_quotes.check(quote_root("q-badex", "Rule CPR-59 requires “Invitations to quote must go to five suppliers always” on spend."))
    check("quotes: planted register excerpt that is not in rules.json fails", bad["status"] == "FAIL" and any("not in the verbatim_quote" in i for i in bad["items"]), bad["items"])
    bq = check_quotes.check(quote_root("q-badrule", "Nothing quoted.", lambda d: next(r for r in d["rules"] if r["rule_id"] == "CPR-59").update(verbatim_quote=q.replace("three", "five", 1))))
    check("quotes: planted altered quote in rules.json fails the verifier", bq["status"] == "FAIL" and any("verify_quotes.py" in i for i in bq["items"]), bq["items"][:3])
    bn = check_quotes.check(quote_root("q-blockq", "> A stray block quote with no rule named at all"))
    check("quotes: a block quote naming no rule fails", bn["status"] == "FAIL" and any("no rule id" in i for i in bn["items"]), bn["items"])
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("\nALL PASS" if not FAILS else f"\n{len(FAILS)} FAILED: {FAILS}")
sys.exit(1 if FAILS else 0)
