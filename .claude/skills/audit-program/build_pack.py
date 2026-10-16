#!/usr/bin/env python3
"""Build the audit pack from the planner's judgments (outputs/audit-plan.json).

The planner supplies judgment: controls, test steps, sample recipes, PBC items.
This script supplies everything checkable: the approved scope (from
auditor-comments.md and the register), every citation and figure, the sample
draws, the existence check of each sampled transaction, the rule coverage check,
and the three rendered documents. On any failure it prints every problem and
writes nothing.

    .venv/bin/python .claude/skills/audit-program/build_pack.py          # build the pack
    .venv/bin/python .claude/skills/audit-program/build_pack.py --gate   # only the scope gate
"""
import argparse
import datetime
import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / ".claude" / "skills" / "risk-assessment"))
import build_register as br  # noqa: E402  (citation, placeholder and decision helpers are shared)

Fatal = br.Fatal
SIZE_BANDS = [(15, 40), (10, 30), (5, 20), (1, 10)]  # score >= first -> items drawn per sample
MAX_ROWS_PER_ITEM = 5
OPS = {"==", "!=", ">", ">=", "<", "<=", "in", "contains"}
AT_RE = re.compile(r"\{\{\s*@([\w.\-]+)\s*\}\}")
SUMMARY_ROW = re.compile(r"^\|\s*(R-[\w-]+)\s*\|(.*)\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|\s*$")
BANNED = re.compile(r"\b(fraud\w*|corrupt\w*|misconduct|illegal\w*|unlawful\w*|embezzl\w*|theft|stolen|collu\w*|"
                    r"kickbacks?|brib\w*)\b", re.I)
SAMPLE_COLS = ["test_id", "risk_id", "item_rank", "item_key", "row_id", "date", "service", "category",
               "narrative", "amount", "supplier", "tag"]


def size_for(score):
    return next(n for lo, n in SIZE_BANDS if score >= lo)


def norm(s):
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z0-9 ]", " ", str(s).upper())).strip()


def cell(s):
    return re.sub(r"\s+", " ", str(s)).replace("|", "/").strip()


# ------------------------------------------------------------------ gate
def read_register(path):
    """(round, {risk_id: {title, L, I, score, band}}) from the register built by build_register.py."""
    if not path.exists():
        raise Fatal(f"register not found: {path}; run the risk-assessor first")
    text = path.read_text(encoding="utf-8")
    m = br.STATE_RE.search(text)
    if not m:
        raise Fatal("register has no builder state comment; it was not built by build_register.py")
    state = json.loads(m.group(1))
    rows = {}
    for line in text.split("<!-- risk-register-state")[0].splitlines():
        r = SUMMARY_ROW.match(line)
        if r:
            title = r.group(2).strip().strip("|").strip()
            rows[r.group(1)] = {"title": title, "L": int(r.group(3)), "I": int(r.group(4)),
                                "score": int(r.group(5)), "band": r.group(6)}
    if set(rows) != set(state["risks"]):
        raise Fatal(f"register summary table {sorted(rows)} does not match its state {sorted(state['risks'])}")
    return state["round"], rows, state.get("rejected", {})


