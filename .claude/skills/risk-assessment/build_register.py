#!/usr/bin/env python3
"""Build outputs/risk-register.md and outputs/auditor-comments.md from the
risk-assessor's judgments (outputs/risk-ratings.json).

The agent supplies judgment only: scores and justifications. This script
resolves every citation, fills every {{$.path}} placeholder from analytics.json,
computes score / matrix label / band from the council's matrix in history.json,
and refuses anything it cannot trace. Run from the project root:

    .venv/bin/python .claude/skills/risk-assessment/build_register.py
        [--ratings P] [--analytics P] [--rules P] [--history P] [--out-dir D]

Exit 0 = register written (warnings may be printed); exit 1 = nothing written.
"""
import argparse
import datetime
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

CITE_RE = re.compile(r"\[(rule|metric|history):([^\]\s]+)\]")
PH_RE = re.compile(r"\{\{\s*(\$[^}|\s]*)\s*(?:\|\s*(\w+)\s*)?\}\}")
PATH_TOK = re.compile(r"\.([A-Za-z_][\w-]*)|\[(\d+)\]")
STATE_RE = re.compile(r"<!-- risk-register-state\n(.*?)\n-->", re.S)

# Tests that are risk indicators. high_value_suppliers is a population to
# request evidence for, not an indicator, so it never counts as a signal.
INDICATOR_TESTS = ["threshold_clustering", "split_purchases", "off_contract",
                   "duplicates", "expired_notice_spend", "spend_vs_award"]
RUBRIC_BASE_CAP = 4  # indicators never prove "Certain"; 5 only via the repeat uplift
ADVERSE = {"limited assurance", "no assurance", "weak", "unsatisfactory", "limited"}
FIELDS = ["title", "description", "likelihood", "impact", "repeat_finding",
          "evidence", "proposed_focus"]
DECISIONS = {"approve": "Approve", "reject": "Reject", "amend": "Amend"}
HIST_LISTS = ["audit_opinions", "follow_ups", "risk_themes", "discrepancies", "gaps"]
# Used only when history.json reports no usable council method (stated in header).
FALLBACK_BANDS = [(16, "Very high"), (10, "High"), (5, "Medium"), (1, "Low")]
FALLBACK_LABELS = {1: "Very low", 2: "Low", 3: "Medium", 4: "High", 5: "Very high"}


class Fatal(Exception):
    pass


# ---------------------------------------------------------------- lookups
def resolve_path(doc, path):
    """Resolve $.a.b[0].c against doc; KeyError with a reason if it does not."""
    if not path.startswith("$"):
        raise KeyError(f"{path}: must start with $")
    cur, pos = doc, 1
    while pos < len(path):
        m = PATH_TOK.match(path, pos)
        if not m:
            raise KeyError(f"{path}: bad syntax at {path[pos:]!r}")
        key, idx = m.group(1), m.group(2)
        try:
            cur = cur[key] if key is not None else cur[int(idx)]
        except (KeyError, IndexError, TypeError):
            raise KeyError(f"{path}: nothing at {m.group(0)}")
        pos = m.end()
    return cur


def fmt_value(v, fmt):
    if isinstance(v, (dict, list)) or v is None:
        raise ValueError("not a single value")
    if fmt == "gbp" and isinstance(v, (int, float)) and not isinstance(v, bool):
        return f"£{v:,.0f}"
    if fmt == "pct" and isinstance(v, (int, float)) and not isinstance(v, bool):
        return f"{v:.1f}%"
    if fmt not in (None, "", "int", "gbp", "pct"):
        raise ValueError(f"unknown format |{fmt}")
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, int) or fmt == "int":
        return f"{int(v):,}"
    if isinstance(v, float):
        return f"{v:,.2f}"
    return str(v)


