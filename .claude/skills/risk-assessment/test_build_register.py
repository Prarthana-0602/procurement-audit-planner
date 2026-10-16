#!/usr/bin/env python3
"""Test build_register.py on the fixtures (one good risk R-01, one broken risk R-02)
and on the revision rules. Run from the project root:
    .venv/bin/python .claude/skills/risk-assessment/test_build_register.py
"""
import contextlib
import copy
import io
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_register as br  # noqa: E402

FX = HERE / "fixtures"
BASE = json.load(open(FX / "risk-ratings.json"))
FAILS = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  {detail}"))
    if not cond:
        FAILS.append(name)


def build(ratings, out, argv_extra=()):
    argv = ["--ratings", str(out / "ratings.json"), "--analytics", str(FX / "analytics.json"),
            "--rules", str(FX / "rules.json"), "--history", str(FX / "history.json"), "--out-dir", str(out)]
    (out / "ratings.json").write_text(json.dumps(ratings), encoding="utf-8")
    o, e = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(o), contextlib.redirect_stderr(e):
        rc = br.main(argv)
    return rc, o.getvalue(), e.getvalue()


def good_only():
    r = copy.deepcopy(BASE)
    r["risks"] = [r["risks"][0]]
    return r


def second(r):
    """Add a second good risk R-03 (one indicator test, no uplift: rubric 2)."""
    x = copy.deepcopy(r["risks"][0])
    x.update(id="R-03", title="Payments to one supplier repeated close together")
    x["likelihood"] = {"score": 2, "justification": "One indicator test fires: {{$.tests.duplicates.counts}} repeat payments [metric:$.tests.duplicates.counts]."}
    x.pop("repeat_finding")
    r["risks"].append(x)
    return r


def set_decisions(out, table):
    p = out / "auditor-comments.md"
    lines = []
    for line in p.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\| (R-\d+) \|", line)
        if m and m.group(1) in table:
            cols = line.strip().strip("|").split("|")
            cols[3], cols[4] = f" {table[m.group(1)][0]} ", f" {table[m.group(1)][1]} "
            line = "|" + "|".join(cols) + "|"
        lines.append(line)
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")