def gate(register, comments, ratings_path):
    """Return (errors, scope). scope = {round, approved, rejected}."""
    errors = []
    rnd, rows, _ = read_register(register)
    if rnd < 1:
        errors.append("the register is not a revision (revision 0): the auditor's decisions have not been applied; "
                      "run the risk-assessor revision pass")
    decisions = br.parse_comments(comments)
    if not decisions:
        errors.append(f"no decision rows found in {comments}")
    if ratings_path.exists():
        ids = {r.get("id") for r in br.load(ratings_path, "risk-ratings.json").get("risks", [])}
        if ids != set(rows):
            errors.append(f"risk-ratings.json risks {sorted(ids)} differ from the register {sorted(rows)}")
    approved, rejected = [], []
    for rid, reg in sorted(rows.items()):
        d = decisions.get(rid)
        if d is None:
            errors.append(f"{rid}: in the register but has no row in auditor-comments.md")
            continue
        dec = br.norm_decision(d["decision"])
        if not d["decision"].strip():
            errors.append(f"{rid}: undecided (Decision is blank in auditor-comments.md)")
        elif not dec:
            errors.append(f"{rid}: Decision {d['decision']!r} is not Approve, Reject or Amend")
        elif dec == "Reject":
            errors.append(f"{rid}: rejected in auditor-comments.md but still in the register (revision not applied)")
        else:
            for k, name in (("L", "L"), ("I", "I")):
                want = br.override_tokens(dec, d["comment"]).get(k)
                if want is not None and want != reg[name]:
                    errors.append(f"{rid}: auditor set {k}={want} but the register shows {reg[name]}")
            approved.append({"id": rid, **reg, "decision": dec, "comment": d["comment"]})
    for rid, d in decisions.items():
        if rid in rows:
            continue
        dec = br.norm_decision(d["decision"])
        if dec == "Reject":
            rejected.append({"id": rid, "title": d["title"], "comment": d["comment"]})
            if not d["comment"].strip():
                errors.append(f"{rid}: rejected without a comment; record the reason in auditor-comments.md")
        else:
            errors.append(f"{rid}: has a row in auditor-comments.md but is not in the register and is not a Reject")
    if not errors and not approved:
        errors.append("no approved risks: nothing to plan")
    return errors, {"round": rnd, "approved": approved, "rejected": rejected}


# ------------------------------------------------------------------ plan checks
def plan_texts(plan):
    """Every prose field the planner wrote: (label, text)."""
    out = []
    memo = plan.get("memo") or {}
    for k in ("background", "approach"):
        out.append((f"memo.{k}", memo.get(k)))
    for i, t in enumerate(memo.get("limitations") or []):
        out.append((f"memo.limitations[{i}]", t))
    for rk in plan.get("risks") or []:
        out.append((f"{rk.get('risk_id')}.rationale", rk.get("rationale")))
        for c in rk.get("controls") or []:
            out.append((f"{c.get('id')}.description", c.get("description")))
        for t in rk.get("tests") or []:
            out.append((f"{t.get('id')}.step", t.get("step")))
            out.append((f"{t.get('id')}.no_sample_reason", t.get("no_sample_reason")))
    for p in plan.get("pbc_items") or []:
        out.append((f"{p.get('id')}.item", p.get("item")))
    for i, n in enumerate(plan.get("rules_not_tested") or []):
        out.append((f"rules_not_tested[{i}].reason", n.get("reason")))
    return [(a, b) for a, b in out if isinstance(b, str) and b.strip()]


