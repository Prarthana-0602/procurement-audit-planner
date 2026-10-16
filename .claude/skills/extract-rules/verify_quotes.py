#!/usr/bin/env python3
"""Verify outputs/rules.json against data/contract-rules.pdf.

Usage (from the project root):
    .venv/bin/python .claude/skills/extract-rules/verify_quotes.py
        [--pdf data/contract-rules.pdf] [--rules outputs/rules.json]
    .venv/bin/python .claude/skills/extract-rules/verify_quotes.py --inventory

Checks: schema, sequential rule IDs, declared (null) parameters, every quote
present on its stated PDF page, and that every clause in the PDF is either in
`rules` or in `excluded`. Exit code 0 = pass, 1 = errors. Needs pdftotext and
pdfinfo (poppler) on PATH. Standard library only.
"""
import argparse
import json
import re
import subprocess
import sys
from functools import lru_cache

RULE_TYPES = {"procedure", "advertising", "approval", "exception", "anti-avoidance",
              "valuation", "record-keeping", "contract-terms", "formality"}
SCOPES = {"goods_services", "works", "concession", "light_touch", "all"}
EVIDENCE = {"spend", "contracts", "committee-papers", "document-request"}
NOTE_KINDS = {"contradiction", "gap", "placeholder", "ambiguity"}
TOP_KEYS = {"source", "parameters", "rules", "excluded", "notes"}
RULE_KEYS = {"rule_id", "clause", "page", "type", "scope", "condition", "threshold_low",
             "threshold_high", "required_action", "approver", "evidence_source",
             "verbatim_quote", "also_covers", "notes_ref"}
RULE_REQUIRED = RULE_KEYS - {"also_covers", "notes_ref"}
EXCL_KEYS = {"clause", "page", "reason", "also_covers"}
NOTE_KEYS = {"note_id", "kind", "clauses", "description", "evidence"}
MIN_QUOTE_CHARS = 10

# Expected appendix row labels; if the PDF no longer matches, the inventory
# reports drift instead of silently shrinking the coverage check.
APP_B_ROWS = ["A", "B1", "B2", "C", "D"]
APP_C_ROWS = ["A", "B", "C", "D", "E", "F"]
APP_A_BANDS = ["uptorelevantThreshold", "Abovetherelevantthresholdandlessthan£500,000",
               "Above£500,000andlessthan£2.5million", "£2.5millionormore"]


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout


def page_count(pdf):
    m = re.search(r"^Pages:\s+(\d+)", run(["pdfinfo", pdf]), re.M)
    return int(m.group(1))


@lru_cache(maxsize=None)
def page_text(pdf, n, layout=False):
    cmd = ["pdftotext", "-f", str(n), "-l", str(n)] + (["-layout"] if layout else []) + [pdf, "-"]
    return run(cmd)


def squash(s):
    """Whitespace-free form used for matching (tables and wraps break spacing)."""
    return re.sub(r"\s+", "", s.replace("­", ""))


def quote_on_page(pdf, page, quote):
    q, p = squash(quote), squash(page_text(pdf, page))
    if q in p:
        return True
    # pdftotext drops the hyphen of a hyphenated line break ("Call-\nIn" -> "CallIn")
    return q.replace("-", "") in p.replace("-", "")


