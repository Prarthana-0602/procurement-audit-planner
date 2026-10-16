#!/usr/bin/env python3
"""Build outputs/history.json from quotes typed once here (copied from the extracted PDF text)."""
import json

A = "audit-completed-work-2024-25-annual.pdf"
Q3 = "audit-completed-work-2025-26-q3.pdf"
PL = "internal-audit-plan-2025-28.pdf"
RS = "risk-management-strategy-2024-27.pdf"


def S(f, p, q, **kw):
    d = {"source_file": f, "pdf_page": p, "quote": q}
    d.update(kw)
    return d


H = {}

H["documents"] = [
    {"file": A, "title": "Internal Audit Plan Update Report", "pages": 2, "committee": None, "date": "End of March 2025",
     "contents": "Appendix A completed-work tables (completed audits, completed follow ups, completed advisory reviews/other work) for the period ending March 2025; no covering report in this PDF.",
     **S(A, 1, "Internal Audit Plan Update Report (End of March 2025) Appendix A")},
    {"file": Q3, "title": "Internal Audit Plan Update Report", "pages": 1, "committee": None, "date": "End of December 2025",
     "contents": "Appendix A completed-work tables for the period ending December 2025; no covering report in this PDF.",
     **S(Q3, 1, "Internal Audit Plan Update Report (End of December 2025) Appendix A")},
    {"file": PL, "title": "Internal Audit Plan 2025-2028", "pages": 7, "committee": "Governance Committee", "date": "29th April 2025",
     "contents": "Covering report only (purpose, recommendation, executive summary, supporting information, appendices list). Appendices A-F are listed but not included in this PDF.",
     **S(PL, 1, "Governance Committee Date of Committee: 29th April 2025")},
    {"file": RS, "title": "Risk Management Strategy", "pages": 35, "committee": "Governance", "date": "12 December 2024",
     "contents": "Covering report (pages 1-4), then Appendix A, the Risk Management Strategy 2024-27 (printed page numbers differ from PDF pages), including impact and likelihood tables, 5x5 matrix, RAG table, risk appetite table, and Appendix 1 policy and Appendix 2 definitions.",
     **S(RS, 1, "Governance Date of Committee: 12 December 2024")},
]

# ---- audit opinions
OPS = []
def op(i, f, pg, period, directorate, service, title, opinion, quote, note=None):
    d = {"id": f"OP-{i:02d}", "report_period": period, "directorate": directorate, "service": service,
         "audit_title": title, "opinion": opinion}
    d.update(S(f, pg, quote))
    if note:
        d["layout_note"] = note
    OPS.append(d)

P1 = "End of March 2025"
nres = "directorate taken from the heading above the row"
op(1, A, 1, P1, "Resources", "Finance, Property and Procurement", "Contract Letting", "Reasonable Assurance",
   "Finance, Property and | Contract Letting | Reasonable Assurance | Procurement", nres + "; service name wraps onto a second line")
op(2, A, 1, P1, "Resources", "Finance, Property and Procurement", "Housing Benefit and Council Tax Hardship Fund", "Reasonable Assurance",
   "Finance, Property and | Housing Benefit and Council Tax | Reasonable Assurance | Procurement | Hardship Fund", nres + "; service and title wrap onto a second line")
op(3, A, 1, P1, "Resources", "Finance, Property and Procurement", "Bank Reconciliation", "Substantial Assurance",
   "Finance, Property and | Bank Reconciliation | Substantial Assurance | Procurement", nres + "; service name wraps onto a second line")
op(4, A, 1, P1, "Resources", "Transformation", "Systems Security (Firewall, Antivirus, Traffic Management)", "Reasonable Assurance",
   "Transformation | Systems Security (Firewall, | Reasonable Assurance | Antivirus, Traffic Management)", nres + "; title wraps onto a second line")
op(5, A, 1, P1, "People", "Public Health", "Joint Agreement Governance", "Advisory - no opinion given",
   "Public Health | Joint Agreement Governance | Advisory - no opinion | given", nres + "; opinion wraps onto a second line")
op(6, A, 1, P1, "Place", "Communities", "Public Protection Partnership – Financial Control Processes", "Substantial Assurance",
   "Communities | Public Protection Partnership – | Substantial Assurance",
   nres + "; the second title line 'Financial Control Processes' is in the plain text of the page but absent from the -layout text")
op(7, A, 1, P1, "Schools", "Primary", "Springfield", "Substantial Assurance",
   "Primary | Springfield | Substantial Assurance", "directorate taken from the heading above the row")
