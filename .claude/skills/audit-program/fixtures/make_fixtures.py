#!/usr/bin/env python3
"""Write small synthetic fixtures for test_build_pack.py (no real council data).
Two approved risks (R-01 approved, R-02 amended), one rejected (R-03), five rules,
a 30-row spend file and three flagged lists.
Run from the project root: .venv/bin/python .claude/skills/audit-program/fixtures/make_fixtures.py"""
import json
from pathlib import Path

import pandas as pd

here = Path(__file__).resolve().parent
(here / "analytics-full").mkdir(exist_ok=True)


def w(name, obj):
    (here / name).write_text(json.dumps(obj, indent=1), encoding="utf-8")


rules = {"rules": [
    {"rule_id": f"CPR-0{i}", "clause": f"{i}.1", "page": i, "type": t}
    for i, t in enumerate(["procedure", "advertising", "anti-avoidance", "exception", "record-keeping"], 1)]}
w("rules.json", rules)
w("history.json", {"audit_opinions": [{"id": "OP-01", "opinion": "Reasonable Assurance"}], "follow_ups": [],
                   "risk_themes": [], "discrepancies": [], "gaps": []})
w("analytics.json", {"population": {"rows_analysed": 30, "gbp_analysed": 123456.5},
                     "tests": {"off_contract": {"status": "ran", "count": 6, "gbp": 90000.0},
                               "threshold_clustering": {"status": "ran", "count": 4, "gbp": 99000.0}},
                     "caveats": ["Annualised estimates are 3-month totals x 4."]})
w("risk-ratings.json", {"risks": [
    {"id": "R-01", "title": "Spend above the quote tier with no contract notice", "description": "Indicator that spend of {{$.tests.off_contract.gbp|gbp}} may lack a notice [rule:CPR-01].",
     "likelihood": {"score": 2, "justification": "One test [metric:$.tests.off_contract.count]."},
     "impact": {"score": 4, "justification": "Notice rule [rule:CPR-02]."}, "evidence": ["Off-contract [metric:$.tests.off_contract.count]"],
     "proposed_focus": "Request quote evidence."},
    {"id": "R-02", "title": "Payments just below a threshold", "description": "Indicator of clustering [rule:CPR-03].",
     "likelihood": {"score": 3, "justification": "Tests [metric:$.tests.threshold_clustering.count]."},
     "impact": {"score": 3, "justification": "Aggregation rule [rule:CPR-03]."}, "evidence": ["Clustering [metric:$.tests.threshold_clustering.count]"],
     "proposed_focus": "Review the flagged payments."}]})

# spend: 6 suppliers x 5 payments
rows = []
for s in range(6):
    for k in range(5):
        rows.append({"row_id": f"wb|Data to publish|{s * 5 + k + 3}", "file": "wb", "date": f"2026-0{k + 1}-1{s}",
                     "service": "Environment", "category": "Contractors", "narrative": f"Work {k}",
                     "amount": 24000.0 + s * 100 + k, "supplier": f"Supplier Number {s} Ltd",
                     "norm_supplier": f"SUPPLIER NUMBER {s}", "tag": "general_procurement"})
spend = pd.DataFrame(rows)
spend.to_csv(here / "analytics-full/cleaned_spend.csv", index=False)
pd.DataFrame([{"supplier": f"Supplier Number {s} Ltd", "norm_supplier": f"SUPPLIER NUMBER {s}", "gbp": 120000.0 - s * 1000,
               "annualised_estimate": 480000.0 - s * 4000, "payments": 5, "primary_tag": "general_procurement"} for s in range(6)]
             ).to_csv(here / "analytics-full/off_contract.csv", index=False)
pd.DataFrame([{"row_id": r["row_id"], "tier": 25000, "date": r["date"], "supplier": r["supplier"], "norm_supplier": r["norm_supplier"],
               "amount": r["amount"], "tag": "general_procurement"} for r in rows[:10]]
             ).to_csv(here / "analytics-full/threshold_clustering.csv", index=False)