def check_plan(plan, scope, ctx, errors):
    """Structure, citations, control->test coverage. Returns {rule_id: [where cited]}."""
    cited = {}

    def cite_rules(text, where):
        for kind, ref in br.CITE_RE.findall(text or ""):
            if kind == "rule" and ref in ctx.rule_ids:
                cited.setdefault(ref, []).append(where)

    approved = {r["id"] for r in scope["approved"]}
    memo = plan.get("memo")
    if not isinstance(memo, dict) or not all(isinstance(memo.get(k), str) and memo[k].strip() for k in ("background", "approach")):
        errors.append("plan: memo needs non-empty 'background' and 'approach'")
    elif not isinstance(memo.get("limitations"), list) or not memo["limitations"]:
        errors.append("plan: memo needs a non-empty 'limitations' list")
    risks = plan.get("risks")
    if not isinstance(risks, list):
        errors.append("plan: 'risks' must be a list")
        return cited
    seen = [r.get("risk_id") for r in risks]
    for rid in sorted(approved - set(seen)):
        errors.append(f"{rid}: approved but missing from the plan")
    for rid in sorted(set(seen) - approved):
        errors.append(f"{rid}: in the plan but not an approved risk (plan works only on approved risks)")
    if len(set(seen)) != len(seen):
        errors.append("plan: duplicate risk_id entries")
    pbc_ids = [p.get("id") for p in plan.get("pbc_items") or []]
    if len(set(pbc_ids)) != len(pbc_ids) or not all(pbc_ids):
        errors.append("plan: pbc_items need unique ids")
    used_pbc, all_controls, all_tests = set(), set(), set()
    for rk in risks:
        rid = rk.get("risk_id")
        if rid not in approved:
            continue
        cite_rules(" ".join(str(x) for x in br_risk_text(rk.get("_ratings"))), rid)
        if not isinstance(rk.get("rationale"), str) or not rk["rationale"].strip():
            errors.append(f"{rid}: needs a 'rationale' (why this risk is in the plan)")
        controls, tests = rk.get("controls") or [], rk.get("tests") or []
        if not controls:
            errors.append(f"{rid}: no expected controls")
        if not tests:
            errors.append(f"{rid}: no test steps")
        cids = set()
        for c in controls:
            cid = c.get("id")
            if not cid or cid in all_controls:
                errors.append(f"{rid}: control id {cid!r} missing or duplicated")
            all_controls.add(cid)
            cids.add(cid)
            tags = br.CITE_RE.findall(c.get("description") or "")
            if not any(k == "rule" and ref in ctx.rule_ids for k, ref in tags):
                errors.append(f"{cid}: control cites no rule in rules.json (uncited control)")
            cite_rules(c.get("description"), cid)
        covered = set()
        for t in tests:
            tid = t.get("id")
            if not tid or tid in all_tests:
                errors.append(f"{rid}: test id {tid!r} missing or duplicated")
            all_tests.add(tid)
            tags = br.CITE_RE.findall(t.get("step") or "")
            if not any((k == "rule" and ref in ctx.rule_ids) or (k == "metric" and ctx.cite(k, ref)[0]) for k, ref in tags):
                errors.append(f"{tid}: test step cites no rule or metric that resolves")
            cite_rules(t.get("step"), tid)
            tc = t.get("control_ids") or []
            if not tc:
                errors.append(f"{tid}: test covers no control")
            for c in tc:
                if c not in cids:
                    errors.append(f"{tid}: control {c} is not a control of {rid}")
            covered |= set(tc)
            ids = t.get("pbc") or []
            if not ids:
                errors.append(f"{tid}: needs at least one PBC item")
            for p in ids:
                if p not in pbc_ids:
                    errors.append(f"{tid}: PBC item {p} is not in pbc_items")
            used_pbc |= set(ids)
            if t.get("sample") is None and not (t.get("no_sample_reason") or "").strip():
                errors.append(f"{tid}: no sample recipe and no 'no_sample_reason'")
        for c in sorted(cids - covered):
            errors.append(f"{c}: control has no test step")
    for p in sorted(set(pbc_ids) - used_pbc):
        errors.append(f"{p}: PBC item is not needed by any test")
    for kind_label, text in plan_texts(plan):
        for kind, ref in br.CITE_RE.findall(text):
            ok, why = ctx.cite(kind, ref)
            if not ok:
                errors.append(f"{kind_label}: citation [{kind}:{ref}] does not resolve ({why})")
    return cited


def br_risk_text(rk):
    if not rk:
        return []
    out = [rk.get("title", ""), rk.get("description", ""), rk.get("proposed_focus", "")]
    for k in ("likelihood", "impact"):
        out.append((rk.get(k) or {}).get("justification", ""))
    return out + list(rk.get("evidence") or [])


def check_coverage(plan, ctx, cited, errors):
    """Every rule in rules.json is cited, or listed as not tested with a reason."""
    listed = {}
    for i, n in enumerate(plan.get("rules_not_tested") or []):
        ids, reason = n.get("rule_ids") or [], (n.get("reason") or "").strip()
        if not ids or not reason:
            errors.append(f"rules_not_tested[{i}]: needs rule_ids and a reason")
        for rid in ids:
            if rid not in ctx.rule_ids:
                errors.append(f"rules_not_tested[{i}]: {rid} is not a rule in rules.json")
            elif rid in cited:
                errors.append(f"{rid}: listed as not tested but also cited by {', '.join(sorted(set(cited[rid])))}")
            listed[rid] = reason
    for rid in sorted(ctx.rule_ids - set(cited) - set(listed)):
        errors.append(f"{rid}: rule is not cited by any risk, control or test and is not listed as not tested")
    return listed


