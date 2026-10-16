#!/usr/bin/env python3
"""Verify outputs/history.json against the PDFs in data/committee/.

Usage (from the project root):
    .venv/bin/python scripts/verify_history.py
        [--history outputs/history.json] [--pdf-dir data/committee]

Checks:
  * top-level shape: required sections present, lists are lists, ids unique
  * every object that carries a `quote` also carries `source_file` + `pdf_page`
    (and every object that carries `source_file` carries a `quote`)
  * source_file exists in --pdf-dir and pdf_page is inside the document
  * every quote is on its stated page. Matching ignores whitespace only (case,
    punctuation and dash types must match exactly). A quote is checked against
    the plain text and the -layout text of that page. A table row may be quoted
    as fragments joined by " | "; each fragment must be on the page and the
    fragments must appear in that order within a few consecutive layout lines
    (one table row), so fragments cannot be borrowed from different rows.
  * opinion fields (opinion, report_opinion, implementation_opinion) appear in
    their own quote; audit_title appears on the stated page
  * scoring_method.matrix cells: 25 distinct (likelihood, impact) pairs, each
    score == likelihood x impact
  * a gap or discrepancy may not be empty of content

Exit code 0 = pass, 1 = errors. Needs pdftotext and pdfinfo (poppler).
Standard library only.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from functools import lru_cache

REQUIRED_SECTIONS = {
    "documents": list,
    "audit_opinions": list,
    "follow_ups": list,
    "agreed_actions": list,
    "risk_themes": list,
    "scoring_method": dict,
    "strategic_risk_register": dict,
    "discrepancies": list,
    "gaps": list,
}
ID_SECTIONS = ["audit_opinions", "follow_ups", "agreed_actions", "risk_themes",
               "discrepancies", "gaps"]
OPINION_FIELDS = ["opinion", "report_opinion", "implementation_opinion"]
MIN_QUOTE_CHARS = 10
MIN_FRAGMENT_CHARS = 4
SEP = " | "
MAX_ROW_LINES = 4  # a table row may wrap over this many non-blank layout lines


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout


@lru_cache(maxsize=None)
def page_count(pdf):
    m = re.search(r"^Pages:\s+(\d+)", run(["pdfinfo", pdf]), re.M)
    return int(m.group(1))


@lru_cache(maxsize=None)
def page_text(pdf, n, layout):
    cmd = ["pdftotext", "-f", str(n), "-l", str(n)] + (["-layout"] if layout else []) + [pdf, "-"]
    return run(cmd)


def squash(s):
    """Whitespace-free form used for matching (tables and wraps break spacing)."""
    return re.sub(r"\s+", "", s.replace("­", ""))


def squash_hyphen_tolerant(s):
    # pdftotext can drop the hyphen of a hyphenated line break ("Call-\nIn" -> "CallIn")
    return squash(s).replace("-", "")


def found(needle, hay):
    return needle in hay or needle.replace("-", "") in hay.replace("-", "")


def fragments_in_row(pdf, page, fragments):
    """True if the fragments appear in order, all within MAX_ROW_LINES
    consecutive non-blank layout lines (so they belong to one table row)."""
    lines = [squash(l) for l in page_text(pdf, page, True).splitlines() if l.strip()]
    starts, text = [], ""
    for l in lines:
        starts.append(len(text))
        text += l
    qs = [squash(f) for f in fragments]

    def line_of(pos):
        return max(i for i, st in enumerate(starts) if st <= pos)

    first = text.find(qs[0])
    while first >= 0:
        pos, last_end, ok = first, first, True
        for q in qs:
            i = text.find(q, pos)
            if i < 0:
                ok = False
                break
            last_end = i + len(q)
            pos = last_end
        if ok and line_of(last_end - 1) - line_of(first) < MAX_ROW_LINES:
            return True
        first = text.find(qs[0], first + 1)
    return False


def quote_on_page(pdf, page, quote):
    """Return (ok, how). `how` names the text mode that matched."""
    fragments = quote.split(SEP)
    if len(fragments) == 1:
        q = squash(fragments[0])
        if found(q, squash(page_text(pdf, page, False))):
            return True, "plain"
        if found(q, squash(page_text(pdf, page, True))):
            return True, "layout"
        return False, None
    return (True, "layout-fragments") if fragments_in_row(pdf, page, fragments) else (False, None)


def walk(node, path=""):
    """Yield (path, dict) for every dict in the document."""
    if isinstance(node, dict):
        yield path, node
        for k, v in node.items():
            yield from walk(v, f"{path}.{k}" if path else k)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk(v, f"{path}[{i}]")


def check_shape(h, errs):
    if not isinstance(h, dict):
        errs.append("top level is not an object")
        return False
    for key, typ in REQUIRED_SECTIONS.items():
        if key not in h:
            errs.append(f"missing top-level section: {key}")
        elif not isinstance(h[key], typ):
            errs.append(f"section {key} must be a {typ.__name__}")
    seen = set()
    for sec in ID_SECTIONS:
        for i, item in enumerate(h.get(sec, []) if isinstance(h.get(sec), list) else []):
            iid = item.get("id") if isinstance(item, dict) else None
            if not iid:
                errs.append(f"{sec}[{i}]: no id")
            elif iid in seen:
                errs.append(f"{sec}[{i}]: duplicate id {iid}")
            else:
                seen.add(iid)
    return not errs


def check_matrix(h, errs):
    sm = h.get("scoring_method")
    if not isinstance(sm, dict):
        return
    m = sm.get("matrix")
    if not m:
        return
    cells = m.get("cells") if isinstance(m, dict) else None
    if not isinstance(cells, list):
        errs.append("scoring_method.matrix.cells missing or not a list")
        return
    pairs = set()
    for i, c in enumerate(cells):
        try:
            l, im, s = int(c["likelihood"]), int(c["impact"]), int(c["score"])
        except (KeyError, TypeError, ValueError):
            errs.append(f"matrix.cells[{i}]: needs integer likelihood, impact, score")
            continue
        if (l, im) in pairs:
            errs.append(f"matrix.cells[{i}]: duplicate cell likelihood={l} impact={im}")
        pairs.add((l, im))
        if s != l * im:
            errs.append(f"matrix.cells[{i}]: score {s} != likelihood {l} x impact {im}")
    if len(pairs) != 25:
        errs.append(f"matrix has {len(pairs)} distinct cells, expected 25")


def verify(history, pdf_dir):
    errs, stats = [], {"quotes": 0, "plain": 0, "layout": 0, "layout-fragments": 0}
    if not check_shape(history, errs):
        return errs, stats
    check_matrix(history, errs)

    for path, d in walk(history):
        has_q = "quote" in d
        has_src = "source_file" in d or "pdf_page" in d
        if not has_q and not has_src:
            continue
        where = path or "(root)"
        if has_q and not ("source_file" in d and "pdf_page" in d):
            errs.append(f"{where}: quote without source_file and pdf_page")
            continue
        if has_src and not has_q:
            errs.append(f"{where}: source_file/pdf_page without a quote")
            continue
        sf, pg, q = d["source_file"], d["pdf_page"], d["quote"]
        if not isinstance(q, str) or len(squash(q)) < MIN_QUOTE_CHARS:
            errs.append(f"{where}: quote missing or shorter than {MIN_QUOTE_CHARS} characters")
            continue
        if not isinstance(pg, int) or isinstance(pg, bool):
            errs.append(f"{where}: pdf_page must be an integer, got {pg!r}")
            continue
        pdf = os.path.join(pdf_dir, str(sf))
        if not os.path.isfile(pdf):
            errs.append(f"{where}: source_file not found in {pdf_dir}: {sf}")
            continue
        n = page_count(pdf)
        if not 1 <= pg <= n:
            errs.append(f"{where}: pdf_page {pg} outside {sf} (1-{n})")
            continue
        short = [f for f in q.split(SEP) if len(squash(f)) < MIN_FRAGMENT_CHARS]
        if short:
            errs.append(f"{where}: quote fragment too short to verify: {short[0]!r}")
            continue
        stats["quotes"] += 1
        ok, how = quote_on_page(pdf, pg, q)
        if not ok:
            errs.append(f"{where}: quote not on {sf} page {pg}: {q[:80]!r}")
            continue
        stats[how] += 1
        sq = squash(q.replace(SEP, ""))
        for f in OPINION_FIELDS:
            if f in d and squash(str(d[f])) not in sq:
                errs.append(f"{where}: {f} {d[f]!r} is not in its own quote")
        if "audit_title" in d:
            t = squash(str(d["audit_title"]))
            if not (found(t, squash(page_text(pdf, pg, False))) or
                    found(t, squash(page_text(pdf, pg, True)))):
                errs.append(f"{where}: audit_title {d['audit_title']!r} not on {sf} page {pg}")

    for sec in ("gaps", "discrepancies"):
        for i, item in enumerate(history.get(sec, [])):
            if isinstance(item, dict) and not any(
                    isinstance(v, str) and v.strip() for k, v in item.items() if k != "id"):
                errs.append(f"{sec}[{i}]: empty entry")
    return errs, stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--history", default="outputs/history.json")
    ap.add_argument("--pdf-dir", default="data/committee")
    a = ap.parse_args()
    try:
        with open(a.history, encoding="utf-8") as fh:
            history = json.load(fh)
    except (OSError, json.JSONDecodeError) as e:
        print(f"FAIL: cannot read {a.history}: {e}")
        return 1
    errs, stats = verify(history, a.pdf_dir)
    for e in errs:
        print("ERROR:", e)
    print(f"quotes checked: {stats['quotes']} (plain {stats['plain']}, layout {stats['layout']}, "
          f"layout-fragments {stats['layout-fragments']})")
    print("PASS" if not errs else f"FAIL ({len(errs)} errors)")
    return 0 if not errs else 1


if __name__ == "__main__":
    sys.exit(main())