op(8, A, 1, P1, "Schools", "Primary", "St Paul’s", "Reasonable Assurance",
   "St Paul’s | Reasonable Assurance", "directorate and service (Primary) taken from rows above; the service cell is blank on this row")
op(9, A, 1, P1, "Schools", "Primary", "St John and St Nicolas Federation", "Reasonable Assurance",
   "St John and St Nicolas Federation | Reasonable Assurance", "directorate and service (Primary) taken from rows above; the service cell is blank on this row")
P3 = "End of December 2025"
op(10, Q3, 1, P3, "Resources", "Strategy and Governance", "Recruitment (Talent Attraction) and Retention", "Reasonable Assurance",
   "Strategy and Governance | Recruitment (Talent Attraction) and | Reasonable Assurance | Retention", nres + "; title wraps onto a second line")
op(11, Q3, 1, P3, "Resources", "Finance, Property and Procurement", "Accounts Payable", "Reasonable Assurance",
   "Finance, Property and | Accounts Payable | Reasonable Assurance | Procurement", nres + "; service name wraps onto a second line")
op(12, Q3, 1, P3, "People", "Children with Disabilities and SEN Teams", "Personal Budgets (Direct Payments)", "Limited Assurance",
   "Children with Disabilities | Personal Budgets (Direct | Limited Assurance | and SEN Teams | Payments)", nres + "; service and title wrap onto a second line")
op(13, Q3, 1, P3, "People", "Children and Family", "Separated Children (UASC)", "Substantial Assurance",
   "Children and Family | Separated Children (UASC) | Substantial Assurance", nres)
op(14, Q3, 1, P3, "People", "Adult Social Care", "Purchase of Residential and Nursing Care Provision", "Reasonable Assurance",
   "Adult Social Care | Purchase of Residential and | Reasonable Assurance | Nursing Care Provision", nres + "; title wraps onto a second line")
op(15, Q3, 1, P3, "Schools", "Primary", "Winchcombe", "Reasonable Assurance",
   "Primary | Winchcombe | Reasonable Assurance", "directorate taken from the heading above the row")
op(16, Q3, 1, P3, "Schools", "Primary", "Curridge", "Substantial Assurance",
   "Curridge | Substantial Assurance", "directorate and service (Primary) taken from rows above; the service cell is blank on this row")
H["audit_opinions"] = OPS

H["none_reported"] = [
    {"table": "COMPLETED AUDITS, Corporate", "note": "Table row reads None", **S(A, 1, "1) COMPLETED AUDITS | Corporate | None")},
    {"table": "COMPLETED AUDITS, Corporate", "note": "Table row reads None", **S(Q3, 1, "1) COMPLETED AUDITS | Corporate | None")},
    {"table": "COMPLETED FOLLOW UPS", "note": "Table reads None", **S(Q3, 1, "2) COMPLETED FOLLOW UPS | None")},
    {"table": "COMPLETED ADVISORY REVIEWS/OTHER WORK", "note": "Table reads None", **S(Q3, 1, "3) COMPLETED ADVISORY REVIEWS/OTHER WORK | None")},
]

# ---- follow ups
FU = []
FU.append({"id": "FU-01", "kind": "follow_up", "report_period": P1, "directorate": "Resources", "service": "Finance, Property and Procurement",
           "audit_title": "Fixed Asset Register", "report_opinion": "Advisory – no opinion",
           **S(A, 1, "Fixed Asset Register | Advisory – no | opinion"),
           "layout_note": "directorate/service printed as 'Resources/Finance, Property and Procurement'; the report-opinion cell wraps and the implementation cell sits between its two lines, so the implementation opinion is quoted separately",
           "implementation": {"implementation_opinion": "Satisfactory", **S(A, 1, "Fixed Asset Register | Advisory – no | Satisfactory")}})
FU.append({"id": "FU-02", "kind": "follow_up", "report_period": P1, "directorate": "Schools", "service": "Primary",
           "audit_title": "Garland (now Burghfield Common Federation)", "report_opinion": "Weak", "implementation_opinion": "Unsatisfactory",
           **S(A, 2, "Garland (now Burghfield | Weak | Unsatisfactory"),
           "layout_note": "directorate and service taken from the heading lines above the row; title wraps onto a second line"})
FU.append({"id": "FU-03", "kind": "follow_up", "report_period": P1, "directorate": "Schools", "service": "Primary",
           "audit_title": "Westwood Farm", "report_opinion": "Limited Assurance",
           **S(A, 2, "Westwood Farm | Limited | Assurance"),
           "layout_note": "directorate and service taken from the heading lines above the row; the report-opinion cell wraps and the implementation cell sits between its two lines, so the implementation opinion is quoted separately",
           "implementation": {"implementation_opinion": "Satisfactory", **S(A, 2, "Westwood Farm | Limited | Satisfactory")}})
