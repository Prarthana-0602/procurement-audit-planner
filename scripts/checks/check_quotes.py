#!/usr/bin/env python3
"""Quote check. (1) Runs the extract-rules verifier on rules.json against
data/contract-rules.pdf: schema, every verbatim_quote on its stated page, every clause
accounted for. (2) Every rule quote excerpt in risk-register.md matches rules.json:
a blockquote line (starting >) or a quoted passage (“...” or "...") on a line that names
a rule id (CPR-nn) must be a passage of that rule's verbatim_quote, ignoring whitespace.
    .venv/bin/python scripts/checks/check_quotes.py [--root DIR]
"""
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROJECT, cli, read_json, read_text, result  # noqa: E402

VERIFIER = PROJECT / ".claude" / "skills" / "extract-rules" / "verify_quotes.py"
QUOTED = re.compile(r"[“\"]([^“”\"]{10,})[”\"]")
RULE_ID = re.compile(r"\bCPR-\d+\b")
MIN_EXCERPT = 10


def squash(s):
    return re.sub(r"\s+", "", s.replace("­", "")).lower()


def check(root):
    items = []
    pdf, rules_path = root / "data" / "contract-rules.pdf", root / "outputs" / "rules.json"
    if not pdf.exists():
        items.append(f"contract-rules.pdf not found: {pdf}")
    rules = read_json(rules_path, items, "rules.json")
    if items:
        return result("check_quotes", items, "")
    p = subprocess.run([sys.executable, str(VERIFIER), "--pdf", str(pdf), "--rules", str(rules_path)],
                       capture_output=True, text=True)
    verifier_line = next((l for l in reversed(p.stdout.strip().splitlines()) if l.startswith(("PASS", "FAIL"))), "")
    if p.returncode != 0:
        items += [f"verify_quotes.py: {l}" for l in (p.stdout + p.stderr).strip().splitlines() if l.strip()][:30]
    quotes = {r["rule_id"]: squash(r["verbatim_quote"]) for r in rules.get("rules", [])}
    text = read_text(root / "outputs" / "risk-register.md", items, "risk-register.md")
    n = 0
    for i, line in enumerate((text or "").split("<!-- risk-register-state")[0].splitlines(), 1):
        ids = RULE_ID.findall(line)
        excerpts = [m.group(1) for m in QUOTED.finditer(line)] + ([line.lstrip("> ").strip()] if line.startswith(">") else [])
        for ex in excerpts:
            if not ids:
                if line.startswith(">"):
                    items.append(f"risk-register.md line {i}: quoted excerpt with no rule id: {ex[:60]!r}")
                continue
            n += 1
            if len(ex.strip()) < MIN_EXCERPT:
                continue
            if not any(rid in quotes and squash(ex.strip(" .…")) in quotes[rid] for rid in ids):
                items.append(f"risk-register.md line {i}: excerpt not in the verbatim_quote of {', '.join(ids)}: {ex[:70]!r}")
    return result("check_quotes", items,
                  f"{verifier_line or 'verify_quotes PASS'}; {n} register excerpt(s) checked against rules.json")


if __name__ == "__main__":
    sys.exit(cli(check, __doc__.split("\n\n")[0]))