class Ctx:
    def __init__(self, analytics, rules, history):
        self.a, self.r, self.h = analytics, rules, history
        self.rule_ids = {x["rule_id"] for x in rules.get("rules", [])}
        self.hist = {}  # id -> (list name, item)
        for lst in HIST_LISTS:
            for it in history.get(lst, []):
                if "id" in it:
                    self.hist[it["id"]] = (lst, it)

    def adverse(self, hid):
        """True/False for an audit opinion or follow-up id; None if not an audit item."""
        lst, it = self.hist.get(hid, (None, None))
        if lst not in ("audit_opinions", "follow_ups"):
            return None
        vals = [it.get("opinion"), it.get("report_opinion"), it.get("implementation_opinion"),
                (it.get("implementation") or {}).get("implementation_opinion")]
        return any(str(v).strip().lower() in ADVERSE for v in vals if v)

    def test_signals(self, name):
        t = self.a.get("tests", {}).get(name)
        if not isinstance(t, dict) or t.get("status") != "ran":
            return False
        n = t.get("counts", t.get("count"))
        return isinstance(n, (int, float)) and not isinstance(n, bool) and n > 0

    def cite(self, kind, ref):
        """(resolved?, reason)."""
        if kind == "rule":
            return (ref in self.rule_ids, f"no rule {ref} in rules.json")
        if kind == "history":
            return (ref in self.hist, f"no history item {ref}")
        try:
            resolve_path(self.a, ref)
            return True, ""
        except KeyError as e:
            return False, str(e.args[0])


def fill(text, ctx, errors):
    """Fill {{$.path|fmt}} placeholders; unresolvable ones are errors."""
    def sub(m):
        try:
            return fmt_value(resolve_path(ctx.a, m.group(1)), m.group(2))
        except (KeyError, ValueError) as e:
            errors.append(f"placeholder {m.group(0)}: {e.args[0]}")
            return m.group(0)
    return PH_RE.sub(sub, text)


def mark_cites(text, ctx, found):
    """Flag unresolvable citations in rendered text; record all in found."""
    def sub(m):
        ok, why = ctx.cite(m.group(1), m.group(2))
        found.append((m.group(1), m.group(2), ok, why))
        return m.group(0) if ok else f"[{m.group(1)}:{m.group(2)} ⚠UNRESOLVED]"
    return CITE_RE.sub(sub, text)


TYPED_FIG = [re.compile(p) for p in (r"£\s?\d", r"\d(?:\.\d+)?\s?%", r"\b\d{1,3}(?:,\d{3})+\b",
                                     r"(?<![\w.,£])\d{2,}(?![\w])")]


def typed_figures(text):
    """Digits typed in prose (outside citations and placeholders). Years are allowed."""
    t = PH_RE.sub(" ", CITE_RE.sub(" ", text))
    t = re.sub(r"\b(19|20)\d{2}(?:/\d{2,4})?\b", " ", t)
    t = re.sub(r"\b[A-Z]{1,5}-\d+\b", " ", t)  # ids such as CPR-59, OP-12
    return sorted({m.group(0).strip() for p in TYPED_FIG for m in p.finditer(t)})