FU.append({"id": "FU-04", "kind": "advisory_review", "report_period": P1, "directorate": "Transformation, Customer and ICT",
           "audit_title": "Transformation SWOT",
           **S(A, 2, "Transformation, Customer | Transformation SWOT | and ICT"),
           "layout_note": "Directorate/Dept/Service cell wraps onto a second line; the table has a Review Title column and no opinion column"})
H["follow_ups"] = FU

H["agreed_actions"] = []

# ---- risk themes
RT = []
def rt(theme, f, pg, quote, context):
    RT.append({"id": f"RT-{len(RT)+1:02d}", "theme": theme, "context": context, **S(f, pg, quote)})

SRC = "Risk Management Strategy 2024-27, section 6.7: 'it can be helpful to use the following sources of risk as prompts to ensure that all areas of risk are considered'"
CTX_SRC = "When identifying risks, it can be helpful to use the following sources of risk as prompts to ensure that all areas of risk are considered:"
cats = [
 (32, "Infrastructure", "Infrastructure Functioning of transport, communications and utilities infrastructure."),
 (32, "Politics & Law", "Politics & Law Effects of change of government policy"),
 (32, "Social Factors", "Social Factors Effects of changes in demographic, residential and social trends on ability to deliver objectives."),
 (32, "Technology", "Technology Capacity to deal with obsolescence and innovation"),
 (32, "Competition & Markets", "Affecting the competitiveness (cost and quality) of the service and/or ability to deliver value for money and general market effectiveness."),
 (32, "Customer & Stakeholder – related", "Satisfaction of: citizens, users, central and regional government and other stakeholders."),
 (32, "Sustainability / Environmental", "Environmental consequences arising from option"),
 (32, "Finance", "Costs, long term financial sustainability/ reliance on finite or vulnerable funding streams. Financial control, fraud and corruption."),
 (32, "People Management / Human resources", "Managing changes to services that may affect staff and/or ways of working."),
 (33, "Contracts & Partnerships", "Dependency on, or failure of, contractors to deliver services or products to the agreed cost and specification. Procurement contract and relationship management."),
 (33, "Tangible Assets", "Security of land and buildings, safety of plant and equipment, control of IT hardware."),
 (33, "Reputation", "Affecting the public standing of the Council, partnerships, or individuals in it"),
 (33, "Professional Judgement & Activities", "Risks inherent in professional work such as assessing clients’ welfare or planning or response to the Human Rights Act."),
]
for pg, name, q in cats:
    rt(name, RS, pg, q, "Listed in the strategy's table of sources of risk. " + CTX_SRC + " (page 31)")
# audit-title themes
rt("Contract Letting (audit title)", A, 1, "Finance, Property and | Contract Letting | Reasonable Assurance | Procurement",
   "Audit title in COMPLETED AUDITS, period End of March 2025")
rt("Accounts Payable (audit title)", Q3, 1, "Finance, Property and | Accounts Payable | Reasonable Assurance | Procurement",
   "Audit title in COMPLETED AUDITS, period End of December 2025")
rt("Purchase of Residential and Nursing Care Provision (audit title)", Q3, 1,
   "Adult Social Care | Purchase of Residential and | Reasonable Assurance | Nursing Care Provision",
   "Audit title in COMPLETED AUDITS, period End of December 2025")
rt("Personal Budgets (Direct Payments) (audit title)", Q3, 1,
   "Children with Disabilities | Personal Budgets (Direct | Limited Assurance | and SEN Teams | Payments)",
   "Audit title in COMPLETED AUDITS, period End of December 2025")
rt("Joint Agreement Governance (audit title)", A, 1, "Public Health | Joint Agreement Governance | Advisory - no opinion | given",
   "Audit title in COMPLETED AUDITS, period End of March 2025")
rt("Public Protection Partnership – Financial Control Processes (audit title)", A, 1,
   "Communities | Public Protection Partnership – | Substantial Assurance",
   "Audit title in COMPLETED AUDITS, period End of March 2025")
rt("Link between planned audits and the Corporate Risk Register", PL, 5,
   "The type of audit, setting out any direct links with the Council Strategy and Corporate Risk Register.",
   "Internal Audit Plan 2025-2028 section 5.7(c): says the plan's Appendix D carries these links; Appendix D is not in the PDF")
H["risk_themes"] = RT

