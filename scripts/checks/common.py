"""Shared helpers for the QA checks. Every check returns a dict:
{"name", "status": "PASS"|"FAIL", "summary": one line, "items": [one line per problem]}.
Paths are read from a project root (default: this repository) holding outputs/ and data/."""
import argparse
import json
import re
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
ROW_ID_RE = re.compile(r"[\w\-]+\|Data to publish\|\d+")


def result(name, items, summary_ok, summary_fail=None):
    items = list(items)
    return {"name": name, "status": "FAIL" if items else "PASS",
            "summary": (summary_fail or f"{len(items)} problem(s)") if items else summary_ok, "items": items}


def read_text(path, items, what=None):
    p = Path(path)
    if not p.exists():
        items.append(f"{what or p.name} not found: {p}")
        return None
    return p.read_text(encoding="utf-8")


def read_json(path, items, what=None):
    t = read_text(path, items, what)
    if t is None:
        return None
    try:
        return json.loads(t)
    except json.JSONDecodeError as e:
        items.append(f"{what or Path(path).name} is not valid JSON: {e}")
        return None


def cli(check, description, extra=None):
    """Standard command line for one check script."""
    ap = argparse.ArgumentParser(description=description)
    ap.add_argument("--root", default=str(PROJECT), help="project root holding outputs/ and data/")
    for flag, kw in (extra or {}).items():
        ap.add_argument(flag, **kw)
    a = ap.parse_args()
    r = check(Path(a.root), **{k: v for k, v in vars(a).items() if k != "root"})
    print_result(r)
    return 1 if r["status"] == "FAIL" else 0


def print_result(r, limit=25):
    print(f"{r['status']}: {r['name']}: {r['summary']}")
    for it in r["items"][:limit]:
        print(f"  - {it}")
    if len(r["items"]) > limit:
        print(f"  ... and {len(r['items']) - limit} more")


def main_exit(code):
    sys.exit(code)
