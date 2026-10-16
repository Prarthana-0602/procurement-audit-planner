#!/usr/bin/env python3
"""Traceability check.
 1. Every rule in rules.json is cited by a rated risk, a control or a test, or is listed in
    audit-plan.json as not tested with a reason; and appears in risk-control-matrix.md.
 2. Every approved in-scope risk (build_pack.py's gate: register + auditor-comments.md)
    has a control, every control has a test, and the risk appears in the matrix and the program.
 3. Every High (or Extreme) risk in the register is in scope; every rejected risk has a
    recorded reason in auditor-comments.md.
 4. challenges.md exists, every row cites evidence and none is open (skipped with --interim,
    for runs made while the challenger is still working).
    .venv/bin/python scripts/checks/check_trace.py [--root DIR] [--interim]
"""
import importlib.util
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROJECT, cli, read_json, read_text, result  # noqa: E402

CITE = re.compile(r"\[(rule|metric|history):([^\]\s]+)\]")
EVIDENCE = re.compile(r"\[(?:rule|metric|history):[^\]]+\]|\b(?:CPR|OP|FU|RT|GAP|DISC|T|C|PBC|R)-\d+\b|\.csv\b|\$\.[\w.]+")
STATUSES = {"open", "resolved", "declined", "for the auditor"}
HIGH = {"high", "extreme", "very high"}


def load_builder():
    p = PROJECT / ".claude" / "skills" / "audit-program" / "build_pack.py"
    spec = importlib.util.spec_from_file_location("build_pack_for_qa", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def rules_of(text):
    return {ref for k, ref in CITE.findall(text or "") if k == "rule"}


def plan_text(rk):
    out = []
    for c in rk.get("controls") or []:
        out.append(c.get("description", ""))
    for t in rk.get("tests") or []:
        out.append(t.get("step", ""))
    return out


def check_challenges(root, items):
    text = read_text(root / "outputs" / "challenges.md", items, "challenges.md")
    if text is None:
        return
    rows, cols = [], None
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cols is None:
            if "Status" in cells and "#" in cells:
                cols = {c.lower(): i for i, c in enumerate(cells)}
            continue
        if set("".join(cells)) <= set("-: "):
            continue
        rows.append(cells)
    if cols is None:
        items.append("challenges.md: no challenge table with '#' and 'Status' columns")
        return
    ci = next((i for k, i in cols.items() if k.startswith("challenge")), None)
    for cells in rows:
        num = cells[cols["#"]] if cols["#"] < len(cells) else "?"
        status = cells[cols["status"]].lower() if cols["status"] < len(cells) else ""
        if status == "open":
            items.append(f"challenges.md #{num}: status is still open")
        elif status not in STATUSES:
            items.append(f"challenges.md #{num}: status {status!r} is not one of {sorted(STATUSES)}")
        if ci is None or ci >= len(cells) or not EVIDENCE.search(cells[ci]):
            items.append(f"challenges.md #{num}: no evidence cited (rule, metric, history item, or pack item id)")


def check(root, interim=False):
    items = []
    out = root / "outputs"
    bp = load_builder()
    gate_errors, scope = bp.gate(out / "risk-register.md", out / "auditor-comments.md", out / "risk-ratings.json")
    items += [f"scope: {e}" for e in gate_errors]
    rules = read_json(out / "rules.json", items, "rules.json")
    plan = read_json(out / "audit-plan.json", items, "audit-plan.json")
    ratings = read_json(out / "risk-ratings.json", items, "risk-ratings.json")
    matrix = read_text(out / "risk-control-matrix.md", items)
    program = read_text(out / "audit-program.md", items)
    if rules and plan is not None and ratings is not None:
        approved = {r["id"] for r in scope["approved"]}
        # 1. every rule traced
        cited = set()
        for r in ratings.get("risks", []):
            if r["id"] in approved:
                cited |= rules_of(" ".join(str(x) for x in [r.get("title"), r.get("description"), r.get("proposed_focus"),
                                                              (r.get("likelihood") or {}).get("justification"),
                                                              (r.get("impact") or {}).get("justification")] + list(r.get("evidence") or [])))
        for rk in plan.get("risks", []):
            for t in plan_text(rk):
                cited |= rules_of(t)
        listed = {}
        for n in plan.get("rules_not_tested") or []:
            for rid in n.get("rule_ids") or []:
                listed[rid] = (n.get("reason") or "").strip()
        for rule in rules["rules"]:
            rid = rule["rule_id"]
            if rid not in cited and not listed.get(rid):
                items.append(f"{rid}: not cited by a rated risk, control or test, and not listed as not tested with a reason")
            if matrix is not None and not re.search(rf"\|\s*{rid}\s*\|", matrix):
                items.append(f"{rid}: missing from risk-control-matrix.md")
        # 2. approved risks fully traced
        by_plan = {rk.get("risk_id"): rk for rk in plan.get("risks", [])}
        for rid in sorted(approved):
            rk = by_plan.get(rid)
            if rk is None:
                items.append(f"{rid}: approved but has no entry in audit-plan.json")
                continue
            tests = rk.get("tests") or []
            if not rk.get("controls"):
                items.append(f"{rid}: no control")
            for c in rk.get("controls") or []:
                if not any(c.get("id") in (t.get("control_ids") or []) for t in tests):
                    items.append(f"{rid}/{c.get('id')}: control has no test")
            if matrix is not None and not re.search(rf"\|\s*{rid}\s*\|", matrix):
                items.append(f"{rid}: missing from risk-control-matrix.md")
            if program is not None and not re.search(rf"^##\s*{rid}\b", program, re.M):
                items.append(f"{rid}: missing from audit-program.md")
    # 3. High risks in scope; exclusions recorded
    try:
        _, rows, _ = bp.read_register(out / "risk-register.md")
        in_scope = {r["id"] for r in scope["approved"]}
        for rid, r in rows.items():
            if r["band"].lower() in HIGH and rid not in in_scope:
                items.append(f"{rid}: {r['band']} risk is not in scope and no recorded exclusion reason applies (see scope problems)")
    except Exception as e:  # missing or malformed register is already reported by the gate
        if not gate_errors:
            items.append(f"register: {e}")
    for rj in scope["rejected"]:
        if not rj["comment"].strip():
            items.append(f"{rj['id']}: rejected with no recorded reason")
    # 4. challenges
    if not interim:
        check_challenges(root, items)
    note = " (interim: challenges.md closure not checked)" if interim else ""
    return result("check_trace", items, f"rules, approved risks, High risks and challenges all trace{note}"
                  if not interim else f"rules, approved risks and High risks trace{note}")


if __name__ == "__main__":
    sys.exit(cli(check, __doc__.split("\n\n")[0],
                 {"--interim": {"action": "store_true", "help": "skip the challenges.md closure check"}}))