# ---- scoring method
IMP = {}
levels = [
 (5, "Critical", ["> 1% annual WBC budget >£2m", "WBC budget | Death", "Destruction of building, IT infrastructure", "Front page of national press",
                   "Probable legal challenge with penalties. Probable regulatory intervention."],
  ["> 1% annual WBC budget >£2m", "Death", "Destruction of building, IT infrastructure", "Front page of national press",
   "Probable legal challenge with penalties. Probable regulatory intervention."]),
 (4, "Major", ["0.25% - 1% annual WBC budget £500k £2M", "Permanent disability",
               "Majority loss of main building / Loss of main ICT system – e.g. Email / Payroll / network",
               "Adverse publicity nationally HSE / Fire Authority prosecution",
               "High possibility of legal challenge. High possibility of regulatory intervention."],
  ["0.25% - 1% annual WBC budget £500k £2M", "Permanent disability",
   "Majority loss of main building / Loss of main ICT system – e.g. Email / Payroll / network",
   "Adverse publicity nationally HSE / Fire Authority prosecution",
   "High possibility of legal challenge. High possibility of regulatory intervention."]),
 (3, "Medium", ["0.1% - 0.3% annual WBC budget £175k -500k", "Major injury / hospitalisation",
                "Partial loss off main building or total loss of minor building. Temporary loss of major ICT system – up to one week, total loss of minor ICT system",
                "External agency criticism – EG Auditor, Ofsted etc. HSE / Fire Authority enforcement action",
                "Reasonable possibility of successful legal challenge. Reasonable possibility of regulatory interest."],
  None),
 (2, "Minor", ["0.01% 0.1% of annual WBC budget £17.5k £175k", "Major financial loss £1,000+ Illness e.g. stress / minor accident / RIDDOR",
               "Partial loss of minor building. Temporary loss of minor ICT system – up to one week. Loss of Major system – up to one day",
               "Ombudsman complaint upheld",
               "Low possibility of legal challenge. Low possibility regulatory interest"],
  ["0.01% - 0.1% of annual WBC budget £17.5k - £175k", "Major financial loss £1,000+ Illness e.g. stress / minor accident / RIDDOR",
   "Partial loss of minor building. Temporary loss of minor ICT system – up to one week. Loss of Major system – up to one day",
   "Ombudsman complaint upheld", "Low possibility of legal challenge. Low possibility regulatory interest"]),
 (1, "Negligible", ["Less than 0.01% annual WBC budget £17.5k", "Minor Financial loss up to £1,000 / complaint / Grievance",
                    "Loss of minor ICT system - up to one day", "Adverse publicity locally",
                    "Negligible possibility of legal challenge or regulatory interest"], None),
]
crit_names = ["financial_loss_to_council", "personal_staff_or_customers", "assets_physical_information", "reputation", "compliance_litigation_regulatory_contract"]
impact = []
for score, label, quotes, texts in levels:
    texts = texts or quotes
    row = {"score": score, "label": label, "criteria": []}
    for n, q, t in zip(crit_names, quotes, texts):
        c = {"criterion": n, "text": t, **S(RS, 14, q)}
        if q == "WBC budget | Death":
            c["layout_note"] = "cell is only the word Death; quote includes the adjacent financial-cell line 'WBC budget' to reach the minimum quote length"
        if score == 2 and n == "financial_loss_to_council":
            c["layout_note"] = "plain text drops the dashes in this cell; text rebuilt from -layout"
        row["criteria"].append(c)
    impact.append(row)

likelihood = [
 {"score": 5, "label": "Certain", "incidents": "Risk will occur within a 12 month period", "probability": "100%",
  **S(RS, 15, "Risk will occur within a 12 month period | 100% | Certain")},
 {"score": 4, "label": "Almost Certain", "incidents": "Risk is almost certain to occur within a 12 month period", "probability": "70% - 99%",
  **S(RS, 15, "Risk is almost certain to occur within a 12 month | Almost | 70% - 99% | period | Certain")},
 {"score": 3, "label": "Likely", "incidents": "Risk is likely to occur within a 12 month period", "probability": "30% - 69%",
  **S(RS, 15, "Risk is likely to occur within a 12 month period | 30% - 69% | Likely")},
 {"score": 2, "label": "Unlikely", "incidents": "Risk is unlikely to occur within a 12 month period", "probability": "2% - 29%",
  **S(RS, 15, "Risk is unlikely to occur within a 12 month period | 2% - 29% | Unlikely")},
 {"score": 1, "label": "Rare", "incidents": "Risk is very rare and highly unlikely to occur within a 12 month period", "probability": "–<2%",
  **S(RS, 15, "Risk is very rare and highly unlikely to occur | –<2% | Rare | within a 12 month period")},
]

