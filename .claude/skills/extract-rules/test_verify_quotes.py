#!/usr/bin/env python3
"""Self-test for verify_quotes.py. Run from the project root:
    .venv/bin/python .claude/skills/extract-rules/test_verify_quotes.py
Builds a clean fixture (a few real rules, every other clause excluded), checks it
passes, then applies one deliberate error at a time and checks the verifier
reports the expected code. Also writes fixtures/bad_rules.json (all errors at once).
"""
import copy
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PDF = "data/contract-rules.pdf"
sys.path.insert(0, str(HERE))
import verify_quotes as vq  # noqa: E402

Q_SPLIT = ("There shall be no artificial splitting or disaggregation of a contract to avoid the "
           "application of the provisions of the Procurement Legislation and/or these Rules.")
Q_A = "At least one quote must be sought from an appropriate source."
Q_B1 = "Invitations to quote must be sent via the Procurement Portal to at least three appropriate sources"
Q_NOTE = "There are three different procurement regulation thresholds for"


def bound(amount=None, param=None, inclusive=True):
    return {"amount": amount, "param": param, "inclusive": inclusive}


def clean():
    inv, _ = vq.inventory(PDF)
    rules = [
        dict(rule_id="CPR-01", clause="6.16", page=5, type="anti-avoidance", scope=["all"],
             condition="Any contract", threshold_low=None, threshold_high=None,
             required_action="No artificial splitting of a contract", approver=None,
             evidence_source=["spend"], verbatim_quote=Q_SPLIT),
        dict(rule_id="CPR-02", clause="Appendix B row A", page=12, type="procedure", scope=["all"],
             condition="Above £1,000 and less than £25,000",
             threshold_low=bound(1000, None, False), threshold_high=bound(25000, None, False),
             required_action="Seek at least one quote", approver=None,
             evidence_source=["document-request"], verbatim_quote=Q_A),
        dict(rule_id="CPR-03", clause="Appendix B row B1", page=12, type="procedure",
             scope=["goods_services"], condition="£25,000 or more and less than the Threshold",
             threshold_low=bound(25000, None, True),
             threshold_high=bound(None, "THRESHOLD_GOODS_SERVICES", False),
             required_action="Three invitations to quote via the Portal", approver=None,
             evidence_source=["contracts"], verbatim_quote=Q_B1, notes_ref=["N-01"]),
    ]
    covered = {"6.16", "Appendix B row A", "Appendix B row B1", "10.7", "10.7.1"}
    excluded = [dict(clause="10.7", page=8, reason="Fixture: whole clause excluded.",
                     also_covers=["10.7.*"])]
    covered |= {k for k in inv if k.startswith("10.7.")}
    for k in sorted(inv, key=vq.sort_key):
        if k not in covered:
            excluded.append(dict(clause=k, page=inv[k], reason="Fixture: not a rule."))
    return dict(
        source=dict(file=PDF, pages=15),
        parameters=dict(THRESHOLD_GOODS_SERVICES=None, THRESHOLD_RELEVANT=None),
        rules=rules, excluded=excluded,
        notes=[dict(note_id="N-01", kind="gap", clauses=["Appendix B notes"],
                    description="Fixture note.", evidence=[dict(page=13, quote=Q_NOTE)])])


def codes(doc):
    errors, _, _ = vq.verify(doc, PDF)
    return {e.split(":")[0] for e in errors}, errors


def drop_excluded(d, clause):
    d["excluded"] = [e for e in d["excluded"] if e["clause"] != clause]


