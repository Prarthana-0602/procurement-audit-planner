#!/usr/bin/env python3
"""Test scripts/verify_history.py on a good fixture and on copies with one
planted error each. Run from the project root:
    .venv/bin/python scripts/test_verify_history.py
Uses the real PDFs in data/committee (read-only)."""
import copy
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import verify_history as vh  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
GOOD = json.load(open(os.path.join(HERE, "fixtures", "history_good.json"), encoding="utf-8"))
PDF_DIR = "data/committee"


def mutate(fn):
    h = copy.deepcopy(GOOD)
    fn(h)
    return h


def drop(key):
    return lambda h: h.pop(key)


CASES = [
    # (name, mutation, substring expected in the errors)
    ("wrong page", lambda h: h["audit_opinions"][0].update(pdf_page=2), "quote not on"),
    ("page out of range", lambda h: h["audit_opinions"][0].update(pdf_page=9), "outside"),
    ("page not an integer", lambda h: h["audit_opinions"][0].update(pdf_page="1"), "must be an integer"),
    ("one word changed", lambda h: h["audit_opinions"][0].update(
        quote="Contract Letting | Reasonable Assurances"), "quote not on"),
    ("case changed", lambda h: h["risk_themes"][0].update(quote="procurement contract"), "quote not on"),
    ("opinion borrowed from another row", lambda h: h["audit_opinions"][0].update(
        quote="Contract Letting | Substantial Assurance"), "quote not on"),
    # Adjacent rows of a packed table fall inside the fragment window, so here
    # the opinion-field cross-check is what catches the borrowed word.
    ("follow-up implementation changed", lambda h: h["follow_ups"][0].update(
        quote="Garland (now Burghfield | Weak | Satisfactory"), "is not in its own quote"),
    ("en dash swapped for hyphen", lambda h: h["follow_ups"][1].update(
        quote="Fixed Asset Register | Advisory - no | Satisfactory"), "quote not on"),
    ("fragments out of order", lambda h: h["audit_opinions"][1].update(
        quote="Reasonable Assurance | Systems Security (Firewall, | Antivirus, Traffic Management)"),
     "quote not on"),
    ("invented quote", lambda h: h["risk_themes"][0].update(
        quote="Procurement fraud is the council's highest risk"), "quote not on"),
    ("unknown file", lambda h: h["audit_opinions"][0].update(source_file="no-such.pdf"), "not found"),
    ("quote too short", lambda h: h["risk_themes"][0].update(quote="Risk"), "shorter than"),
    ("fragment too short", lambda h: h["audit_opinions"][0].update(
        quote="Contract Letting | Re"), "too short"),
    ("quote without source", lambda h: h["risk_themes"][0].pop("source_file"),
     "quote without source_file"),
    ("source without quote", lambda h: h["risk_themes"][0].pop("quote"),
     "without a quote"),
    ("opinion not in its quote", lambda h: h["audit_opinions"][0].update(opinion="Limited Assurance"),
     "is not in its own quote"),
    ("title not on page", lambda h: h["audit_opinions"][0].update(audit_title="Payroll"),
     "audit_title"),
    ("matrix score wrong", lambda h: h["scoring_method"]["matrix"]["cells"][7].update(score=99),
     "score 99 !="),
    ("matrix cell missing", lambda h: h["scoring_method"]["matrix"]["cells"].pop(),
     "expected 25"),
    ("matrix cell duplicated", lambda h: h["scoring_method"]["matrix"]["cells"].__setitem__(
        3, dict(h["scoring_method"]["matrix"]["cells"][2])), "duplicate cell"),
    ("duplicate id", lambda h: h["audit_opinions"][1].update(id="OP-01"), "duplicate id"),
    ("missing id", lambda h: h["gaps"][0].pop("id"), "no id"),
    ("missing section: gaps", drop("gaps"), "missing top-level section: gaps"),
    ("section wrong type", lambda h: h.update(gaps={}), "must be a list"),
    ("empty gap", lambda h: h["gaps"].append({"id": "GP-02"}), "empty entry"),
    ("bad quote inside discrepancy evidence", lambda h: h["discrepancies"][0]["evidence"][0].update(
        pdf_page=15), "quote not on"),
]


def main():
    fails = 0
    errs, _ = vh.verify(GOOD, PDF_DIR)
    if errs:
        fails += 1
        print("FAIL good fixture should pass, got:", errs)
    else:
        print("ok   good fixture passes")
    for name, fn, want in CASES:
        errs, _ = vh.verify(mutate(fn), PDF_DIR)
        if any(want in e for e in errs):
            print(f"ok   {name}")
        else:
            fails += 1
            print(f"FAIL {name}: expected an error containing {want!r}, got {errs}")
    print("PASS" if not fails else f"FAIL ({fails})")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