grid = {  # impact -> [band,score] for likelihood 1..5
 5: ["Moderate", "High", "Extreme", "Extreme", "Extreme"],
 4: ["Moderate", "High", "High", "Extreme", "Extreme"],
 3: ["Low", "Moderate", "High", "High", "Extreme"],
 2: ["Low", "Moderate", "Moderate", "High", "High"],
 1: ["Low", "Low", "Low", "Moderate", "Moderate"],
}
printed = {5: [5, 10, 15, 20, 25], 4: [4, 8, 12, 16, 20], 3: [3, 6, 9, 12, 15], 2: [2, 4, 6, 8, 10], 1: [1, 2, 3, 4, 5]}
cells = []
for im in (5, 4, 3, 2, 1):
    for l in range(1, 6):
        cells.append({"likelihood": l, "impact": im, "score": printed[im][l-1], "band": grid[im][l-1]})

bands = [
 {"level": "Extreme (Red)", "score_range": "15 -25", "escalation": "Add to Corporate Risk Register and mitigation action.",
  "response": "Allocate to Executive Director to oversee and Service Director implement agreed actions.",
  **S(RS, 19, "Extreme | Add to Corporate | Allocate to Executive Director to | 15 -25 | Risk Register and | oversee and Service Director")},
 {"level": "Medium - High (Amber)", "score_range": "8-12", "escalation": "Seek assurance that identified controls are effective",
  "response": "Allocate to Service Director to put in place Controls Assurance.",
  **S(RS, 19, "Medium - | Seek assurance | High | that identified | Allocate to Service Director to put in | 8-12"),
  "layout_note": "label printed as 'Medium - High' then '(Amber)' two lines later; the plain text prints 'Medium High' without a dash",
  "extra_quotes": [S(RS, 19, "controls are | place Controls Assurance. | (Amber) | effective")]},
 {"level": "Moderate", "score_range": "4-6", "escalation": "None", "response": "Monitor risk",
  **S(RS, 19, "Moderate 4-6 None Monitor risk")},
 {"level": "Low (Green)", "score_range": "Up to 3", "escalation": "None", "response": "Consider at next annual review",
  **S(RS, 19, "Up to 3 None Consider at next annual review | (Green)"), "layout_note": "level word Low sits on the line above the score cell"},
]

def cell(text, pg, q=None):
    return {"text": text, **S(RS, pg, q or text)}

appetite = {
 "level_names": {"names": ["Averse", "Cautious", "Flexible", "Open", "Seeking"],
                 **S(RS, 16, "Risk levels | Averse | Cautious | Flexible | Open | Seeking")},
 "risk_types": [
  {"type": "Financial/ Asset", "description": "amount of financial loss prepared to put at risk through lost investment and/or financial loss",
   "levels": {"Averse": "Up to £100k", "Cautious": "£100k - £250k", "Flexible": "£250k - £500k", "Open": "£500k - £1m", "Seeking": "£1m +"},
   **S(RS, 16, "Financial/ Asset | Up to £100k | £100k - | £250k - £500k | £500k - £1m | £1m +"),
   "layout_note": "the Cautious cell wraps ('£100k -' / '£250k'); plain text prints it without the dash"},
  {"type": "Compliance", "description": "Exposure to legal challenge. Risk of regulatory interest/ involvement",
   **S(RS, 16, "Compliance Exposure to legal challenge. Risk of regulatory interest/ involvement"),
   "levels": {
     "Averse": cell("Following approved standards and practices, engaging in business as usual, low value transactions", 16),
     "Cautious": cell("Following approved standards and practices, engaging in business as usual, increased value transactions", 16),
     "Flexible": cell("Following approved standards and practices as far as possible, innovating, public interest, high value transactions", 16),
     "Open": cell("Innovating, new area of work, significant public interest, high value transaction", 16),
     "Seeking": cell("Innovating in unprecedented environment", 16)}},
  {"type": "Reputation", "description": "Exposure to reputational damage or enhancement",
   **S(RS, 16, "Reputation Exposure to reputational damage or enhancement"),
   "levels": {
     "Averse": cell("No chance of any repercussions / negative comments", 16),
     "Cautious": cell("Little chance of significant repercussions and mitigation in place beforehand", 16),
     "Flexible": cell("Exposure of greater scrutiny and public interest. Management through listening and active engagement.", 16),
     "Open": cell("Experimental– possible significant reputational damage or enhancement", 16, "Experimental– possible significant reputational damage or enhancement"),
     "Seeking": cell("Unprecedented – probable significant reputational damage or enhancement", 16)},
   "layout_note": "the Flexible cell continues 'Risk of reputational damage.' at the top of the next page (PDF page 17)",
   "continuation": S(RS, 17, "reputational damage.")},
  {"type": "Operational", "description": "Related to the delivery of Council Strategy",
   **S(RS, 17, "Operational Related to the delivery of Council Strategy"),
   "levels": {
     "Averse": cell("Essential development of core business only", 17),
     "Cautious": cell("Maintain status quo; new schemes are tried and tested only by others", 17),
     "Flexible": cell("Encourage innovation through new schemes offered to the Council", 17),
     "Open": cell("Proactive pursuit of innovation and crafting solutions that have not been attempted before", 17),
     "Seeking": cell("Desire to ‘break the mould’ and challenge current working practices", 17)}},
 ],
 "table_caption": S(RS, 17, "Table 3. West Berkshire Council Risk Appetite"),
 "council_chosen_level": [
  {"risk_type": "Financial", "level": "Flexible", **S(RS, 17, "Financial Risk Appetite – Flexible"),
   "statement": S(RS, 17, "The Council aims to operate with a financial risk between £250k – £500k.")},
  {"risk_type": "Compliance", "level": "Flexible/Open", **S(RS, 17, "Compliance Risk Appetite – Flexible/Open")},
  {"risk_type": "Reputation", "level": "Open", **S(RS, 17, "Reputation Risk appetite – Open")},
  {"risk_type": "Operational", "level": "Open", **S(RS, 18, "Operational risk appetite – Open")},
 ],
 "scope_statement": S(RS, 16, "The Council’s Risk Appetite 2024/25 – 2027/28"),
 "colour_only_content": "see gaps",
}

