#!/usr/bin/env python3
"""Test build_pack.py on the synthetic fixtures (two in-scope risks, one rejected).
Run from the project root:
    .venv/bin/python .claude/skills/audit-program/test_build_pack.py
"""
import contextlib
import copy
import io
import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_pack as bp  # noqa: E402

FX = HERE / "fixtures"
FAILS = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  {detail}"))
    if not cond:
        FAILS.append(name)


def workdir(tmp, name):
    d = tmp / name
    shutil.copytree(FX, d, ignore=shutil.ignore_patterns("make_fixtures.py", "__pycache__"))
    return d


def build(d, plan=None, gate=False):
    if plan is not None:
        (d / "audit-plan.json").write_text(json.dumps(plan), encoding="utf-8")
    argv = ["--plan", d / "audit-plan.json", "--ratings", d / "risk-ratings.json", "--register", d / "risk-register.md",
            "--comments", d / "auditor-comments.md", "--analytics", d / "analytics.json", "--rules", d / "rules.json",
            "--history", d / "history.json", "--analytics-full", d / "analytics-full", "--out-dir", d / "out"]
    o, e = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(o), contextlib.redirect_stderr(e):
        rc = bp.main([str(x) for x in argv] + (["--gate"] if gate else []))
    return rc, o.getvalue(), e.getvalue()


def edit(d, name, fn):
    p = d / name
    p.write_text(fn(p.read_text(encoding="utf-8")), encoding="utf-8")


