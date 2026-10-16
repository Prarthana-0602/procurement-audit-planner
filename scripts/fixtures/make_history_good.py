"""Writes scripts/fixtures/history_good.json: a small, correct history.json
built from real quotes, used by test_verify_history.py as the baseline that
planted errors are applied to. Run from the project root."""
import json

A = "audit-completed-work-2024-25-annual.pdf"
R = "risk-management-strategy-2024-27.pdf"
cells = [{"likelihood": l, "impact": i, "score": l * i} for i in range(1, 6) for l in range(1, 6)]
good = {
    "documents": [{"file": A, "pages": 2}, {"file": R, "pages": 35}],
    "audit_opinions": [
        {"id": "OP-01", "source_file": A, "pdf_page": 1, "service": "Finance, Property and Procurement",
         "audit_title": "Contract Letting", "opinion": "Reasonable Assurance",
         "quote": "Contract Letting | Reasonable Assurance"},
        {"id": "OP-02", "source_file": A, "pdf_page": 1, "service": "Transformation",
         "audit_title": "Systems Security (Firewall, Antivirus, Traffic Management)",
         "opinion": "Reasonable Assurance",
         "quote": "Systems Security (Firewall, | Reasonable Assurance | Antivirus, Traffic Management)"},
    ],
    "follow_ups": [
        {"id": "FU-01", "source_file": A, "pdf_page": 2, "audit_title": "Garland (now Burghfield",
         "report_opinion": "Weak", "implementation_opinion": "Unsatisfactory",
         "quote": "Garland (now Burghfield | Weak | Unsatisfactory"},
        {"id": "FU-02", "source_file": A, "pdf_page": 1, "audit_title": "Fixed Asset Register",
         "implementation_opinion": "Satisfactory",
         "quote": "Fixed Asset Register | Advisory \u2013 no | Satisfactory"},
    ],
    "agreed_actions": [],
    "risk_themes": [
        {"id": "RT-01", "theme": "Contracts & Partnerships", "source_file": R, "pdf_page": 33,
         "quote": "Procurement contract"},
    ],
    "scoring_method": {
        "usable": True,
        "impact_scale": {"source_file": R, "pdf_page": 14,
                         "quote": "Major financial loss £1,000+"},
        "matrix": {"source_file": R, "pdf_page": 18, "quote": "5x5 Risk Matrix Assessments",
                   "cells": cells},
    },
    "strategic_risk_register": {"present": False, "source_file": R, "pdf_page": 28,
                                "quote": "risk is reported as a Part II (confidential information) report to the"},
    "discrepancies": [
        {"id": "DI-01", "description": "Text names Medium as (2); table scores it 3.",
         "evidence": [
             {"source_file": R, "pdf_page": 14, "quote": "Negligible (1), Minor (2), Medium (2), Major (4), or"},
             {"source_file": R, "pdf_page": 18, "quote": "5x5 Risk Matrix Assessments"}]},
    ],
    "gaps": [{"id": "GP-01", "what": "No agreed-actions table in the papers."}],
}
with open("scripts/fixtures/history_good.json", "w", encoding="utf-8") as f:
    json.dump(good, f, indent=1, ensure_ascii=False)