H["scoring_method"] = {
 "usable": True, "unusable_reason": None,
 "section": "Risk Management Strategy 2024-27 sections 4.1-4.4 (evaluation, Tables 1-2), 5.8-5.13 (appetite, Figure 1, Table 4)",
 "scales": {
   "impact": {"section": "4.3, Table 1. Impact Ratings", "levels": impact,
              "table_caption": S(RS, 14, "Table 1. Impact Ratings")},
   "likelihood": {"section": "4.4, Table 2. Likelihood Ratings", "levels": likelihood,
                  "table_caption": S(RS, 15, "Table 2. Likelihood Ratings")}},
 "matrix": {"section": "5.11, Figure 1", "cells": cells,
            "orientation": "likelihood 1-5 left to right (Rare to Certain); impact 5 (Critical) at top to 1 (Negligible) at bottom; each cell prints its score and a band word",
            **S(RS, 18, "5x5 Risk Matrix Assessments")},
 "bands": {"section": "5.13, Table 4", "rows": bands,
           "table_caption": S(RS, 19, "Table 4. RAG Levels, Risk Scores, Escalation and Responses")},
 "appetite": appetite,
 "evaluation_levels": {"section": "4.1 (and Appendix 2 definitions)", "levels": [
   {"name": "Gross level", "definition": "likelihood and impact without additional, specific mitigation action", **S(RS, 13, "Gross level – likelihood and impact without additional, specific mitigation action.")},
   {"name": "Actual level", "definition": "this is the current likelihood and impact, based on mitigation action already put in place but excluding further mitigation action planned",
    **S(RS, 13, "Actual level - this is the current likelihood and impact, based on mitigation action already put in place but excluding further mitigation action planned.")},
   {"name": "Expected level", "definition": "this is a future level of likelihood and impact based on any additional mitigation action (if any) planned",
    **S(RS, 14, "Expected level – this is a future level of likelihood and impact based on any additional mitigation action (if any) planned")}]},
}

H["strategic_risk_register"] = {
 "present": False,
 "note": "No risk register is in data/committee/. The strategy names it the Corporate Risk Register and states how risk is reported to the Governance Committee.",
 "evidence": [
   S(RS, 28, "risk is reported as a Part II (confidential information) report to the Governance Committee."),
   S(RS, 24, "Corporate Risk Register – this register records the most significant risks for the Council or those risks which may prevent the Council from achieving its strategic objectives as set out in the Council Strategy."),
 ]}

# ---- discrepancies
D = []
def dis(kind, desc, *ev):
    D.append({"id": f"DISC-{len(D)+1:02d}", "kind": kind, "description": desc, "evidence": list(ev)})

dis("label_text_vs_table", "The running text gives the Medium impact rating as (2); Table 1 gives Medium the rating 3. The same sentence also gives Minor as (2).",
    S(RS, 14, "Negligible (1), Minor (2), Medium (2), Major (4), or Critical impact(5):"),
    S(RS, 14, "3 Medium 0.1% - 0.3% annual WBC budget £175k -500k"))