# ---------------------------------------------------------------- method
class Method:
    """Scoring method: council matrix from history.json, or the stated fallback."""

    def __init__(self, history):
        sm = history.get("scoring_method", {})
        self.fallback = not sm.get("usable")
        self.section = sm.get("section", "")
        self.header_notes, self.conflicts = [], []
        self.esc_used = self.esc_other = None
        if self.fallback:
            self.cells, self.table4 = {}, []
            self.i_labels = self.l_labels = FALLBACK_LABELS
            return
        self.cells = {(c["likelihood"], c["impact"]): c for c in sm["matrix"]["cells"]}
        for (l, i), c in self.cells.items():
            if c["score"] != l * i:
                raise Fatal(f"history.json matrix cell L{l}xI{i} has score {c['score']} != {l * i}")
        self.i_labels = {x["score"]: x["label"] for x in sm["scales"]["impact"]["levels"]}
        self.l_labels = {x["score"]: x["label"] for x in sm["scales"]["likelihood"]["levels"]}
        self.table4 = []
        for r in sm["bands"]["rows"]:
            nums = [int(n) for n in re.findall(r"\d+", r["score_range"])]
            lo, hi = (1, nums[0]) if r["score_range"].lower().startswith("up to") else (nums[0], nums[-1])
            self.table4.append({"lo": lo, "hi": hi, "level": r["level"],
                                "name": re.sub(r"\s*\(.*?\)", "", r["level"]).strip(),
                                "escalation": r["escalation"]})
        self._conflicts(history)

    def _conflicts(self, history):
        """Turn recorded discrepancies that affect scoring into used/marked statements."""
        for d in history.get("discrepancies", []):
            kind, desc = d.get("kind"), d.get("description", "")
            ref = f"{d['id']} (history)"
            if kind == "band_label":
                self.conflicts.append((ref, desc,
                    "USED: the Figure 1 matrix label for each cell's band (High, Extreme, Moderate, Low).",
                    "MARKED, not used: Table 4's label 'Medium - High (Amber)' for scores 8-12; shown beside the band."))
            elif kind == "score_threshold":
                nums = [int(n) for q in d.get("evidence", []) for n in re.findall(r"(\d+) or above", q.get("quote", ""))]
                ext = max((b for b in self.table4 if "extreme" in b["name"].lower()), key=lambda b: b["lo"], default=None)
                if nums and ext:
                    self.esc_used, self.esc_other = ext["lo"], min(nums)
                    self.conflicts.append((ref, desc,
                        f"USED: Table 4, add to Corporate Risk Register at scores {ext['lo']}-{ext['hi']}.",
                        f"MARKED, not used: Figure 4, scores {self.esc_other} or above; risks scoring "
                        f"{self.esc_other}-{ext['lo'] - 1} are flagged in the register."))
                else:
                    self.conflicts.append((ref, desc, "UNRESOLVED: builder could not read both thresholds.",
                                           "Auditor to decide the Corporate Risk Register threshold."))
            elif kind == "label_text_vs_table" and "impact" in desc.lower():
                self.conflicts.append((ref, desc,
                    "USED: Table 1 numbering (Negligible 1, Minor 2, Medium 3, Major 4, Critical 5).",
                    "MARKED, not used: the running-text label 'Medium (2)'."))
            elif kind == "overlapping_bounds":
                self.conflicts.append((ref, desc,
                    "USED: where an estimated financial loss falls in the overlap, rate the higher impact (Major, 4).",
                    "MARKED, not used: the Medium (3) reading of the overlap."))

    def cell(self, l, i):
        if self.fallback:
            s = l * i
            band = next(n for lo, n in FALLBACK_BANDS if s >= lo)
            return {"score": s, "band": band}
        return self.cells[(l, i)]

    def table4_for(self, score):
        return next((b for b in self.table4 if b["lo"] <= score <= b["hi"]), None)

    def notes_for(self, score, band):
        out = []
        t4 = self.table4_for(score)
        if t4 and t4["name"].lower() != band.lower():
            out.append(f"Table 4 names this band '{t4['level']}'; the matrix label is used (see conflicts).")
        if self.esc_used and self.esc_other <= score < self.esc_used:
            out.append(f"Figure 4 would add this to the Corporate Risk Register (score {self.esc_other} or above); "
                       f"Table 4 does not (needs {self.esc_used}). Table 4 applied; auditor to confirm.")
        elif self.esc_used and score >= self.esc_used:
            out.append("Corporate Risk Register escalation applies (Table 4).")
        return out