tmp = Path(tempfile.mkdtemp())
try:
    # 1. good + broken fixture
    out = tmp / "a"; out.mkdir()
    rc, so, se = build(BASE, out)
    reg = (out / "risk-register.md").read_text(encoding="utf-8")
    check("fixture builds", rc == 0, se)
    check("good risk kept, with matrix score 16 Extreme", "### R-01" in reg and "**Score 16, Extreme**" in reg)
    check("broken risk dropped and listed", "### R-02" not in reg and "EXCLUDED R-02" in so and "## Excluded risks" in reg)
    check("placeholders filled from analytics", "628 suppliers" in reg and "£248,804,592" in reg and "{{" not in reg.split("## Risks")[1].split("## Excluded")[0])
    check("uplift stated explicitly", "repeat-finding uplift +1" in reg)
    check("conflicts stated in header", "Conflicts in the scoring method" in reg and "MARKED, not used" in reg and "DISC-03" in reg)
    check("typed figure warned", "figure typed in prose" in so)
    check("register ends with Auditor decisions", reg.split("<!-- risk-register-state")[0].rstrip().split("\n## ")[-1].startswith("Auditor decisions"))
    com = (out / "auditor-comments.md").read_text(encoding="utf-8")
    check("comments template: one row per rated risk, blank decision", "| R-01 |" in com and "R-02" not in com and re.search(r"\| R-01 \|.*\|  \|  \|$", com.strip().splitlines()[-1]))

    # 2. each planted fault drops only that risk
    def planted(name, mutate, expect):
        d = tmp / name; d.mkdir()
        r = good_only(); mutate(r["risks"][0])
        rc, so, se = build(r, d)
        check(f"drop: {name}", "EXCLUDED R-01" in so and expect in so, so + se)
    planted("no-citation", lambda x: x["impact"].update(justification="Bad outcome likely."), "impact justification has no resolvable citation")
    planted("bad-placeholder", lambda x: x["evidence"].append("Count {{$.tests.off_contract.nope}}."), "placeholder")
    planted("rubric-mismatch", lambda x: (x.pop("repeat_finding"), x["likelihood"].update(score=5)), "does not follow the rubric")
    planted("uplift-not-adverse", lambda x: x["repeat_finding"].update(history=["OP-01"]), "not adverse")
    planted("uplift-not-audit", lambda x: x["repeat_finding"].update(history=["DISC-01"]), "not an audit opinion")
    d = tmp / "ov"; d.mkdir(); r = good_only(); r["risks"][0].pop("repeat_finding"); r["risks"][0]["likelihood"].update(score=4, rubric_override={"score": 4, "reason": "Auditor-style judgment for test"})
    rc, so, se = build(r, d)
    check("rubric_override with reason accepted and shown", rc == 0 and "rubric override to 4" in (d / "risk-register.md").read_text(encoding="utf-8"))

    # 3. comments are kept when rewritten (draft re-run)
    set_decisions(out, {"R-01": ("", "keep this note")})
    rc, so, se = build(good_only(), out)
    check("comment text survives a rebuild", "keep this note" in (out / "auditor-comments.md").read_text(encoding="utf-8"))

    # 4. revision flow
    def fresh(name):
        d = tmp / name; d.mkdir()
        build(second(good_only()), d)
        return d

    d = fresh("rev-ok")
    set_decisions(d, {"R-01": ("Approve", "fine"), "R-03": ("Amend", "I=3 raise the impact? use L=2")})
    r = second(good_only()); r["risks"][1]["impact"]["score"] = 3
    r["risks"][1]["impact"]["justification"] += " Amended."
    r["revision"] = {"summary": "Applied auditor amendment.", "changes": [{"risk_id": "R-03", "field": "impact", "reason": "Auditor asked for I=3"}]}
    rc, so, se = build(r, d)
    reg = (d / "risk-register.md").read_text(encoding="utf-8")
    check("revision applied, header names change", rc == 0 and "## Revision 1: what changed" in reg and "R-03 | impact" in reg, so + se)
    check("override marked", "**AUDITOR OVERRIDE**" in reg and "**(auditor override)**" in reg)
    check("approved risk listed unchanged", "Approved, unchanged: R-01" in reg)
    rc2, so2, se2 = build(r, d)  # re-run with nothing pending is stable
    check("re-run after applying is stable", rc2 == 0 and "revision 1" in so2, so2 + se2)

    def revision_fail(name, decisions, mutate, expect):
        d = fresh(name)
        set_decisions(d, decisions)
        r = second(good_only()); mutate(r)
        before = (d / "risk-register.md").read_text(encoding="utf-8")
        rc, so, se = build(r, d)
        check(f"revision fails: {name}", rc == 1 and expect in se and (d / "risk-register.md").read_text(encoding="utf-8") == before, se)

    claim = lambda rid, f: {"summary": "x", "changes": [{"risk_id": rid, "field": f, "reason": "r"}]}
    both = {"R-01": ("Approve", ""), "R-03": ("Approve", "")}
    revision_fail("undecided", {"R-01": ("Approve", "")}, lambda r: r.update(revision={"summary": "x", "changes": []}), "undecided")
    revision_fail("no revision block", both, lambda r: None, "no 'revision' block")
    revision_fail("unrequested change", both, lambda r: (r["risks"][1].update(proposed_focus="Different focus."), r.update(revision=claim("R-03", "proposed_focus"))), "unrequested change")
    revision_fail("undeclared change", {"R-01": ("Approve", ""), "R-03": ("Amend", "tighten focus")},
                  lambda r: (r["risks"][1].update(proposed_focus="Different focus."), r.update(revision={"summary": "x", "changes": []})), "not declared")
    revision_fail("amend not applied", {"R-01": ("Approve", ""), "R-03": ("Amend", "tighten focus")}, lambda r: r.update(revision={"summary": "x", "changes": []}), "nothing changed")
    revision_fail("reject not applied", {"R-01": ("Approve", ""), "R-03": ("Reject", "no")}, lambda r: r.update(revision={"summary": "x", "changes": []}), "still in risk-ratings.json")
    revision_fail("override not applied", {"R-01": ("Approve", ""), "R-03": ("Amend", "set I=5")},
                  lambda r: (r["risks"][1]["evidence"].append("More."), r.update(revision=claim("R-03", "evidence"))), "override I=5 not applied")
    revision_fail("new risk", both, lambda r: (r["risks"].append({**copy.deepcopy(r["risks"][1]), "id": "R-09"}), r.update(revision={"summary": "x", "changes": []})), "new risk")
    revision_fail("approved risk silently removed", both, lambda r: (r["risks"].pop(1), r.update(revision={"summary": "x", "changes": []})), "removed from risk-ratings.json")
    revision_fail("false claim", both, lambda r: r.update(revision=claim("R-03", "title")), "did not")

    d = fresh("rev-reject")
    set_decisions(d, {"R-01": ("Approve", ""), "R-03": ("Reject", "out of scope")})
    r = good_only(); r["revision"] = {"summary": "Removed R-03 as rejected.", "changes": []}
    rc, so, se = build(r, d)
    reg = (d / "risk-register.md").read_text(encoding="utf-8")
    check("reject removes risk, records it", rc == 0 and "### R-03" not in reg and "## Rejected by the auditor" in reg
          and "| R-03 |" in (d / "auditor-comments.md").read_text(encoding="utf-8"), so + se)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("\nALL PASS" if not FAILS else f"\n{len(FAILS)} FAILED: {FAILS}")
sys.exit(1 if FAILS else 0)