def check_prose(plan, spend, errors, warnings):
    names = {n for n in spend["norm_supplier"].dropna().map(norm) if len(n) >= 6 and (" " in n or len(n) >= 8)}
    rx = re.compile(r"(?<![A-Z0-9])(" + "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True)) + r")(?![A-Z0-9])") if names else None
    for label, text in plan_texts(plan):
        m = BANNED.search(text)
        if m:
            errors.append(f"{label}: accusatory word {m.group(0)!r}; use indicator language")
        if rx:
            hit = rx.search(norm(text))
            if hit:
                errors.append(f"{label}: names a supplier ({hit.group(1)}); supplier names stay in analytics-full")
        figs = br.typed_figures(text)
        if figs:
            warnings.append(f"{label}: figure typed in prose {figs}; use a {{{{$.path}}}} or {{{{@key}}}} placeholder")


# ------------------------------------------------------------------ sampling
def apply_filter(df, flt, label, errors):
    for f in flt or []:
        col, op, val = f.get("col"), f.get("op"), f.get("value")
        if col not in df.columns or op not in OPS:
            errors.append(f"{label}: bad filter {f} (columns: {list(df.columns)[:12]}; ops: {sorted(OPS)})")
            return df.iloc[0:0]
        s = df[col]
        if op in ("in", "contains"):
            m = s.astype(str).isin([str(v) for v in val]) if op == "in" else s.astype(str).str.contains(str(val), regex=False)
        else:
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                s, val = pd.to_numeric(s, errors="coerce"), float(val)
            else:
                s, val = s.astype(str), str(val)
            m = {"==": s == val, "!=": s != val, ">": s > val, ">=": s >= val, "<": s < val, "<=": s <= val}[op]
        df = df[m.fillna(False)]
    return df