# ---------------------------------------------------------------- one risk
def check_risk(rk, ctx, method, override):
    """Validate and resolve one risk. Returns dict with ok, errors, warnings, resolved fields."""
    res = {"id": rk.get("id", "?"), "errors": [], "warnings": [], "raw": rk, "ok": False}
    err, warn = res["errors"], res["warnings"]
    for f in ("id", "title", "description", "likelihood", "impact", "evidence", "proposed_focus"):
        if f not in rk or rk[f] in (None, "", []):
            err.append(f"missing field '{f}'")
    if err:
        return res
    scores = {}
    for dim in ("likelihood", "impact"):
        blk = rk[dim]
        s, j = blk.get("score") if isinstance(blk, dict) else None, blk.get("justification") if isinstance(blk, dict) else None
        if not (isinstance(s, int) and not isinstance(s, bool) and 1 <= s <= 5) or not isinstance(j, str) or not j.strip():
            err.append(f"{dim}: needs integer score 1-5 and a justification")
            continue
        scores[dim] = s
    if err:
        return res
    for t in [rk["title"], rk["description"], rk["proposed_focus"]] + list(rk["evidence"]):
        if not isinstance(t, str):
            err.append("title, description, evidence and focus must be text")
            return res

    # citations: each justification needs at least one that resolves
    cites = {}
    for dim in ("likelihood", "impact"):
        found = []
        res[dim + "_text"] = fill(mark_cites(rk[dim]["justification"], ctx, found), ctx, err)
        cites[dim] = found
        if not any(ok for _, _, ok, _ in found):
            bad = "; ".join(f"{k}:{r} ({w})" for k, r, _, w in found)
            err.append(f"{dim} justification has no resolvable citation" + (f" [{bad}]" if bad else ""))
        for k, r, ok, w in found:
            if not ok:
                warn.append(f"{dim}: unresolved citation {k}:{r} ({w})")
    res["title_text"] = fill(rk["title"], ctx, err)
    res["description_text"] = fill(mark_cites(rk["description"], ctx, []), ctx, err)
    res["focus_text"] = fill(mark_cites(rk["proposed_focus"], ctx, []), ctx, err)
    res["evidence_text"] = [fill(mark_cites(e, ctx, []), ctx, err) for e in rk["evidence"]]

    # rubric + repeat-finding uplift
    sig = sorted({m.group(1) for k, r, ok, _ in cites["likelihood"] if k == "metric" and ok
                  for m in [re.match(r"\$\.tests\.(\w+)", r)] if m
                  and m.group(1) in INDICATOR_TESTS and ctx.test_signals(m.group(1))})
    rubric = min(RUBRIC_BASE_CAP, 1 + len(sig))
    rf = rk.get("repeat_finding")
    uplift = 0
    if rf:
        ids = rf.get("history") if isinstance(rf, dict) else None
        if not ids or not isinstance(ids, list):
            err.append("repeat_finding needs a 'history' list of audit ids")
        else:
            for hid in ids:
                a = ctx.adverse(hid)
                if a is None:
                    err.append(f"repeat_finding cites {hid}, which is not an audit opinion or follow-up in history.json")
                elif not a:
                    err.append(f"repeat_finding cites {hid}, whose opinion is not adverse")
            uplift = 1
    else:
        adv = sorted({r for k, r, ok, _ in cites["likelihood"] + cites["impact"] if k == "history" and ok and ctx.adverse(r)})
        if adv:
            warn.append(f"cites adverse audit(s) {', '.join(adv)} but applies no repeat_finding uplift; confirm the theme is not a repeat")
    base = rubric
    ro = rk["likelihood"].get("rubric_override")
    if ro:
        if not (isinstance(ro, dict) and isinstance(ro.get("score"), int) and str(ro.get("reason", "")).strip()):
            err.append("rubric_override needs integer 'score' and a 'reason'")
        else:
            base = ro["score"]
    expected = min(5, base + uplift)
    ov = override.get("L")
    if ov:
        res["override_L"] = ov
    elif scores["likelihood"] != expected:
        err.append(f"likelihood {scores['likelihood']} does not follow the rubric: {len(sig)} indicator test(s) cited "
                   f"({', '.join(sig) or 'none'}) gives {rubric}" + (f", override base {base}" if ro else "")
                   + (", +1 repeat-finding uplift" if uplift else "") + f" = {expected}. Re-rate, or add a rubric_override with a reason")
    if override.get("I"):
        res["override_I"] = override["I"]
    res.update(sig=sig, rubric=rubric, base=base, uplift=uplift, rf=rf if uplift else None, ro=ro)

    # score from the matrix
    c = method.cell(scores["likelihood"], scores["impact"])
    res.update(L=scores["likelihood"], I=scores["impact"], score=c["score"], band=c["band"])
    res["band_notes"] = method.notes_for(c["score"], c["band"])

    # typed figures
    for where, t in [("title", rk["title"]), ("description", rk["description"]), ("proposed_focus", rk["proposed_focus"]),
                     ("likelihood", rk["likelihood"]["justification"]), ("impact", rk["impact"]["justification"])] + \
                    [(f"evidence[{n}]", e) for n, e in enumerate(rk["evidence"])]:
        figs = typed_figures(t)
        if figs:
            warn.append(f"{where}: figure typed in prose ({', '.join(figs)}); use a {{{{$.path}}}} placeholder")
    res["ok"] = not err
    return res