dis("band_label", "Table 4 labels the 8-12 band 'Medium - High (Amber)'; the cells of Figure 1 with scores in that range print 'High'. Figure 1 also uses the word 'Medium' only as the impact label for 3.",
    S(RS, 19, "Medium - | Seek assurance | High | that identified | Allocate to Service Director to put in | 8-12"),
    S(RS, 18, "Moderate | High | High | Extreme | Extreme"))
dis("score_threshold", "Table 4 requires 'Add to Corporate Risk Register' for scores 15 -25; Figure 4 (Risk Escalation) lists the Corporate Risk Register as including risks that 'Score 9 or above'.",
    S(RS, 19, "Extreme | Add to Corporate | Allocate to Executive Director to | 15 -25 | Risk Register and | oversee and Service Director"),
    S(RS, 21, "Score 9 or above"))
dis("overlapping_bounds", "Table 1 financial-loss percentages overlap: Medium is 0.1% - 0.3% and Major is 0.25% - 1% of annual WBC budget.",
    S(RS, 14, "3 Medium 0.1% - 0.3% annual WBC budget £175k -500k"),
    S(RS, 14, "4 Major 0.25% - 1% annual WBC budget £500k £2M"))
dis("label", "Section 4.1 names the middle evaluation level 'Actual level'; Appendix 2 names it 'Current risk rating'; Table 4 heads its score column 'Current'. Appendix 2 names the third level 'Expected Net risk rating' where section 4.1 says 'Expected level'.",
    S(RS, 13, "Actual level - this is the current likelihood and impact"),
    S(RS, 34, "Current risk rating - this is the likelihood and impact at the time of assessment"),
    S(RS, 34, "Expected Net risk rating - this is a future level of likelihood and impact based on"))
dis("label", "Committee name differs: Figure 4 gives the six-monthly review of the Corporate Risk Register to 'Governance and Ethics Committee'; elsewhere in the strategy the body is 'the Governance Committee'.",
    S(RS, 21, "Governance and Ethics Committee"),
    S(RS, 24, "Operations Boards and the Governance Committee."))
dis("section_reference", "Appendix 1 section 5.1 refers to risk evaluation as 'Section 7', appetite as 'Section 8 and Section 9' and recording and reporting as 'Section 10'; the contents list puts evaluation in section 4, appetite in section 5, and recording in section 6.",
    S(RS, 30, "Risk analysis and Risk evaluation (see Section 7)"),
    S(RS, 6, "4. How do we evaluate risks?"),
    S(RS, 6, "6. Risk Recording and Reporting"))
dis("section_reference", "Appendix 1 section 2.3 says definitions are 'listed as part of Appendix 1'; the definitions of key terminology are headed 'Appendix 2'.",
    S(RS, 26, "The definitions for the other key risk management terminology used in this document are listed as part of Appendix 1."),
    S(RS, 34, "Appendix 2 - Definitions of key terminology that is part of West"))
dis("two_statements_same_fact", "Section 4.7 says the level of resource is 'sufficient to meet' the planned programme; section 5.8 says it is 'approximately in line with the number of days' in the planned programme.",
    S(PL, 3, "The plan over the three-year period shows the level of resource is sufficient to meet the planned programme of work."),
    S(PL, 5, "The plan over the three-year period shows the level of resource is approximately in line with the number of days in the planned programme of work."))
dis("section_reference", "Section 4.3 refers to sections 5.3b), 5.3d), 5.3g), 5.5 and 5.6c) as the highlighted key changes; section 5.3 in the report lists only (a) to (c) (Purpose of Internal Auditing, Code of Ethics, Performance standards), and section 5.4 repeats the references as '5.3b)', '5.3d)', '5.3g)'.",
    S(PL, 3, "Key changes are set out in the highlighted sections 5.3b), 5.3d), 5.3g), 5.5 and 5.6c)."),
    S(PL, 4, "Purpose of Internal Auditing. Code of Ethics. Performance standards required to be followed for the professional practice of internal auditing."),
    S(PL, 4, "5.3d) - sets out the requirement for significant changes to the audit plan to be reported/approved by the Governance Committee."))
dis("label", "The opinion label for an advisory item is printed 'Advisory - no opinion given' (hyphen) in the COMPLETED AUDITS table and 'Advisory – no opinion' (en dash, without 'given') in the COMPLETED FOLLOW UPS table of the same paper.",
    S(A, 1, "Public Health | Joint Agreement Governance | Advisory - no opinion | given"),
    S(A, 1, "Fixed Asset Register | Advisory – no | opinion"))