def draw_sample(test, rk, spend, afdir, errors):
    """Deterministic draw. Returns (sample DataFrame, info) or (None, None) after recording errors."""
    tid, rec = test["id"], test["sample"]
    cap = size_for(rk["score"])
    path = afdir / str(rec.get("file", ""))
    if not rec.get("file") or "/" in rec["file"] or not path.is_file():
        errors.append(f"{tid}: sample file {rec.get('file')!r} is not in analytics-full")
        return None, None
    src = pd.read_csv(path, low_memory=False)
    src["_line"] = range(2, len(src) + 2)  # line number in the source file
    pop = apply_filter(src, rec.get("filter"), f"{tid} sample", errors)
    if pop.empty:
        errors.append(f"{tid}: sample filter matches no rows in {rec['file']}")
        return None, None
    by, desc = [], []
    for s in rec.get("sort") or []:
        if s.get("by") not in src.columns:
            errors.append(f"{tid}: sort column {s.get('by')!r} not in {rec['file']}")
            return None, None
        by.append(s["by"]); desc.append(bool(s.get("desc")))
    by.append(src.columns[0]); desc.append(False)  # tie-break: deterministic whatever the file order
    pop = pop.sort_values(by, ascending=[not d for d in desc], kind="mergesort")
    n = rec.get("n", cap)
    if not isinstance(n, int) or isinstance(n, bool) or n < 1:
        errors.append(f"{tid}: sample n must be a positive integer")
        return None, None
    if n > cap:
        errors.append(f"{tid}: sample n={n} exceeds {cap}, the size for {rk['id']} score {rk['score']}")
        return None, None
    n = min(n, len(pop))
    method = rec.get("method", "top")
    if method == "spread":  # evenly spaced through the sorted population, integer arithmetic only
        idx = [i * len(pop) // n for i in range(n)]
        items = pop.iloc[idx]
    elif method == "top":
        items = pop.iloc[:n]
    else:
        errors.append(f"{tid}: sample method must be 'top' or 'spread'")
        return None, None
    per = rec.get("rows_per_item", 3)
    if not isinstance(per, int) or not 1 <= per <= MAX_ROWS_PER_ITEM:
        errors.append(f"{tid}: rows_per_item must be 1 to {MAX_ROWS_PER_ITEM}")
        return None, None
    kind = "transaction" if "row_id" in src.columns else "group" if "row_ids" in src.columns else \
        "supplier" if "norm_supplier" in src.columns else None
    if kind is None:
        errors.append(f"{tid}: {rec['file']} has no row_id, row_ids or norm_supplier column to pull transactions by")
        return None, None
    by_id = spend.set_index("row_id", drop=False).rename_axis(None)
    rows = []
    for rank, (_, it) in enumerate(items.iterrows(), 1):
        key = f"{rec['file']}:line {it['_line']}"
        ids = [it["row_id"]] if kind == "transaction" else str(it["row_ids"]).split(";") if kind == "group" else \
            list(spend.loc[spend["norm_supplier"] == it["norm_supplier"], "row_id"])
        missing = [i for i in ids if i not in by_id.index]
        if missing:
            errors.append(f"{tid}: {key} lists transaction(s) not in cleaned_spend.csv: {missing[:3]}")
            continue
        got = by_id.loc[ids].sort_values(["amount", "date", "row_id"], ascending=[False, True, True], kind="mergesort").iloc[:per]
        if kind == "transaction" and abs(float(got.iloc[0]["amount"]) - float(it["amount"])) > 0.005:
            errors.append(f"{tid}: {key} amount {it['amount']} differs from cleaned_spend.csv {got.iloc[0]['amount']}")
            continue
        for _, g in got.iterrows():
            rows.append({"test_id": tid, "risk_id": rk["id"], "item_rank": rank, "item_key": key, **{c: g[c] for c in SAMPLE_COLS[4:]}})
    sample = pd.DataFrame(rows, columns=SAMPLE_COLS)
    info = {"file": rec["file"], "kind": kind, "population": int(len(pop)), "items": int(len(items)),
            "rows": int(len(sample)), "size_cap": cap, "method": method, "rows_per_item": per,
            "filter": rec.get("filter") or [], "sort": rec.get("sort") or []}
    return sample, info


# ------------------------------------------------------------------ rendering
class Renderer:
    def __init__(self, ctx, computed, errors):
        self.ctx, self.computed, self.errors, self.figures = ctx, computed, errors, []
        self.doc = ""

    def record(self, key, value, text, source):
        self.figures.append({"key": key, "value": value, "text": text, "source": source, "doc": self.doc})

    def num(self, key, value, text=None):
        """A figure the builder computed itself, written into a table or sentence."""
        self.record(key, value, str(value) if text is None else text, "computed by build_pack.py")
        return str(value) if text is None else text

    def fill(self, text, label):
        def at(m):
            if m.group(1) not in self.computed:
                self.errors.append(f"{label}: placeholder {m.group(0)}: no such computed figure")
                return m.group(0)
            v = self.computed[m.group(1)]
            self.record("@" + m.group(1), v, f"{v:,}" if isinstance(v, int) else str(v), "computed by build_pack.py")
            return f"{v:,}" if isinstance(v, int) else str(v)

        def dollar(m):
            try:
                v = br.resolve_path(self.ctx.a, m.group(1))
                s = br.fmt_value(v, m.group(2))
            except (KeyError, ValueError) as e:
                self.errors.append(f"{label}: placeholder {m.group(0)}: {e.args[0]}")
                return m.group(0)
            self.record(m.group(1), v, s, "analytics.json")
            return s
        return br.PH_RE.sub(dollar, AT_RE.sub(at, text))


def filter_text(rec):
    parts = [f"{f['col']} {f['op']} {f['value']}" for f in rec.get("filter") or []]
    srt = [f"{s['by']} {'desc' if s.get('desc') else 'asc'}" for s in rec.get("sort") or []]
    return ("filter: " + " and ".join(parts) if parts else "no filter") + "; sort: " + (", ".join(srt) or "file order")


def render_all(plan, scope, ctx, ratings, infos, listed, cited, version, now, errors):
    approved = {r["id"]: r for r in scope["approved"]}
    plan_risks = {r["risk_id"]: r for r in plan["risks"]}
    rated = {r["id"]: r for r in ratings["risks"]}
    n_tests = sum(len(r["tests"]) for r in plan["risks"])
    comp = {"scope.approved": len(approved), "scope.rejected": len(scope["rejected"]), "scope.tests": n_tests,
            "scope.samples": len(infos), "scope.sample_rows": sum(i["rows"] for i in infos.values()),
            "scope.rules_total": len(ctx.rule_ids), "scope.rules_cited": len(cited), "scope.rules_not_tested": len(listed),
            "scope.register_revision": scope["round"], "scope.pack_version": version}
    for tid, i in infos.items():
        comp.update({f"{tid}.population": i["population"], f"{tid}.items": i["items"], f"{tid}.rows": i["rows"]})
    for rid, r in approved.items():
        comp.update({f"{rid}.score": r["score"], f"{rid}.likelihood": r["L"], f"{rid}.impact": r["I"],
                     f"{rid}.sample_size": size_for(r["score"])})
    R = Renderer(ctx, comp, errors)
    head = (f"**Status:** DRAFT pack v{version}, awaiting QA and auditor sign-off · built {now} · "
            f"from risk register revision {scope['round']} · indicators to investigate, not findings of wrongdoing")

    # ---- planning memo
    R.doc = "planning-memo.md"
    memo = plan["memo"]
    L = ["# Planning memo: West Berkshire Council procurement audit", "", head, "", "## 1. Scope: approved risks", "",
         "| Risk | Title | Likelihood | Impact | Score | Band | Auditor decision | Auditor comment |", "|---|---|---|---|---|---|---|---|"]
    for r in approved.values():
        L.append(f"| {r['id']} | {cell(r['title'])} | {R.num(r['id'] + '.likelihood', r['L'])} | {R.num(r['id'] + '.impact', r['I'])} | "
                 f"{R.num(r['id'] + '.score', r['score'])} | {r['band']} | {r['decision']} | {cell(r['comment'])} |")
    L += ["", f"{R.num('scope.approved', len(approved))} risk(s) are in scope, each recommended by the risk-assessor and "
          "decided by the auditor. Scores are the register's; an Amend carries the auditor's override."]
    if scope["rejected"]:
        L += ["", "**Rejected by the auditor, not planned** (recorded in auditor-comments.md):", ""]
        L += [f"- {r['id']} {cell(r['title'])}: {cell(r['comment'])}" for r in scope["rejected"]]
    L += ["", "**Why each risk is in the plan**", ""]
    L += [f"- **{rid}**: {R.fill(plan_risks[rid]['rationale'], rid + '.rationale')}" for rid in approved]
    L += ["", "## 2. Background", "", R.fill(memo["background"], "memo.background"), "", "## 3. Approach", "",
          R.fill(memo["approach"], "memo.approach"), "", "## 4. Sampling", "",
          "Samples are drawn by code from the full flagged lists in `outputs/analytics-full/`, sorted by the recipe shown "
          "in audit-program.md and taken in order, so a re-run draws the same items. Each sampled transaction is "
          "confirmed to exist in `cleaned_spend.csv`. Size follows the risk score: "
          + ", ".join(f"score {lo} or more: {n} items" for lo, n in SIZE_BANDS) + ". "
          "Items are suppliers, flagged groups or single payments depending on the list; up to "
          f"{MAX_ROWS_PER_ITEM} of each item's largest transactions are pulled.", "",
          "| Test | Risk | Source list | Population | Items drawn | Transactions | Sample file |", "|---|---|---|---|---|---|---|"]
    for tid, i in infos.items():
        rid = next(r["risk_id"] for r in plan["risks"] for t in r["tests"] if t["id"] == tid)
        L.append(f"| {tid} | {rid} | {i['file']} | {R.num(tid + '.population', i['population'], f'{i['population']:,}')} | "
                 f"{R.num(tid + '.items', i['items'])} | {R.num(tid + '.rows', i['rows'])} | `samples/{tid}.csv` |")
    L += ["", f"In total {R.num('scope.samples', len(infos))} sample file(s) and "
          f"{R.num('scope.sample_rows', comp['scope.sample_rows'], f'{comp['scope.sample_rows']:,}')} transactions.", "",
          "## 5. Limitations", ""]
    L += [f"- {R.fill(t, f'memo.limitations[{i}]')}" for i, t in enumerate(memo["limitations"])]
    L += ["", "## 6. Rule coverage", "",
          f"{R.num('scope.rules_total', len(ctx.rule_ids))} testable rules in rules.json: "
          f"{R.num('scope.rules_cited', len(cited))} cited by a risk, control or test, "
          f"{R.num('scope.rules_not_tested', len(listed))} listed as not tested with a reason. "
          "See risk-control-matrix.md.", "", "## 7. Sign-off", "",
          "The pack is cross-checked by the QA scripts; the auditor signs off in `outputs/review.md`.", ""]
    memo_md = "\n".join(L)

    # ---- risk-control matrix
    R.doc = "risk-control-matrix.md"
    rule_info = {x["rule_id"]: x for x in ctx.r["rules"]}
    L = ["# Risk-control matrix", "", head, "", "## Risk → rule → control → test", "",
         "| Risk | Rule(s) | Expected control | Test(s) | Sample |", "|---|---|---|---|---|"]
    for rid in approved:
        pr = plan_risks[rid]
        for c in pr["controls"]:
            rules = sorted({ref for k, ref in br.CITE_RE.findall(c["description"]) if k == "rule"})
            ts = [t for t in pr["tests"] if c["id"] in t["control_ids"]]
            L.append(f"| {rid} | {', '.join(rules)} | {c['id']}: {cell(R.fill(c['description'], c['id']))} | "
                     f"{', '.join(t['id'] for t in ts)} | {', '.join('samples/' + t['id'] + '.csv' for t in ts if t['id'] in infos) or 'none'} |")
    L += ["", "## Rule coverage", "", "| Rule | Clause | Page | Type | Cited by |", "|---|---|---|---|---|"]
    for rid in sorted(ctx.rule_ids):
        x = rule_info[rid]
        by = ", ".join(sorted(set(cited.get(rid, [])))) or "not tested: " + cell(listed[rid])
        L.append(f"| {rid} | {x['clause']} | {x['page']} | {x['type']} | {by} |")
    L.append("")
    matrix_md = "\n".join(L)

    # ---- audit program
    R.doc = "audit-program.md"
    L = ["# Audit program", "", head, ""]
    for rid, r in approved.items():
        pr, rt = plan_risks[rid], rated[rid]
        L += [f"## {rid}: {r['title']}", "",
              f"**Rating:** L{r['L']} × I{r['I']} = {r['score']} {r['band']} · auditor decision: {r['decision']} · "
              f"sample size by score: up to {R.num(rid + '.sample_size', size_for(r['score']))} items per test", "",
              R.fill(rt["description"], rid + ".description"), "",
              f"**Proposed focus (risk-assessor):** {R.fill(rt['proposed_focus'], rid + '.proposed_focus')}", "",
              "**Expected controls**", ""]
        L += [f"- **{c['id']}**: {R.fill(c['description'], c['id'])}" for c in pr["controls"]]
        L += ["", "**Test steps**", "", "| Test | Controls | Step | Sample | PBC |", "|---|---|---|---|---|"]
        for t in pr["tests"]:
            i = infos.get(t["id"])
            if i:
                s = (f"{i['file']}: {filter_text(t['sample'])}; {i['method']}; {i['items']} of {i['population']:,} {i['kind']}s → "
                     f"{i['rows']} transactions in `samples/{t['id']}.csv`")
                R.num(t["id"] + ".items", i["items"]); R.num(t["id"] + ".population", i["population"], f"{i['population']:,}")
                R.num(t["id"] + ".rows", i["rows"])
            else:
                s = "no sample: " + R.fill(t["no_sample_reason"], t["id"] + ".no_sample_reason")
            L.append(f"| {t['id']} | {', '.join(t['control_ids'])} | {cell(R.fill(t['step'], t['id']))} | {cell(s)} | {', '.join(t['pbc'])} |")
        L.append("")
    L += ["## Request list (PBC): prepared by client", "", "| PBC | Item requested | Needed for |", "|---|---|---|"]
    needs = {}
    for r in plan["risks"]:
        for t in r["tests"]:
            for p in t["pbc"]:
                needs.setdefault(p, []).append(t["id"])
    for p in plan["pbc_items"]:
        L.append(f"| {p['id']} | {cell(R.fill(p['item'], p['id']))} | {', '.join(needs[p['id']])} |")
    L.append("")
    return memo_md, matrix_md, "\n".join(L), R.figures, comp


# ------------------------------------------------------------------ main
def run(a):
    out = Path(a.out_dir)
    gate_errors, scope = gate(Path(a.register), Path(a.comments), Path(a.ratings))
    if gate_errors:
        raise Fatal("gate closed:\n  - " + "\n  - ".join(gate_errors))
    ap = scope["approved"]
    print(f"GATE PASS: register revision {scope['round']}; in scope {', '.join(r['id'] for r in ap)} "
          f"({sum(r['decision'] == 'Approve' for r in ap)} approved, {sum(r['decision'] == 'Amend' for r in ap)} amended); "
          f"rejected {', '.join(r['id'] for r in scope['rejected']) or 'none'}")
    if a.gate:
        return 0
    plan = br.load(a.plan, "audit-plan.json")
    ratings = br.load(a.ratings, "risk-ratings.json")
    ctx = br.Ctx(br.load(a.analytics, "analytics.json"), br.load(a.rules, "rules.json"), br.load(a.history, "history.json"))
    afdir = Path(a.analytics_full)
    spend_path = Path(a.spend) if a.spend else afdir / "cleaned_spend.csv"
    if not spend_path.exists():
        raise Fatal(f"cleaned spend not found: {spend_path}")
    spend = pd.read_csv(spend_path, low_memory=False)
    errors, warnings = [], []
    rated = {r["id"]: r for r in ratings["risks"]}
    for rk in plan.get("risks") or []:
        rk["_ratings"] = rated.get(rk.get("risk_id"))
    cited = check_plan(plan, scope, ctx, errors)
    listed = check_coverage(plan, ctx, cited, errors)
    check_prose(plan, spend, errors, warnings)
    infos, samples = {}, {}
    byid = {r["id"]: r for r in ap}
    for rk in plan.get("risks") or []:
        if rk.get("risk_id") not in byid:
            continue
        for t in rk.get("tests") or []:
            if t.get("sample") is not None and t.get("id"):
                df, info = draw_sample(t, byid[rk["risk_id"]], spend, afdir, errors)
                if df is not None:
                    samples[t["id"]], infos[t["id"]] = df, info
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    version = plan.get("version", 1)
    docs = None
    if not errors:
        docs = render_all(plan, scope, ctx, ratings, infos, listed, cited, version, now, errors)
    if errors:
        raise Fatal("pack not built, nothing written:\n  - " + "\n  - ".join(errors))
    memo_md, matrix_md, program_md, figures, comp = docs
    sdir = out / "samples"
    sdir.mkdir(parents=True, exist_ok=True)
    for old in sdir.glob("T-*.csv"):
        old.unlink()
    for tid, df in samples.items():
        df.to_csv(sdir / f"{tid}.csv", index=False)
    (out / "planning-memo.md").write_text(memo_md, encoding="utf-8")
    (out / "risk-control-matrix.md").write_text(matrix_md, encoding="utf-8")
    (out / "audit-program.md").write_text(program_md, encoding="utf-8")
    (out / "pack-figures.json").write_text(json.dumps(
        {"generated": now, "pack_version": version, "register_revision": scope["round"], "computed": comp,
         "samples": infos, "figures": figures}, indent=1, default=str), encoding="utf-8")
    print(f"pack v{version}: {len(ap)} risk(s), {len(infos)} sample file(s) with {comp['scope.sample_rows']} transactions, "
          f"{len(cited)}/{len(ctx.rule_ids)} rules cited, {len(listed)} listed as not tested, {len(figures)} figures recorded")
    for w in warnings:
        print(f"  WARN {w}")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    o = ROOT / "outputs"
    p.add_argument("--gate", action="store_true", help="run only the scope gate")
    for name, default in (("plan", o / "audit-plan.json"), ("ratings", o / "risk-ratings.json"),
                          ("register", o / "risk-register.md"), ("comments", o / "auditor-comments.md"),
                          ("analytics", o / "analytics.json"), ("rules", o / "rules.json"),
                          ("history", o / "history.json"), ("analytics-full", o / "analytics-full"),
                          ("out-dir", o)):
        p.add_argument("--" + name, default=str(default))
    p.add_argument("--spend", default=None, help="default: <analytics-full>/cleaned_spend.csv")
    a = p.parse_args(argv)
    try:
        return run(a)
    except Fatal as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