# ---------------------------------------------------------------- auditor decisions
def parse_comments(path):
    """Existing decisions: {risk_id: {title, rating, decision, comment}}."""
    out = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if not re.match(r"\|\s*R-[\w-]+\s*\|", line):
            continue
        cols = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cols) >= 5:
            out[cols[0]] = {"title": cols[1], "rating": cols[2], "decision": cols[3], "comment": "|".join(cols[4:]).strip()}
    return out


def norm_decision(raw):
    return DECISIONS.get(raw.strip().lower()) if raw.strip() else ""


def override_tokens(decision, comment):
    if decision != "Amend":
        return {}
    return {k: int(m.group(1)) for k in "LI" for m in [re.search(rf"\b{k}\s*=\s*([1-5])\b", comment)] if m}


def snap(rk):
    return {f: rk.get(f) for f in FIELDS}


def cell_clean(s):
    return re.sub(r"\s+", " ", str(s)).replace("|", "/").strip()


# ---------------------------------------------------------------- revision
def revision_check(prev, decisions, ratings, results, errors):
    """Compare this run with the previous register and the auditor's decisions.
    Returns (changes, pending) and appends to errors."""
    state_risks, rejected, applied = prev["risks"], prev.get("rejected", {}), prev.get("applied", {})
    pending = {rid: (d["decision"], d["comment"]) for rid, d in decisions.items()
               if d["decision"] and applied.get(rid) != [d["decision"], d["comment"]]}
    for rid, d in decisions.items():
        if d["decision"] == "?":
            errors.append(f"{rid}: decision '{d['raw']}' is not Approve, Reject or Amend")
    for rid in state_risks:
        if rid not in decisions or not decisions[rid]["decision"]:
            errors.append(f"{rid}: no auditor decision recorded (undecided)")
    by_id = {r["id"]: r for r in results}
    claims = (ratings.get("revision") or {}).get("changes", []) if pending else []  # a stale block is ignored once applied
    if pending and not isinstance(ratings.get("revision"), dict):
        errors.append("auditor decisions are pending but risk-ratings.json has no 'revision' block")
    actual = {}
    for rid, old in state_risks.items():
        dec = decisions.get(rid, {}).get("decision", "")
        if dec == "Reject":
            if rid in by_id:
                errors.append(f"{rid}: auditor rejected this risk but it is still in risk-ratings.json")
            continue
        r = by_id.get(rid)
        if r is None:
            errors.append(f"{rid}: removed from risk-ratings.json without an auditor Reject")
            continue
        if not r["ok"]:
            errors.append(f"{rid}: now fails builder checks ({'; '.join(r['errors'])}); an approved risk may not be dropped")
            continue
        diff = [f for f in FIELDS if json.dumps(old.get(f), sort_keys=True) != json.dumps(r["raw"].get(f), sort_keys=True)]
        if diff:
            actual[rid] = diff
        if rid in pending and pending[rid][0] == "Amend" and not diff:
            errors.append(f"{rid}: auditor asked for an amendment ('{pending[rid][1]}') but nothing changed")
        if diff and not (dec == "Amend" and rid in pending):
            errors.append(f"{rid}: unrequested change to {', '.join(diff)} (decision: {dec or 'none'})")
    for rid in by_id:
        if rid not in state_risks:
            errors.append(f"{rid}: new risk not in the previous register and not requested by the auditor")
    for rid, d in decisions.items():  # auditor score overrides must be applied
        for k, want in override_tokens(d["decision"], d["comment"]).items():
            r = by_id.get(rid)
            have = r and r["raw"]["likelihood" if k == "L" else "impact"].get("score")
            if r and have != want:
                errors.append(f"{rid}: auditor override {k}={want} not applied (risk-ratings.json has {have})")
    # the agent's claims must match the real diff, both ways
    claimed = set()
    for c in claims:
        rid, fld, why = c.get("risk_id"), c.get("field"), str(c.get("reason", "")).strip()
        if fld not in FIELDS or not why:
            errors.append(f"revision change {rid}/{fld}: needs a valid field and a reason")
        elif fld not in actual.get(rid, []):
            errors.append(f"revision claims {rid}.{fld} changed, but it did not")
        else:
            claimed.add((rid, fld))
    for rid, flds in actual.items():
        for f in flds:
            if (rid, f) not in claimed:
                errors.append(f"{rid}.{f} changed but is not declared in the revision block")
    changes = [{"risk_id": rid, "field": f, "reason": next((str(c.get("reason")) for c in claims if c.get("risk_id") == rid and c.get("field") == f), ""),
                "decision": decisions[rid]["decision"], "comment": decisions[rid]["comment"]}
               for rid, flds in actual.items() for f in flds]
    return changes, pending


