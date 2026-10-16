#!/usr/bin/env python3
"""Number check. Every figure of three or more digits, or with a £ sign, in
planning-memo.md, risk-control-matrix.md and audit-program.md must be a value in
analytics.json, pack-figures.json, rules.json or outputs/samples/*.csv.
Skipped: row ids, rule/test/control/risk/PBC ids, citation tags, dates and times, years,
clause and page references, code spans (file names), and the clause/page columns of
the rule-coverage table.
    .venv/bin/python scripts/checks/check_numbers.py [--root DIR]
"""
import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROW_ID_RE, cli, read_json, read_text, result  # noqa: E402

DOCS = ["planning-memo.md", "risk-control-matrix.md", "audit-program.md"]
NUM = re.compile(r"(?<![\w.\-/])(£\s?)?(\d[\d,]*(?:\.\d+)?)(\s?(?:m\b|k\b|million|bn\b))?")
STRIP = [  # removed before scanning
    re.compile(r"\[(?:rule|metric|history):[^\]]*\]"),
    re.compile(r"`[^`]*`"),
    re.compile(r"\$\.[\w.\[\]\-]+"),
    re.compile(r"\b\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}(?::\d{2})?(?: UTC)?)?\b"),
    re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b"),
    re.compile(r"\b(?:19|20)\d{2}(?:[/\-–]\d{2,4})?\b"),
    re.compile(r"\b[A-Za-z]{1,5}-\d+\b"),
    re.compile(r"\b(?:clauses?|sections?|paras?|paragraphs?|pages?|pp?\.|appendix [A-Z] row)\s*[\w.]+(?:\s*[-–,]\s*\d[\w.]*)*", re.I),
]
RULE_ROW = re.compile(r"^\|\s*CPR-\d+\s*\|[^|]*\|[^|]*\|[^|]*\|")


def leaves(o, out):
    if isinstance(o, bool):
        return
    if isinstance(o, (int, float)):
        out.add(float(o))
    elif isinstance(o, dict):
        for v in o.values():
            leaves(v, out)
    elif isinstance(o, list):
        for v in o:
            leaves(v, out)
    elif isinstance(o, str):  # numbers written inside source strings (e.g. thresholds in a condition)
        for m in re.finditer(r"\d[\d,]*(?:\.\d+)?", o):
            try:
                out.add(float(m.group(0).replace(",", "")))
            except ValueError:
                pass


def known_values(root, items):
    vals = set()
    for name in ("analytics.json", "pack-figures.json", "rules.json"):
        d = read_json(root / "outputs" / name, items)
        if d is not None:
            leaves(d, vals)
    for f in sorted((root / "outputs" / "samples").glob("*.csv")):
        with open(f, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                for v in row.values():
                    try:
                        vals.add(float(v))
                    except (TypeError, ValueError):
                        pass
    return vals


def matches(tok, dec, vals_i, vals_d):
    return round(tok) in vals_i if dec == 0 else round(tok, min(dec, 2)) in vals_d


def scan_line(line):
    t = ROW_ID_RE.sub(" ", line)
    if RULE_ROW.match(t):
        t = "|".join(t.split("|")[5:])
    for rx in STRIP:
        t = rx.sub(" ", t)
    for m in NUM.finditer(t):
        pound, body, suffix = m.group(1), m.group(2), (m.group(3) or "").strip().lower()
        digits = re.sub(r"\D", "", body)
        if not pound and len(digits) < 3:
            continue
        val = float(body.replace(",", "").rstrip(","))
        val *= {"m": 1e6, "million": 1e6, "k": 1e3, "bn": 1e9}.get(suffix, 1)
        dec = len(body.split(".")[1]) if "." in body and not suffix else 0
        yield m.group(0).strip(), val, dec


def check(root):
    items = []
    vals = known_values(root, items)
    vals_i = {round(v) for v in vals}
    vals_d = {round(v, 2) for v in vals} | {round(v, 1) for v in vals}
    n = 0
    for doc in DOCS:
        text = read_text(root / "outputs" / doc, items)
        if text is None:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            for raw, val, dec in scan_line(line):
                n += 1
                if not matches(val, dec, vals_i, vals_d):
                    items.append(f"{doc} line {i}: {raw} is not a value in analytics.json, pack-figures.json, rules.json or samples/*.csv")
    return result("check_numbers", items, f"{n} figure(s) in the three documents all found in the source values")


if __name__ == "__main__":
    sys.exit(cli(check, __doc__.split("\n\n")[0]))