def inventory(pdf):
    """clause id -> page where it starts, plus drift problems."""
    inv, problems = {}, []
    n = page_count(pdf)
    num = re.compile(r"^\s*(\d{1,2}(?:\.\d{1,2}){1,4})\s{2,}\S")
    for p in range(1, n + 1):
        lay = page_text(pdf, p, True)
        for line in lay.splitlines():
            m = num.match(line)
            if m and m.group(1) not in inv:
                inv[m.group(1)] = p
        if "Contract Rules - Appendix A" in lay:
            if all(b in squash(page_text(pdf, p)) for b in APP_A_BANDS):
                for i in range(1, 5):
                    inv[f"Appendix A row {i}"] = p
            else:
                problems.append("Appendix A value bands not as expected")
        for app in "BC":
            if f"Contract Rules - Appendix {app}" in lay:
                inv[f"Appendix {app} intro"] = p
        if "There are three different procurement regulation thresholds" in lay:
            inv["Appendix B notes"] = p
        if "In the interests of clarity where an exemption" in lay:
            inv["Appendix C closing note"] = p
    # row labels sit on the appendix page and, for Appendix C, its continuation page
    for app, rows, rx, span in (("B", APP_B_ROWS, r"^\s{2,6}([A-D][12]?)(?:\s{2,}\S.*|\s*)$", 1),
                                ("C", APP_C_ROWS, r"^\s{2,6}([A-F])(?:\s{2,}\S.*|\s*)$", 2)):
        start = inv.get(f"Appendix {app} intro")
        for p in range(start or n + 1, min((start or 0) + span, n + 1)):
            for line in page_text(pdf, p, True).splitlines():
                m = re.match(rx, line)
                if m and m.group(1) in rows:
                    inv.setdefault(f"Appendix {app} row {m.group(1)}", p)
    for app, rows in (("B", APP_B_ROWS), ("C", APP_C_ROWS)):
        for r in rows:
            if f"Appendix {app} row {r}" not in inv:
                problems.append(f"inventory drift: Appendix {app} row {r} not found")
    for k in ("Appendix B intro", "Appendix B notes", "Appendix C intro", "Appendix C closing note"):
        if k not in inv:
            problems.append(f"inventory drift: '{k}' not found")
    return inv, problems


def sort_key(cid):
    m = re.match(r"^(\d+(?:\.\d+)*)$", cid)
    if m:
        return (0, [int(x) for x in cid.split(".")], "")
    return (1, [], cid)


def expand(entry, inv):
    ids = {entry.get("clause")}
    for c in entry.get("also_covers", []) or []:
        if isinstance(c, str) and c.endswith(".*"):
            pre = c[:-1]
            ids |= {k for k in inv if k.startswith(pre)}
        elif isinstance(c, str):
            ids.add(c)
    return ids


def is_int(x):
    return isinstance(x, int) and not isinstance(x, bool)


def check_bound(b, where, params, errors):
    if b is None:
        return
    if not isinstance(b, dict) or set(b) != {"amount", "param", "inclusive"}:
        errors.append(f"E-SCHEMA: {where}: bound must be null or exactly {{amount, param, inclusive}}")
        return
    if not isinstance(b["inclusive"], bool):
        errors.append(f"E-SCHEMA: {where}: inclusive must be true/false")
    a, p = b["amount"], b["param"]
    if (a is None) == (p is None):
        errors.append(f"E-SCHEMA: {where}: exactly one of amount/param must be set")
    if a is not None and (not is_int(a) or a < 0):
        errors.append(f"E-SCHEMA: {where}: amount must be a non-negative integer (GBP), got {a!r}")
    if p is not None and p not in params:
        errors.append(f"E-PARAM: {where}: parameter {p!r} is not declared in parameters")


def check_str(v, where, errors, oneline=False):
    if not isinstance(v, str) or not v.strip():
        errors.append(f"E-SCHEMA: {where}: must be a non-empty string")
    elif oneline and "\n" in v:
        errors.append(f"E-SCHEMA: {where}: must be a single line")