# ---------------------------------------------------------------- rendering
def short(v):
    if isinstance(v, dict) and "score" in v:
        return str(v["score"])
    return "revised text"


def render(ctx, method, kept, dropped, rejected, round_no, changes, decisions, pending, warnings, prev_state, ratings, now):
    L = []
    w = L.append
    w("# Risk register: West Berkshire Council procurement audit planning")
    w("")
    w(f"**Status:** {'DRAFT v0, awaiting auditor decisions' if round_no == 0 else f'REVISION {round_no}'} · "
      f"generated {now} · indicators to investigate, not findings of wrongdoing")
    w("")
    if method.fallback:
        w("**Scoring method: FALLBACK.** history.json reports no usable council scoring method, so risks are rated on "
          "1-5 Very low…Very high (likelihood × impact). Band thresholds (Low 1-4, Medium 5-9, High 10-15, "
          "Very high 16+) are this builder's, not the council's.")
    else:
        w(f"**Scoring method:** the council's own, from the Risk Management Strategy 2024-27 ({method.section}): "
          "likelihood 1-5 × impact 1-5 = score; band from the Figure 1 matrix.")
    w("")
    w("**Likelihood rubric (binding):** base = 1 + number of distinct indicator tests cited with a non-zero count "
      f"(capped at {RUBRIC_BASE_CAP}, because indicators never show a risk is certain); +1 for a repeat finding that "
      "cites an adverse audit opinion (cap 5). Deviations carry a stated reason or an auditor override.")
    w("")
    if round_no > 0:
        w(f"## Revision {round_no}: what changed")
        w("")
        rev = (ratings.get("revision") or {}) if pending else {}
        if rev.get("summary"):
            w(f"Agent summary: {fill_plain(rev['summary'], ctx)}")
            w("")
        if changes:
            w("| Risk | Field | Change | Reason | Auditor decision |")
            w("|---|---|---|---|---|")
            for c in changes:
                old = (prev_state["risks"].get(c["risk_id"]) or {}).get(c["field"])
                new = next((k["raw"].get(c["field"]) for k in kept if k["id"] == c["risk_id"]), None)
                ov = override_tokens(c["decision"], c["comment"])
                flag = " **AUDITOR OVERRIDE**" if ov and c["field"] in ("likelihood", "impact") and \
                    ov.get("L" if c["field"] == "likelihood" else "I") else ""
                w(f"| {c['risk_id']} | {c['field']} | {short(old)} → {short(new)}{flag} | {cell_clean(c['reason'])} | "
                  f"{c['decision']}: {cell_clean(c['comment'])} |")
        else:
            w("No risk content changed in this revision.")
        w("")
        appr = sorted(r for r, d in decisions.items() if d["decision"] == "Approve")
        if appr:
            w(f"Approved, unchanged: {', '.join(appr)}.")
        if rejected:
            w(f"Removed on auditor rejection: {', '.join(sorted(rejected))}.")
        w("")
    if method.conflicts:
        w("## Conflicts in the scoring method (one reading used, the other marked)")
        w("")
        for ref, desc, used, marked in method.conflicts:
            w(f"- **{ref}:** {desc}  ")
            w(f"  {used}  ")
            w(f"  {marked}")
        w("")
    if warnings:
        w("## Builder warnings")
        w("")
        for x in warnings:
            w(f"- {x}")
        w("")
    w("## Summary")
    w("")
    w("| Risk | Title | Likelihood | Impact | Score | Band |")
    w("|---|---|---|---|---|---|")
    for r in sorted(kept, key=lambda r: (-r["score"], r["id"])):
        w(f"| {r['id']} | {cell_clean(r['title_text'])} | {r['L']} | {r['I']} | {r['score']} | {r['band']} |")
    w("")
    w("## Risks")
    w("")
    for r in kept:
        ll = method.l_labels.get(r["L"], ""); il = method.i_labels.get(r["I"], "")
        w(f"### {r['id']}: {r['title_text']}")
        w("")
        w(f"**Score {r['score']}, {r['band']}** (likelihood {r['L']} {ll} × impact {r['I']} {il}; matrix cell L{r['L']}×I{r['I']})")
        for n in r["band_notes"]:
            w(f"  \n_{n}_")
        w("")
        w(f"- **Risk (indicator):** {r['description_text']}")
        lo = " **(auditor override)**" if r.get("override_L") else ""
        w(f"- **Likelihood: {r['L']} ({ll}){lo}.** {r['likelihood_text']}")
        tail = f"rubric: {len(r['sig'])} indicator test(s) with a non-zero count ({', '.join(r['sig']) or 'none'}) → base {r['rubric']}"
        if r["ro"]:
            tail += f"; rubric override to {r['base']}: {r['ro']['reason']}"
        if r["uplift"]:
            tail += f"; **repeat-finding uplift +1** citing {', '.join('[history:%s]' % h for h in r['rf']['history'])}"
            if r["rf"].get("note"):
                tail += f" ({r['rf']['note']})"
        w(f"  - _{tail}_")
        io = " **(auditor override)**" if r.get("override_I") else ""
        w(f"- **Impact: {r['I']} ({il}){io}.** {r['impact_text']}")
        w("- **Evidence:**")
        for e in r["evidence_text"]:
            w(f"  - {e}")
        w(f"- **Proposed focus:** {r['focus_text']}")
        w("")
    if dropped:
        w("## Excluded risks (not in the register; no resolvable evidence)")
        w("")
        for r in dropped:
            w(f"- **{r['id']}**: " + "; ".join(r["errors"]))
        w("")
    if rejected:
        w("## Rejected by the auditor")
        w("")
        for rid, d in sorted(rejected.items()):
            w(f"- **{rid}** {d['title']}: {d['comment'] or 'no comment'}")
        w("")
    w("## Auditor decisions")
    w("")
    w("Record one decision per risk in `outputs/auditor-comments.md` (Approve, Reject or Amend, with a comment). "
      "Approve puts the risk in audit scope. To dictate a score when amending, write `L=n` and/or `I=n` in the comment; "
      "the next revision applies it and marks it as an auditor override. "
      "The risk-assessor is then re-run to produce a revision; nothing else may change.")
    w("")
    w("| Risk | Rating | Decision |")
    w("|---|---|---|")
    for r in kept:
        d = decisions.get(r["id"], {}).get("decision") or "_awaiting_"
        w(f"| {r['id']} | {r['score']} {r['band']} | {d} |")
    w("")
    return "\n".join(L)