dis("label", "The 'Overall Opinion - Report' column of the follow-up table prints 'Weak' for one school and 'Limited Assurance' for another; the COMPLETED AUDITS tables use the labels Substantial Assurance, Reasonable Assurance and Limited Assurance.",
    S(A, 2, "Garland (now Burghfield | Weak | Unsatisfactory"),
    S(A, 2, "Westwood Farm | Limited | Assurance"))
dis("label_text_vs_table", "Section 5.10 describes the Open reputation appetite as 'little chance of significant repercussions'; in Table 3 that wording sits in the Cautious column, and the Open column reads 'Experimental– possible significant reputational damage or enhancement'.",
    S(RS, 17, "even the transformational activities are delivered with sound governance arrangements in place"),
    S(RS, 17, "ensure there is little chance of significant repercussions"),
    S(RS, 16, "Reputation | No chance of | Little chance | Experimental–"))
H["discrepancies"] = D

# ---- gaps
G = []
def gap(what, looked_in, reason, *ev):
    d = {"id": f"GAP-{len(G)+1:02d}", "what": what, "looked_in": looked_in, "reason": reason}
    if ev:
        d["evidence"] = list(ev)
    G.append(d)

gap("Agreed audit actions with theme, due date, status or overdue flag",
    "all four PDFs (searched for recommendation, agreed, overdue, due, implementation, action)",
    "No paper contains an actions table or list. The follow-up tables give only an implementation-progress opinion per audit. The plan report mentions monitoring reports on implementation of agreed recommendations but does not include them.",
    S(PL, 5, "Monitoring reports on progress with implementation of agreed audit recommendations."))
gap("Internal Audit Plan 2025-28 appendices (Appendix D: audit areas, level of risk assessed by Internal Audit, planned days, date last reviewed); also Appendices A, B, C, E, F",
    "internal-audit-plan-2025-28.pdf (7 pages, pages 1-7 read)",
    "The PDF is the covering report only; the appendices are listed but not included, so no audit risk levels or day counts are available.",
    S(PL, 6, "Appendix D - Internal Audit Plan 2025 to 2028;"),
    S(PL, 5, "The level of risk associated with the audit area/function, as assessed by Internal Audit."))
gap("Strategic (Corporate) Risk Register", "data/committee/ (four files)",
    "Not among the papers; the strategy says risk is reported to the Governance Committee as a Part II (confidential information) report.",
    S(RS, 28, "risk is reported as a Part II (confidential information) report to the Governance Committee."))
gap("Opinion table cells that could not be read", "both Appendix A files",
    "None found unreadable. One title line ('Financial Control Processes', 2024-25 annual file page 1) is present in the plain text but missing from the -layout text; recorded in the layout_note of OP-06.")
gap("Colour-only or shading-only content", "risk-management-strategy-2024-27.pdf pages 16-19",
    "Table 3 says shaded areas identify the Council's risk appetite levels, but which cells are shaded is not text and is not recorded; the stated levels per risk type come from section 5.10 text. The colours of the Figure 1 cells and Table 4 rows are likewise not text; band words (Low, Moderate, High, Extreme) and RAG names (Red, Amber, Green) are as printed.",
    S(RS, 16, "with shaded areas identifying the Council’s risk appetite levels:"))
gap("Number or detail of recommendations behind each audit opinion; audit dates; findings narrative", "both Appendix A files",
    "Appendix A tables give only directorate/service, audit title and opinion (and for follow-ups an implementation opinion). The note under the table says the opinion is derived from the number/significance of recommendations, but the numbers are not given.",
    S(A, 1, "The overall opinion is derived from the number/significance of recommendations together with using professional judgement."))
gap("Mapping from matrix scores to the risk appetite 'line'", "risk-management-strategy-2024-27.pdf sections 5.7-5.13",
    "Section 5.7 refers to risks falling above the appetite 'line'; no paragraph found that states which scores fall above or below the chosen appetite levels.",
    S(RS, 16, "Risks that fall above the risk appetite ‘line’ may still happen and should still be managed effectively and transparently."))
gap("Procurement-specific narrative in the audit papers", "all four PDFs (searched procure, contract, partnership)",
    "Procurement-relevant wording appears only in two audit titles (Contract Letting; Accounts Payable) and in the strategy's category 'Contracts & Partnerships'; no paper describes procurement findings.")
H["gaps"] = G

with open("outputs/history.json", "w", encoding="utf-8") as fh:
    json.dump(H, fh, ensure_ascii=False, indent=2)
print("written")