BASE = json.load(open(FX / "audit-plan.json"))
tmp = Path(tempfile.mkdtemp())
try:
    # 1. the good fixture builds
    d = workdir(tmp, "good")
    rc, so, se = build(d)
    out = d / "out"
    check("good fixture builds", rc == 0, se)
    check("scope: R-01 approved, R-02 amended, R-03 rejected and recorded", "in scope R-01, R-02 (1 approved, 1 amended)" in so and "rejected R-03" in so, so)
    memo = (out / "planning-memo.md").read_text(encoding="utf-8") if rc == 0 else ""
    check("memo: placeholders filled, rejected risk and reason recorded",
          "30 payments were analysed" in memo and "2 approved risks" in memo and "{{" not in memo and "R-03" in memo and "separate AP review" in memo, memo[:400])
    check("three documents + figures + samples written", all((out / f).exists() for f in (
        "planning-memo.md", "risk-control-matrix.md", "audit-program.md", "pack-figures.json", "samples/T-01.csv", "samples/T-02.csv", "samples/T-03.csv")))
    prog = (out / "audit-program.md").read_text(encoding="utf-8") if rc == 0 else ""
    check("risk text placeholders filled in the program", "£90,000" in prog and "{{" not in prog)
    check("audit program ends with the PBC list", prog.rstrip().split("\n## ")[-1].startswith("Request list (PBC)"))
    import pandas as pd
    spend = pd.read_csv(d / "analytics-full/cleaned_spend.csv")
    t1, t2, t3 = (pd.read_csv(out / f"samples/T-0{i}.csv") for i in (1, 2, 3))
    check("every sampled transaction exists in the spend file", all(df.row_id.isin(spend.row_id).all() for df in (t1, t2, t3)))
    check("score 6 -> size 20 (cap), T-01 n=3 suppliers x 2 rows", t1.item_rank.nunique() == 3 and len(t1) == 6 and bp.size_for(8) == 20 and bp.size_for(6) == 20)
    check("top-n by sort: largest annualised first", list(t1.drop_duplicates("item_rank").supplier)[:1] == ["Supplier Number 0 Ltd"])
    check("group file expands row_ids", set(t3.row_id) <= set(spend.row_id) and len(t3) == 4)
    check("spread method picks evenly through the list", t2.item_rank.nunique() == 5)
    fig = json.load(open(out / "pack-figures.json"))
    check("figures recorded with source", any(f["source"] == "analytics.json" and f["key"] == "$.population.rows_analysed" for f in fig["figures"])
          and any(f["source"].startswith("computed") for f in fig["figures"]) and fig["computed"]["scope.rules_total"] == 5)
    first = {f.name: f.read_text() for f in out.rglob("*") if f.is_file() and f.name != "pack-figures.json"}
    shutil.rmtree(out); rc2, _, _ = build(d)
    check("deterministic: a re-run writes identical files, ignoring the timestamp",
          rc2 == 0 and all(__import__("re").sub(r"built [\d\- :]+UTC", "", first[f.name]) == __import__("re").sub(r"built [\d\- :]+UTC", "", f.read_text())
                           for f in out.rglob("*") if f.is_file() and f.name != "pack-figures.json"))

    # 2. the three required failures
    def plan_fail(name, mutate, expect, files=None):
        d = workdir(tmp, name)
        p = copy.deepcopy(BASE); mutate(p)
        rc, so, se = build(d, p)
        check(f"fails: {name}", rc == 1 and expect in se and not (d / "out" / "planning-memo.md").exists(), se)

    plan_fail("missing risk", lambda p: p["risks"].pop(1), "R-02: approved but missing from the plan")
    plan_fail("uncited control", lambda p: p["risks"][0]["controls"][1].update(description="Awards are advertised."), "C-02: control cites no rule")
    plan_fail("unaccounted rule", lambda p: p.update(rules_not_tested=[{"rule_ids": ["CPR-04"], "reason": "Documents only."}]),
              "CPR-05: rule is not cited by any risk, control or test and is not listed as not tested")

    # 3. further plan faults
    plan_fail("control without a test", lambda p: p["risks"][0]["tests"][0].update(control_ids=["C-01"]), "C-02: control has no test step")
    plan_fail("test cites nothing", lambda p: p["risks"][0]["tests"][0].update(step="Obtain evidence."), "T-01: test step cites no rule or metric")
    plan_fail("unresolved citation", lambda p: p["memo"].update(approach="See [metric:$.tests.nope.count] and [rule:CPR-02]."), "does not resolve")
    plan_fail("bad placeholder", lambda p: p["memo"].update(background="Total {{$.tests.nope}}."), "placeholder")
    plan_fail("sample bigger than score size", lambda p: p["risks"][0]["tests"][0]["sample"].update(n=21), "exceeds 20")
    plan_fail("sample filter matches nothing", lambda p: p["risks"][0]["tests"][0]["sample"].update(filter=[{"col": "primary_tag", "op": "==", "value": "grant"}]), "matches no rows")
    plan_fail("pbc not requested", lambda p: p["pbc_items"].append({"id": "PBC-09", "item": "Extra."}), "PBC-09: PBC item is not needed")
    plan_fail("risk not approved", lambda p: p["risks"].append({**copy.deepcopy(p["risks"][0]), "risk_id": "R-03"}), "R-03: in the plan but not an approved risk")
    plan_fail("accusatory language", lambda p: p["risks"][0].update(rationale="This suggests fraud."), "accusatory word 'fraud'")
    plan_fail("supplier named", lambda p: p["memo"].update(approach="Start with Supplier Number 3 Ltd [rule:CPR-02]."), "names a supplier")
    plan_fail("rule both cited and not tested", lambda p: p["rules_not_tested"].append({"rule_ids": ["CPR-01"], "reason": "x"}), "listed as not tested but also cited")

    # sampled transaction missing from the spend file
    d = workdir(tmp, "missing-tx")
    edit(d, "analytics-full/cleaned_spend.csv", lambda t: "\n".join(l for l in t.splitlines() if "|Data to publish|3," not in l and not l.startswith("wb|Data to publish|3,")))
    rc, so, se = build(d)
    check("fails: sampled transaction not in cleaned_spend.csv", rc == 1 and "not in cleaned_spend.csv" in se and not (d / "out" / "samples").exists(), se)

    # 4. gate
    d = workdir(tmp, "gate-ok")
    rc, so, se = build(d, gate=True)
    check("--gate passes alone and writes nothing", rc == 0 and "GATE PASS" in so and not (d / "out").exists(), so + se)
    d = workdir(tmp, "gate-undecided")
    edit(d, "auditor-comments.md", lambda t: t.replace("| Approve | Reviewer: Test. |", "|  |  |"))
    rc, so, se = build(d, gate=True)
    check("--gate fails on an undecided risk", rc == 1 and "R-01: undecided" in se, se)
    d = workdir(tmp, "gate-rev0")
    edit(d, "risk-register.md", lambda t: t.replace('"round": 1', '"round": 0'))
    rc, so, se = build(d, gate=True)
    check("--gate fails when the register is not a revision", rc == 1 and "not a revision" in se, se)
    d = workdir(tmp, "gate-reject-in-register")
    edit(d, "auditor-comments.md", lambda t: t.replace("| Approve |", "| Reject |"))
    rc, so, se = build(d, gate=True)
    check("--gate fails when a rejected risk is still in the register", rc == 1 and "rejected" in se and "still in the register" in se, se)
    d = workdir(tmp, "gate-override")
    edit(d, "auditor-comments.md", lambda t: t.replace("L=2", "L=5"))
    rc, so, se = build(d, gate=True)
    check("--gate fails when an Amend override is not in the register", rc == 1 and "auditor set L=5" in se, se)
    d = workdir(tmp, "gate-reject-nocomment")
    edit(d, "auditor-comments.md", lambda t: t.replace("Covered by a separate AP review.", ""))
    rc, so, se = build(d, gate=True)
    check("--gate fails on a rejection with no recorded reason", rc == 1 and "rejected without a comment" in se, se)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("\nALL PASS" if not FAILS else f"\n{len(FAILS)} FAILED: {FAILS}")
sys.exit(1 if FAILS else 0)