def fill_plain(text, ctx):
    return fill(text, ctx, [])


def render_comments(kept, rejected, decisions, applied_round):
    L = ["# Auditor decisions: risk register", "",
         "Fill in **Decision** (Approve, Reject or Amend) and a **Comment** for every row. Keep comments on one line and "
         "do not use the pipe character. To dictate a score on an Amend, write `L=n` and/or `I=n`. "
         "This file is kept when the register is rebuilt.", "",
         "| Risk | Title | Rating | Decision | Comment |", "|---|---|---|---|---|"]
    rows = {}
    for r in kept:
        d = decisions.get(r["id"], {})
        rows[r["id"]] = (r["title_text"], f"L{r['L']} × I{r['I']} = {r['score']} {r['band']}", d.get("raw", d.get("decision", "")), d.get("comment", ""))
    for rid, d in rejected.items():
        rows[rid] = (d["title"], "removed on rejection", "Reject", d["comment"])
    for rid, d in decisions.items():  # keep any recorded decision whose risk is no longer rated
        if rid not in rows and d.get("decision"):
            rows[rid] = (d["title"], d["rating"], d.get("raw", d["decision"]), d["comment"])
    for rid in sorted(rows):
        t, rt, dec, cm = rows[rid]
        L.append(f"| {rid} | {cell_clean(t)} | {cell_clean(rt)} | {cell_clean(dec)} | {cell_clean(cm)} |")
    L.append("")
    return "\n".join(L)