MUTATIONS = {
    "altered quote": ("E-QUOTE", lambda d: d["rules"][0].update(verbatim_quote=Q_SPLIT.replace("shall", "must"))),
    "quote on wrong page": ("E-QUOTE", lambda d: d["rules"][1].update(page=11)),
    "page outside the PDF": ("E-SCHEMA", lambda d: d["rules"][1].update(page=16)),
    "page far from the clause": ("E-QUOTE", lambda d: d["rules"][0].update(page=9)),
    "non-sequential rule id": ("E-ID", lambda d: d["rules"][2].update(rule_id="CPR-04")),
    "undeclared parameter": ("E-PARAM", lambda d: d["rules"][2].update(threshold_high=bound(None, "THRESHOLD_WORKS", False))),
    "parameter given a value": ("E-PARAM", lambda d: d["parameters"].update(THRESHOLD_GOODS_SERVICES=139688)),
    "float amount (pence)": ("E-SCHEMA", lambda d: d["rules"][1].update(threshold_high=bound(24999.99, None, False))),
    "inclusive missing": ("E-SCHEMA", lambda d: d["rules"][1].update(threshold_low={"amount": 1000, "param": None})),
    "amount and param both set": ("E-SCHEMA", lambda d: d["rules"][2].update(threshold_low=bound(25000, "THRESHOLD_RELEVANT", True))),
    "missing field": ("E-SCHEMA", lambda d: d["rules"][0].pop("approver")),
    "bad type": ("E-SCHEMA", lambda d: d["rules"][0].update(type="whatever")),
    "bad evidence source": ("E-SCHEMA", lambda d: d["rules"][0].update(evidence_source=["memory"])),
    "unknown clause": ("E-COVER", lambda d: d["rules"][0].update(clause="99.9")),
    "uncovered clause": ("E-COVER", lambda d: drop_excluded(d, "6.17")),
    "clause in rules and excluded": ("E-COVER", lambda d: d["excluded"].append(dict(clause="6.16", page=5, reason="x"))),
    "clause excluded twice": ("E-COVER", lambda d: d["excluded"].append(dict(clause="6.17", page=5, reason="x"))),
    "excluded without reason": ("E-SCHEMA", lambda d: d["excluded"][1].update(reason="")),
    "multi-line reason": ("E-SCHEMA", lambda d: d["excluded"][1].update(reason="a\nb")),
    "no anti-avoidance rule": ("E-ANTI", lambda d: d["rules"][0].update(type="procedure")),
    "fabricated note quote": ("E-QUOTE", lambda d: d["notes"][0]["evidence"][0].update(quote="The Threshold for goods is £139,688.")),
    "note id gap": ("E-ID", lambda d: d["notes"][0].update(note_id="N-02")),
    "dangling notes_ref": ("E-SCHEMA", lambda d: d["rules"][2].update(notes_ref=["N-09"])),
    "wrong source.pages": ("E-SCHEMA", lambda d: d["source"].update(pages=50)),
    "extra top-level key": ("E-SCHEMA", lambda d: d.update(extra=1)),
}


def main():
    failures = 0
    base = clean()
    c, errs = codes(base)
    print(f"clean fixture -> {'PASS' if not c else 'FAIL ' + str(errs[:3])}")
    failures += bool(c)
    for name, (want, mut) in MUTATIONS.items():
        d = copy.deepcopy(base)
        mut(d)
        got, errs = codes(d)
        ok = want in got
        failures += not ok
        print(f"{'ok  ' if ok else 'MISS'} {name:32s} expect {want:9s} got {sorted(got)}")
    # one fixture with many errors at once, run through the real command line
    bad = copy.deepcopy(base)
    for name in ("altered quote", "non-sequential rule id", "undeclared parameter",
                 "parameter given a value", "uncovered clause", "fabricated note quote"):
        MUTATIONS[name][1](bad)
    path = HERE / "fixtures" / "bad_rules.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(bad, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    r = subprocess.run([sys.executable, str(HERE / "verify_quotes.py"), "--pdf", PDF, "--rules", str(path)],
                       capture_output=True, text=True)
    print(f"\nCLI on {path.name}: exit {r.returncode}")
    print("\n".join(r.stdout.splitlines()[:12]))
    failures += r.returncode != 1
    print(f"\n{'ALL TESTS PASSED' if not failures else str(failures) + ' TEST(S) FAILED'}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