pd.DataFrame([{"tier": 25000, "supplier": f"Supplier Number {s} Ltd", "norm_supplier": f"SUPPLIER NUMBER {s}", "payments": 2,
               "total_gbp": 48000.0, "tag": "general_procurement",
               "row_ids": ";".join(r["row_id"] for r in rows[s * 5:s * 5 + 2])} for s in range(3)]
             ).to_csv(here / "analytics-full/split_purchases.csv", index=False)

register = """# Risk register: fixture

**Status:** REVISION 1

## Summary

| Risk | Title | Likelihood | Impact | Score | Band |
|---|---|---|---|---|---|
| R-02 | Payments just below a threshold | 2 | 3 | 6 | High |
| R-01 | Spend above the quote tier with no contract notice | 2 | 4 | 8 | High |

## Risks

<!-- risk-register-state
{"applied": {}, "rejected": {"R-03": {"title": "Repeat payments", "comment": "AP review", "round": 1}}, "risks": {"R-01": {}, "R-02": {}}, "round": 1}
-->
"""
(here / "risk-register.md").write_text(register, encoding="utf-8")
(here / "auditor-comments.md").write_text("""# Auditor decisions: fixture

| Risk | Title | Rating | Decision | Comment |
|---|---|---|---|---|
| R-01 | Spend above the quote tier with no contract notice | L2 × I4 = 8 High | Approve | Reviewer: Test. |
| R-02 | Payments just below a threshold | L3 × I3 = 9 High | Amend | Reviewer: Test. L=2 |
| R-03 | Repeat payments | removed on rejection | Reject | Covered by a separate AP review. |
""", encoding="utf-8")

w("audit-plan.json", {
    "version": 1,
    "memo": {"background": "The register holds {{@scope.approved}} approved risks; {{$.population.rows_analysed}} payments were analysed.",
             "approach": "Test the flagged populations against the notice and aggregation rules [rule:CPR-02].",
             "limitations": ["Annualised estimate only [metric:$.tests.off_contract.gbp]."]},
    "risks": [
        {"risk_id": "R-01", "rationale": "Approved by the auditor; off-contract indicator [metric:$.tests.off_contract.count].",
         "controls": [{"id": "C-01", "description": "A quote or notice is held for suppliers above the quote tier [rule:CPR-01]."},
                      {"id": "C-02", "description": "Awards above the publication level are advertised [rule:CPR-02]."}],
         "tests": [{"id": "T-01", "control_ids": ["C-01", "C-02"], "step": "Obtain quote and notice evidence for the sampled suppliers [rule:CPR-01] [metric:$.tests.off_contract.count].",
                    "sample": {"file": "off_contract.csv", "filter": [{"col": "primary_tag", "op": "==", "value": "general_procurement"}],
                               "sort": [{"by": "annualised_estimate", "desc": True}], "n": 3, "rows_per_item": 2},
                    "pbc": ["PBC-01"]}]},
        {"risk_id": "R-02", "rationale": "Amended by the auditor; clustering indicator [metric:$.tests.threshold_clustering.count].",
         "controls": [{"id": "C-03", "description": "Purchases are not split to avoid a threshold [rule:CPR-03]."}],
         "tests": [{"id": "T-02", "control_ids": ["C-03"], "step": "Review payments just below the threshold for one underlying need [rule:CPR-03].",
                    "sample": {"file": "threshold_clustering.csv", "sort": [{"by": "amount", "desc": True}], "n": 5, "method": "spread"},
                    "pbc": ["PBC-02"]},
                   {"id": "T-03", "control_ids": ["C-03"], "step": "Check how combined value was estimated [rule:CPR-03] [metric:$.tests.threshold_clustering.count].",
                    "sample": {"file": "split_purchases.csv", "sort": [{"by": "total_gbp", "desc": True}], "n": 2},
                    "pbc": ["PBC-02"]}]}],
    "pbc_items": [{"id": "PBC-01", "item": "Quote and notice evidence for the sampled suppliers."},
                  {"id": "PBC-02", "item": "Estimate of total value for each flagged purchase."}],
    "rules_not_tested": [{"rule_ids": ["CPR-04", "CPR-05"], "reason": "Evidence is in documents the council holds, not in spend or notices."}]})
print("fixtures written to", here)