# ---------------------------------------------------------------- main
def load(p, what):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise Fatal(f"{what} not found: {p}")
    except json.JSONDecodeError as e:
        raise Fatal(f"{what} is not valid JSON: {e}")


def run(a):
    out = Path(a.out_dir)
    ratings = load(a.ratings, "risk-ratings.json")
    ctx = Ctx(load(a.analytics, "analytics.json"), load(a.rules, "rules.json"), load(a.history, "history.json"))
    method = Method(ctx.h)
    if not isinstance(ratings.get("risks"), list) or not ratings["risks"]:
        raise Fatal("risk-ratings.json needs a non-empty 'risks' list")
    ids = [r.get("id") for r in ratings["risks"]]
    if len(set(ids)) != len(ids):
        raise Fatal("duplicate risk ids in risk-ratings.json")
    reg_path, com_path = out / "risk-register.md", out / "auditor-comments.md"
    prev = None
    if reg_path.exists():
        m = STATE_RE.search(reg_path.read_text(encoding="utf-8"))
        if m:
            prev = json.loads(m.group(1))
    decisions = {}
    for rid, d in parse_comments(com_path).items():
        dec = norm_decision(d["decision"])
        decisions[rid] = {**d, "raw": d["decision"], "decision": dec if dec or not d["decision"].strip() else "?"}
    any_decision = any(d["decision"] for d in decisions.values())

    results = []
    for rk in ratings["risks"]:
        d = decisions.get(rk.get("id"), {})
        results.append(check_risk(rk, ctx, method, override_tokens(d.get("decision", ""), d.get("comment", ""))))
    kept = [r for r in results if r["ok"]]
    dropped = [r for r in results if not r["ok"]]

    errors, changes, pending, round_no = [], [], {}, 0
    rejected = dict(prev.get("rejected", {})) if prev else {}
    applied = dict(prev.get("applied", {})) if prev else {}
    if any_decision:
        if not prev:
            raise Fatal("auditor decisions exist but there is no previous register state to revise "
                        "(outputs/risk-register.md missing or built by hand)")
        changes, pending = revision_check(prev, decisions, ratings, results, errors)
        if errors:
            raise Fatal("revision rejected, nothing written:\n  - " + "\n  - ".join(errors))
        round_no = prev["round"] + (1 if pending else 0)
        for rid, (dec, cm) in pending.items():
            if dec == "Reject":
                rejected[rid] = {"title": decisions[rid]["title"], "comment": cm, "round": round_no}
        for rid, d in decisions.items():
            if d["decision"]:
                applied[rid] = [d["decision"], d["comment"]]
        if not pending and prev.get("last_revision"):
            changes = prev["last_revision"]["changes"]
    elif prev:
        round_no = prev["round"]

    warnings = [f"{r['id']}: {x}" for r in results for x in r["warnings"]]
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    md = render(ctx, method, kept, dropped, rejected, round_no, changes, decisions, pending, warnings, prev, ratings, now)
    state = {"round": round_no, "generated": now, "risks": {r["id"]: snap(r["raw"]) for r in kept},
             "rejected": rejected, "applied": applied,
             "last_revision": {"changes": changes} if round_no > 0 else None}
    md += "\n<!-- risk-register-state\n" + json.dumps(state, sort_keys=True).replace("--", "\\u002d\\u002d") + "\n-->\n"
    out.mkdir(parents=True, exist_ok=True)
    reg_path.write_text(md, encoding="utf-8")
    com_path.write_text(render_comments(kept, rejected, decisions, round_no), encoding="utf-8")
    print(f"risk-register.md: {len(kept)} risk(s) kept, {len(dropped)} excluded, revision {round_no}")
    for r in dropped:
        print(f"  EXCLUDED {r['id']}: " + "; ".join(r["errors"]))
    for x in warnings:
        print(f"  WARN {x}")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    o = ROOT / "outputs"
    p.add_argument("--ratings", default=str(o / "risk-ratings.json"))
    p.add_argument("--analytics", default=str(o / "analytics.json"))
    p.add_argument("--rules", default=str(o / "rules.json"))
    p.add_argument("--history", default=str(o / "history.json"))
    p.add_argument("--out-dir", default=str(o))
    a = p.parse_args(argv)
    try:
        return run(a)
    except Fatal as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
