#!/usr/bin/env python3
"""Regenerate the fixtures for test_build_register.py from the real outputs.
Run from the project root: .venv/bin/python .claude/skills/risk-assessment/fixtures/make_fixtures.py
The fixtures are small: the real scoring method, 3 audit items, 2 discrepancy
kinds, 3 tests and 2 rules."""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[4]
here = Path(__file__).resolve().parent
h = json.load(open(root / "outputs/history.json"))
a = json.load(open(root / "outputs/analytics.json"))
r = json.load(open(root / "outputs/rules.json"))
keep_op = {"OP-01", "OP-12"}
hist = {
    "scoring_method": h["scoring_method"],
    "audit_opinions": [o for o in h["audit_opinions"] if o["id"] in keep_op],
    "follow_ups": [f for f in h["follow_ups"] if f["id"] == "FU-02"],
    "risk_themes": [], "gaps": [],
    "discrepancies": [d for d in h["discrepancies"] if d["id"] in {"DISC-01", "DISC-02", "DISC-03", "DISC-04"}],
}
ana = {"population": {"gbp_analysed": a["population"]["gbp_analysed"], "rows_analysed": a["population"]["rows_analysed"]},
       "tests": {k: {kk: vv for kk, vv in a["tests"][k].items() if kk != "top20"}
                 for k in ("off_contract", "split_purchases", "duplicates")}}
ana["tests"]["off_contract"]["top20"] = a["tests"]["off_contract"]["top20"][:2]
rules = {"rules": [x for x in r["rules"] if x["rule_id"] in {"CPR-59", "CPR-60"}]}
ratings = {"risks": [
    {"id": "R-01", "title": "Spend with suppliers above the quote tier that has no matching contract notice",
     "description": "Indicator that suppliers above the quote tier may lack the contract or quote evidence the rules expect.",
     "likelihood": {"score": 4, "justification":
        "Two indicator tests fire: {{$.tests.off_contract.count}} suppliers have no matching notice [metric:$.tests.off_contract.count] "
        "and {{$.tests.split_purchases.counts}} supplier episodes cross a tier [metric:$.tests.split_purchases.counts]. "
        "The prior audit of the same theme gave a Limited Assurance opinion [history:OP-12]."},
     "repeat_finding": {"history": ["OP-12"], "note": "same theme: direct payments and care purchasing controls"},
     "impact": {"score": 4, "justification":
        "Annualised spend without a notice is {{$.tests.off_contract.annualised_estimate_gbp|gbp}}, above the Major band's financial scale, "
        "and the quote rule is mandatory [rule:CPR-59] [metric:$.tests.off_contract.annualised_estimate_gbp]."},
     "evidence": ["Off-contract indicator covers {{$.tests.off_contract.count}} suppliers [metric:$.tests.off_contract.count].",
                  "Quote requirement [rule:CPR-59]."],
     "proposed_focus": "Request contract and quote evidence for the highest-value suppliers without a notice."},
    {"id": "R-02", "title": "Unsupported risk with an invented citation",
     "description": "This risk cites evidence that does not exist.",
     "likelihood": {"score": 3, "justification": "Probably common [metric:$.tests.no_such_test.count] [rule:CPR-999]."},
     "impact": {"score": 3, "justification": "Likely costs about £2,000,000 a year and 45 payments [history:OP-99]."},
     "evidence": ["Nothing resolves."], "proposed_focus": "None."}]}
for name, obj in (("history.json", hist), ("analytics.json", ana), ("rules.json", rules), ("risk-ratings.json", ratings)):
    (here / name).write_text(json.dumps(obj, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print("fixtures written")