def verify(doc, pdf):
    errors, warns = [], []
    inv, problems = inventory(pdf)
    errors += [f"E-INVENTORY: {p}" for p in problems]
    npages = page_count(pdf)
    if not isinstance(doc, dict):
        return ["E-SCHEMA: top level must be an object"], warns, inv
    if set(doc) != TOP_KEYS:
        errors.append(f"E-SCHEMA: top-level keys must be exactly {sorted(TOP_KEYS)}, got {sorted(doc)}")
    src = doc.get("source")
    if not (isinstance(src, dict) and set(src) == {"file", "pages"} and is_int(src.get("pages"))):
        errors.append("E-SCHEMA: source must be {file, pages}")
    elif src["pages"] != npages:
        errors.append(f"E-SCHEMA: source.pages is {src['pages']} but the PDF has {npages}")

    params = doc.get("parameters")
    if not isinstance(params, dict) or not params:
        errors.append("E-PARAM: parameters must be a non-empty object")
        params = {}
    for k, v in params.items():
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", k):
            errors.append(f"E-PARAM: parameter name {k!r} must be UPPER_SNAKE_CASE")
        if v is not None:
            errors.append(f"E-PARAM: parameter {k} must be null (the PDF does not state it), got {v!r}")

    rules, excluded, notes = doc.get("rules"), doc.get("excluded"), doc.get("notes")
    for name, v in (("rules", rules), ("excluded", excluded), ("notes", notes)):
        if not isinstance(v, list):
            errors.append(f"E-SCHEMA: {name} must be a list")
    rules = rules if isinstance(rules, list) else []
    excluded = excluded if isinstance(excluded, list) else []
    notes = notes if isinstance(notes, list) else []
    note_ids = {n.get("note_id") for n in notes if isinstance(n, dict)}

    used_params, rule_clauses, excl_clauses = set(), set(), []
    for i, r in enumerate(rules):
        w = f"rules[{i}]"
        if not isinstance(r, dict):
            errors.append(f"E-SCHEMA: {w} must be an object")
            continue
        missing, extra = RULE_REQUIRED - set(r), set(r) - RULE_KEYS
        if missing:
            errors.append(f"E-SCHEMA: {w} missing fields {sorted(missing)}")
        if extra:
            errors.append(f"E-SCHEMA: {w} unknown fields {sorted(extra)}")
        want = f"CPR-{i + 1:02d}"
        if r.get("rule_id") != want:
            errors.append(f"E-ID: {w} rule_id is {r.get('rule_id')!r}, expected {want!r} (IDs must be sequential)")
        w = f"{r.get('rule_id', w)}"
        cl, pg = r.get("clause"), r.get("page")
        if cl not in inv:
            errors.append(f"E-COVER: {w}: clause {cl!r} is not a clause of the PDF (see --inventory)")
        else:
            rule_clauses |= expand(r, inv)
        if not is_int(pg) or not 1 <= pg <= npages:
            errors.append(f"E-SCHEMA: {w}: page must be an integer 1..{npages}")
        elif cl in inv and not inv[cl] <= pg <= inv[cl] + 1:
            errors.append(f"E-QUOTE: {w}: page {pg} is not where clause {cl} sits (starts on page {inv[cl]})")
        if r.get("type") not in RULE_TYPES:
            errors.append(f"E-SCHEMA: {w}: type {r.get('type')!r} not in {sorted(RULE_TYPES)}")
        sc = r.get("scope")
        if not (isinstance(sc, list) and sc and set(sc) <= SCOPES and (sc == ["all"] or "all" not in sc)):
            errors.append(f"E-SCHEMA: {w}: scope must be a non-empty list from {sorted(SCOPES)} ('all' alone)")
        for f in ("condition", "required_action"):
            if f in r:
                check_str(r[f], f"{w}.{f}", errors)
        if "approver" in r and r["approver"] is not None:
            check_str(r["approver"], f"{w}.approver", errors)
        ev = r.get("evidence_source")
        if not (isinstance(ev, list) and ev and set(ev) <= EVIDENCE):
            errors.append(f"E-SCHEMA: {w}: evidence_source must be a non-empty list from {sorted(EVIDENCE)}")
        for f in ("threshold_low", "threshold_high"):
            if f in r:
                check_bound(r[f], f"{w}.{f}", params, errors)
                if isinstance(r[f], dict) and r[f].get("param"):
                    used_params.add(r[f]["param"])
        for ref in r.get("notes_ref", []) or []:
            if ref not in note_ids:
                errors.append(f"E-SCHEMA: {w}: notes_ref {ref!r} does not exist in notes")
        q = r.get("verbatim_quote")
        if not isinstance(q, str) or len(squash(q)) < MIN_QUOTE_CHARS:
            errors.append(f"E-QUOTE: {w}: verbatim_quote missing or shorter than {MIN_QUOTE_CHARS} characters")
        elif is_int(pg) and 1 <= pg <= npages and not quote_on_page(pdf, pg, q):
            errors.append(f"E-QUOTE: {w}: quote not found on PDF page {pg}: {q[:70]!r}")

    for i, e in enumerate(excluded):
        w = f"excluded[{i}]"
        if not isinstance(e, dict):
            errors.append(f"E-SCHEMA: {w} must be an object")
            continue
        missing, extra = {"clause", "page", "reason"} - set(e), set(e) - EXCL_KEYS
        if missing:
            errors.append(f"E-SCHEMA: {w} missing fields {sorted(missing)}")
        if extra:
            errors.append(f"E-SCHEMA: {w} unknown fields {sorted(extra)}")
        check_str(e.get("reason"), f"{w}.reason", errors, oneline=True)
        pg = e.get("page")
        if not is_int(pg) or not 1 <= pg <= npages:
            errors.append(f"E-SCHEMA: {w}: page must be an integer 1..{npages}")
        if e.get("clause") not in inv:
            errors.append(f"E-COVER: {w}: clause {e.get('clause')!r} is not a clause of the PDF (see --inventory)")
        else:
            excl_clauses.append(expand(e, inv))
    for ids in excl_clauses:
        for c in ids - set(inv):
            errors.append(f"E-COVER: excluded entry covers unknown clause {c!r}")
    seen = set()
    for ids in excl_clauses:
        dup = ids & seen
        if dup:
            errors.append(f"E-COVER: clauses excluded more than once: {sorted(dup, key=sort_key)}")
        seen |= ids
    both = rule_clauses & seen
    if both:
        errors.append(f"E-COVER: clauses in both rules and excluded: {sorted(both, key=sort_key)}")
    for c in rule_clauses - set(inv):
        errors.append(f"E-COVER: rule covers unknown clause {c!r}")
    unc = sorted(set(inv) - rule_clauses - seen, key=sort_key)
    if unc:
        errors.append(f"E-COVER: {len(unc)} clause(s) in neither rules nor excluded: {unc}")
    if not any(isinstance(r, dict) and r.get("type") == "anti-avoidance" for r in rules):
        errors.append("E-ANTI: no rule has type 'anti-avoidance' (the no-splitting rule must be flagged)")
    for p in set(params) - used_params:
        warns.append(f"W-PARAM: parameter {p} is declared but no rule bound uses it")

    for i, n in enumerate(notes):
        w = f"notes[{i}]"
        if not isinstance(n, dict) or set(n) != NOTE_KEYS:
            errors.append(f"E-SCHEMA: {w} must have exactly {sorted(NOTE_KEYS)}")
            continue
        if n["note_id"] != f"N-{i + 1:02d}":
            errors.append(f"E-ID: {w} note_id is {n['note_id']!r}, expected 'N-{i + 1:02d}'")
        if n["kind"] not in NOTE_KINDS:
            errors.append(f"E-SCHEMA: {w}: kind {n['kind']!r} not in {sorted(NOTE_KINDS)}")
        check_str(n["description"], f"{w}.description", errors)
        if not (isinstance(n["clauses"], list) and n["clauses"] and all(c in inv for c in n["clauses"])):
            errors.append(f"E-COVER: {w}: clauses must be a non-empty list of PDF clauses")
        if not (isinstance(n["evidence"], list) and n["evidence"]):
            errors.append(f"E-SCHEMA: {w}: evidence must be a non-empty list of {{page, quote}}")
            continue
        for j, ev in enumerate(n["evidence"]):
            if not (isinstance(ev, dict) and set(ev) == {"page", "quote"} and is_int(ev["page"])
                    and 1 <= ev["page"] <= npages and isinstance(ev["quote"], str)):
                errors.append(f"E-SCHEMA: {w}.evidence[{j}] must be {{page, quote}} with a valid page")
            elif len(squash(ev["quote"])) < MIN_QUOTE_CHARS or not quote_on_page(pdf, ev["page"], ev["quote"]):
                errors.append(f"E-QUOTE: {w}.evidence[{j}]: quote not found on PDF page {ev['page']}: {ev['quote'][:70]!r}")
    return errors, warns, inv


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pdf", default="data/contract-rules.pdf")
    ap.add_argument("--rules", default="outputs/rules.json")
    ap.add_argument("--inventory", action="store_true", help="print the clause inventory (id, page) and exit")
    a = ap.parse_args()
    if a.inventory:
        inv, problems = inventory(a.pdf)
        for k in sorted(inv, key=sort_key):
            print(f"{k}\t{inv[k]}")
        for p in problems:
            print("PROBLEM:", p, file=sys.stderr)
        sys.exit(1 if problems else 0)
    try:
        with open(a.rules, encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"E-SCHEMA: cannot read {a.rules}: {e}")
        sys.exit(1)
    errors, warns, inv = verify(doc, a.pdf)
    for w in warns:
        print(w)
    for e in errors:
        print(e)
    n = lambda k: len(doc.get(k, [])) if isinstance(doc, dict) and isinstance(doc.get(k), list) else 0
    print(f"{'FAIL' if errors else 'PASS'}: {n('rules')} rules, {n('excluded')} excluded, "
          f"{n('notes')} notes, {len(inv)} PDF clauses; {len(errors)} error(s), {len(warns)} warning(s)")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
