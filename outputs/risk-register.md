# Risk register: West Berkshire Council procurement audit planning

**Status:** DRAFT v0, awaiting auditor decisions · generated 2026-10-16 08:47 UTC · indicators to investigate, not findings of wrongdoing

**Scoring method:** the council's own, from the Risk Management Strategy 2024-27 (Risk Management Strategy 2024-27 sections 4.1-4.4 (evaluation, Tables 1-2), 5.8-5.13 (appetite, Figure 1, Table 4)): likelihood 1-5 × impact 1-5 = score; band from the Figure 1 matrix.

**Likelihood rubric (binding):** base = 1 + number of distinct indicator tests cited with a non-zero count (capped at 4, because indicators never show a risk is certain); +1 for a repeat finding that cites an adverse audit opinion (cap 5). Deviations carry a stated reason or an auditor override.

## Conflicts in the scoring method (one reading used, the other marked)

- **DISC-01 (history):** The running text gives the Medium impact rating as (2); Table 1 gives Medium the rating 3. The same sentence also gives Minor as (2).  
  USED: Table 1 numbering (Negligible 1, Minor 2, Medium 3, Major 4, Critical 5).  
  MARKED, not used: the running-text label 'Medium (2)'.
- **DISC-02 (history):** Table 4 labels the 8-12 band 'Medium - High (Amber)'; the cells of Figure 1 with scores in that range print 'High'. Figure 1 also uses the word 'Medium' only as the impact label for 3.  
  USED: the Figure 1 matrix label for each cell's band (High, Extreme, Moderate, Low).  
  MARKED, not used: Table 4's label 'Medium - High (Amber)' for scores 8-12; shown beside the band.
- **DISC-03 (history):** Table 4 requires 'Add to Corporate Risk Register' for scores 15 -25; Figure 4 (Risk Escalation) lists the Corporate Risk Register as including risks that 'Score 9 or above'.  
  USED: Table 4, add to Corporate Risk Register at scores 15-25.  
  MARKED, not used: Figure 4, scores 9 or above; risks scoring 9-14 are flagged in the register.
- **DISC-04 (history):** Table 1 financial-loss percentages overlap: Medium is 0.1% - 0.3% and Major is 0.25% - 1% of annual WBC budget.  
  USED: where an estimated financial loss falls in the overlap, rate the higher impact (Major, 4).  
  MARKED, not used: the Medium (3) reading of the overlap.

## Summary

| Risk | Title | Likelihood | Impact | Score | Band |
|---|---|---|---|---|---|
| R-02 | Split purchases and threshold-hugging payments | 3 | 3 | 9 | High |
| R-03 | Spend after notice expiry or beyond the awarded value | 3 | 3 | 9 | High |
| R-01 | Spend above the quote tier with no matching contract notice | 2 | 4 | 8 | High |
| R-05 | Care and education placement commissioning controls | 2 | 4 | 8 | High |
| R-04 | Possible duplicate payments to the same supplier | 2 | 2 | 4 | Moderate |

## Risks

### R-01: Spend above the quote tier with no matching contract notice

**Score 8, High** (likelihood 2 Unlikely × impact 4 Major; matrix cell L2×I4)
  
_Table 4 names this band 'Medium - High (Amber)'; the matrix label is used (see conflicts)._

- **Risk (indicator):** Indicator that general procurement spend above the quote tier may have been placed without a competitive process or a published notice. Notices are only published above the Contracts Finder level and a call-off may sit under a notice in another name, so this is a population to investigate, not a finding.
- **Likelihood: 2 (Unlikely).** One indicator test fired for general procurement: 150 suppliers show an annualised estimate above the tender tier with no exact notice match [metric:$.tests.off_contract.by_tag.general_procurement.count].
  - _rubric: 1 indicator test(s) with a non-zero count (off_contract) → base 2_
- **Impact: 4 (Major).** Table 1 compliance, litigation and regulatory criterion (Major): the quote and notice requirements [rule:CPR-59] [rule:CPR-60] could be unmet on spend with an annualised estimate of £22,265,397 [metric:$.tests.off_contract.by_tag.general_procurement.gbp].
- **Evidence:**
  - General procurement off-contract indicator: 150 suppliers, annualised estimate £22,265,397 [metric:$.tests.off_contract.by_tag.general_procurement.gbp]
  - Population to request contract and quote evidence for: 183 general procurement suppliers above the quote tier [metric:$.tests.high_value_suppliers.by_tag.general_procurement.count]
  - Contract Letting audit gave Reasonable Assurance, context only [history:OP-01]
- **Proposed focus:** Request contract, quote and exception evidence for the largest general procurement suppliers with no matching notice; test against the quote rule and Appendix C exceptions.

### R-02: Split purchases and threshold-hugging payments

**Score 9, High** (likelihood 3 Likely × impact 3 Medium; matrix cell L3×I3)
  
_Table 4 names this band 'Medium - High (Amber)'; the matrix label is used (see conflicts)._
  
_Figure 4 would add this to the Corporate Risk Register (score 9 or above); Table 4 does not (needs 15). Table 4 applied; auditor to confirm._

- **Risk (indicator):** Indicator that general procurement purchases may have been split or kept just below a procedure threshold, which the aggregation rules prohibit. Recurring payments also produce these patterns, so each is to be investigated.
- **Likelihood: 3 (Likely).** Two indicator tests fired for general procurement: 47 payments just below a threshold [metric:$.tests.threshold_clustering.by_tag.general_procurement.count] and 132 split-purchase candidates [metric:$.tests.split_purchases.by_tag.general_procurement.count].
  - _rubric: 2 indicator test(s) with a non-zero count (split_purchases, threshold_clustering) → base 3_
- **Impact: 3 (Medium).** Table 1 compliance criterion (Medium): avoidance of the aggregation requirement [rule:CPR-15] and the repeat-purchase valuation rule [rule:CPR-16], with split-purchase combined value of £14,144,144 [metric:$.tests.split_purchases.by_tag.general_procurement.gbp].
- **Evidence:**
  - Threshold clustering, general procurement: 47 payments worth £376,899 [metric:$.tests.threshold_clustering.by_tag.general_procurement.gbp]
  - Split purchases, general procurement: 132 candidates [metric:$.tests.split_purchases.by_tag.general_procurement.count]
  - The lowest tier is noisy and dominated by recurring payments [metric:$.caveats]
- **Proposed focus:** Review flagged general procurement supplier sets for a single underlying need and check how the total value was estimated.

### R-03: Spend after notice expiry or beyond the awarded value

**Score 9, High** (likelihood 3 Likely × impact 3 Medium; matrix cell L3×I3)
  
_Table 4 names this band 'Medium - High (Amber)'; the matrix label is used (see conflicts)._
  
_Figure 4 would add this to the Corporate Risk Register (score 9 or above); Table 4 does not (needs 15). Table 4 applied; auditor to confirm._

- **Risk (indicator):** Indicator that spend may continue after a published contract ended, or exceed the award, without a recorded extension or variation. A newer contract may exist with no notice, and award values may be estimates.
- **Likelihood: 3 (Likely).** Two indicator tests fired for general procurement: 5 suppliers paid after every matching notice ended [metric:$.tests.expired_notice_spend.by_tag.general_procurement.count] and 6 with an annualised estimate well above the award [metric:$.tests.spend_vs_award.by_tag.general_procurement.count].
  - _rubric: 2 indicator test(s) with a non-zero count (expired_notice_spend, spend_vs_award) → base 3_
- **Impact: 3 (Medium).** Table 1 compliance criterion (Medium): extensions and variations need a recorded basis [rule:CPR-70] [rule:CPR-71]; award-excess annualised estimate £626,009 [metric:$.tests.spend_vs_award.by_tag.general_procurement.gbp].
- **Evidence:**
  - Expired-notice spend, general procurement: 5 suppliers, £121,645 [metric:$.tests.expired_notice_spend.by_tag.general_procurement.gbp]
  - Spend versus award, general procurement: 6 suppliers [metric:$.tests.spend_vs_award.by_tag.general_procurement.count]
  - Secondary, premises: 2 expired-notice suppliers [metric:$.tests.expired_notice_spend.by_tag.premises.count]
- **Proposed focus:** Obtain extension and variation approvals, or replacement contracts, for the flagged suppliers.

### R-04: Possible duplicate payments to the same supplier

**Score 4, Moderate** (likelihood 2 Unlikely × impact 2 Minor; matrix cell L2×I2)

- **Risk (indicator):** Indicator that general procurement payments of the same amount to the same supplier within seven days may include duplicates; some may be legitimate repeat charges.
- **Likelihood: 2 (Unlikely).** One indicator test fired for general procurement: 49 same-supplier, same-amount pairs [metric:$.tests.duplicates.by_tag.general_procurement.count].
  - _rubric: 1 indicator test(s) with a non-zero count (duplicates) → base 2_
- **Impact: 2 (Minor).** Table 1 financial criterion (Minor): the general procurement duplicate value is £329,802, likely recoverable [metric:$.tests.duplicates.by_tag.general_procurement.gbp]; payment records are required [rule:CPR-37].
- **Evidence:**
  - Duplicates, general procurement: 49 pairs worth £329,802 [metric:$.tests.duplicates.by_tag.general_procurement.gbp]
  - Accounts Payable audit gave Reasonable Assurance, context only [history:OP-11]
- **Proposed focus:** Test flagged pairs against invoices and the payment system duplicate controls.

### R-05: Care and education placement commissioning controls

**Score 8, High** (likelihood 2 Unlikely × impact 4 Major; matrix cell L2×I4)
  
_Table 4 names this band 'Medium - High (Amber)'; the matrix label is used (see conflicts)._

- **Risk (indicator):** Care and education placements, shown separately from general procurement. Indicator that placement spend above the quote tier may lack a matching notice; Appendix C row F may exempt many placements, so evidence of the basis is to be requested.
- **Likelihood: 2 (Unlikely).** Care and education placements only: one non-recurrence indicator fired, 311 suppliers with no exact notice match [metric:$.tests.off_contract.by_tag.care_education_placement.count]. Repeat payment is the normal pattern here, so duplicates and clustering are not counted.
  - _rubric: 1 indicator test(s) with a non-zero count (off_contract) → base 2_
- **Impact: 4 (Major).** Table 1 compliance and financial criteria (Major): placements carry an annualised estimate of £31,447,862 [metric:$.tests.off_contract.by_tag.care_education_placement.gbp]; the social care exemption needs a recorded basis [rule:CPR-73].
- **Evidence:**
  - Care and education placements, off-contract indicator: 311 suppliers, annualised estimate £31,447,862 [metric:$.tests.off_contract.by_tag.care_education_placement.gbp]
  - Residential and nursing care purchase audit gave Reasonable Assurance, context only [history:OP-14]
  - Placement providers above the quote tier: 315 [metric:$.tests.high_value_suppliers.by_tag.care_education_placement.count]
- **Proposed focus:** Request the commissioning basis (Appendix C row F, framework or notice) for the largest placement providers.

## Auditor decisions

Record one decision per risk in `outputs/auditor-comments.md` (Approve, Reject or Amend, with a comment). Approve puts the risk in audit scope. To dictate a score when amending, write `L=n` and/or `I=n` in the comment; the next revision applies it and marks it as an auditor override. The risk-assessor is then re-run to produce a revision; nothing else may change.

| Risk | Rating | Decision |
|---|---|---|
| R-01 | 8 High | _awaiting_ |
| R-02 | 9 High | _awaiting_ |
| R-03 | 9 High | _awaiting_ |
| R-04 | 4 Moderate | _awaiting_ |
| R-05 | 8 High | _awaiting_ |

<!-- risk-register-state
{"applied": {}, "generated": "2026-10-16 08:47 UTC", "last_revision": null, "rejected": {}, "risks": {"R-01": {"description": "Indicator that general procurement spend above the quote tier may have been placed without a competitive process or a published notice. Notices are only published above the Contracts Finder level and a call-off may sit under a notice in another name, so this is a population to investigate, not a finding.", "evidence": ["General procurement off-contract indicator: {{$.tests.off_contract.by_tag.general_procurement.count|int}} suppliers, annualised estimate {{$.tests.off_contract.by_tag.general_procurement.gbp|gbp}} [metric:$.tests.off_contract.by_tag.general_procurement.gbp]", "Population to request contract and quote evidence for: {{$.tests.high_value_suppliers.by_tag.general_procurement.count|int}} general procurement suppliers above the quote tier [metric:$.tests.high_value_suppliers.by_tag.general_procurement.count]", "Contract Letting audit gave Reasonable Assurance, context only [history:OP-01]"], "impact": {"justification": "Table 1 compliance, litigation and regulatory criterion (Major): the quote and notice requirements [rule:CPR-59] [rule:CPR-60] could be unmet on spend with an annualised estimate of {{$.tests.off_contract.by_tag.general_procurement.gbp|gbp}} [metric:$.tests.off_contract.by_tag.general_procurement.gbp].", "score": 4}, "likelihood": {"justification": "One indicator test fired for general procurement: {{$.tests.off_contract.by_tag.general_procurement.count|int}} suppliers show an annualised estimate above the tender tier with no exact notice match [metric:$.tests.off_contract.by_tag.general_procurement.count].", "score": 2}, "proposed_focus": "Request contract, quote and exception evidence for the largest general procurement suppliers with no matching notice; test against the quote rule and Appendix C exceptions.", "repeat_finding": null, "title": "Spend above the quote tier with no matching contract notice"}, "R-02": {"description": "Indicator that general procurement purchases may have been split or kept just below a procedure threshold, which the aggregation rules prohibit. Recurring payments also produce these patterns, so each is to be investigated.", "evidence": ["Threshold clustering, general procurement: {{$.tests.threshold_clustering.by_tag.general_procurement.count|int}} payments worth {{$.tests.threshold_clustering.by_tag.general_procurement.gbp|gbp}} [metric:$.tests.threshold_clustering.by_tag.general_procurement.gbp]", "Split purchases, general procurement: {{$.tests.split_purchases.by_tag.general_procurement.count|int}} candidates [metric:$.tests.split_purchases.by_tag.general_procurement.count]", "The lowest tier is noisy and dominated by recurring payments [metric:$.caveats]"], "impact": {"justification": "Table 1 compliance criterion (Medium): avoidance of the aggregation requirement [rule:CPR-15] and the repeat-purchase valuation rule [rule:CPR-16], with split-purchase combined value of {{$.tests.split_purchases.by_tag.general_procurement.gbp|gbp}} [metric:$.tests.split_purchases.by_tag.general_procurement.gbp].", "score": 3}, "likelihood": {"justification": "Two indicator tests fired for general procurement: {{$.tests.threshold_clustering.by_tag.general_procurement.count|int}} payments just below a threshold [metric:$.tests.threshold_clustering.by_tag.general_procurement.count] and {{$.tests.split_purchases.by_tag.general_procurement.count|int}} split-purchase candidates [metric:$.tests.split_purchases.by_tag.general_procurement.count].", "score": 3}, "proposed_focus": "Review flagged general procurement supplier sets for a single underlying need and check how the total value was estimated.", "repeat_finding": null, "title": "Split purchases and threshold-hugging payments"}, "R-03": {"description": "Indicator that spend may continue after a published contract ended, or exceed the award, without a recorded extension or variation. A newer contract may exist with no notice, and award values may be estimates.", "evidence": ["Expired-notice spend, general procurement: {{$.tests.expired_notice_spend.by_tag.general_procurement.count|int}} suppliers, {{$.tests.expired_notice_spend.by_tag.general_procurement.gbp|gbp}} [metric:$.tests.expired_notice_spend.by_tag.general_procurement.gbp]", "Spend versus award, general procurement: {{$.tests.spend_vs_award.by_tag.general_procurement.count|int}} suppliers [metric:$.tests.spend_vs_award.by_tag.general_procurement.count]", "Secondary, premises: {{$.tests.expired_notice_spend.by_tag.premises.count|int}} expired-notice suppliers [metric:$.tests.expired_notice_spend.by_tag.premises.count]"], "impact": {"justification": "Table 1 compliance criterion (Medium): extensions and variations need a recorded basis [rule:CPR-70] [rule:CPR-71]; award-excess annualised estimate {{$.tests.spend_vs_award.by_tag.general_procurement.gbp|gbp}} [metric:$.tests.spend_vs_award.by_tag.general_procurement.gbp].", "score": 3}, "likelihood": {"justification": "Two indicator tests fired for general procurement: {{$.tests.expired_notice_spend.by_tag.general_procurement.count|int}} suppliers paid after every matching notice ended [metric:$.tests.expired_notice_spend.by_tag.general_procurement.count] and {{$.tests.spend_vs_award.by_tag.general_procurement.count|int}} with an annualised estimate well above the award [metric:$.tests.spend_vs_award.by_tag.general_procurement.count].", "score": 3}, "proposed_focus": "Obtain extension and variation approvals, or replacement contracts, for the flagged suppliers.", "repeat_finding": null, "title": "Spend after notice expiry or beyond the awarded value"}, "R-04": {"description": "Indicator that general procurement payments of the same amount to the same supplier within seven days may include duplicates; some may be legitimate repeat charges.", "evidence": ["Duplicates, general procurement: {{$.tests.duplicates.by_tag.general_procurement.count|int}} pairs worth {{$.tests.duplicates.by_tag.general_procurement.gbp|gbp}} [metric:$.tests.duplicates.by_tag.general_procurement.gbp]", "Accounts Payable audit gave Reasonable Assurance, context only [history:OP-11]"], "impact": {"justification": "Table 1 financial criterion (Minor): the general procurement duplicate value is {{$.tests.duplicates.by_tag.general_procurement.gbp|gbp}}, likely recoverable [metric:$.tests.duplicates.by_tag.general_procurement.gbp]; payment records are required [rule:CPR-37].", "score": 2}, "likelihood": {"justification": "One indicator test fired for general procurement: {{$.tests.duplicates.by_tag.general_procurement.count|int}} same-supplier, same-amount pairs [metric:$.tests.duplicates.by_tag.general_procurement.count].", "score": 2}, "proposed_focus": "Test flagged pairs against invoices and the payment system duplicate controls.", "repeat_finding": null, "title": "Possible duplicate payments to the same supplier"}, "R-05": {"description": "Care and education placements, shown separately from general procurement. Indicator that placement spend above the quote tier may lack a matching notice; Appendix C row F may exempt many placements, so evidence of the basis is to be requested.", "evidence": ["Care and education placements, off-contract indicator: {{$.tests.off_contract.by_tag.care_education_placement.count|int}} suppliers, annualised estimate {{$.tests.off_contract.by_tag.care_education_placement.gbp|gbp}} [metric:$.tests.off_contract.by_tag.care_education_placement.gbp]", "Residential and nursing care purchase audit gave Reasonable Assurance, context only [history:OP-14]", "Placement providers above the quote tier: {{$.tests.high_value_suppliers.by_tag.care_education_placement.count|int}} [metric:$.tests.high_value_suppliers.by_tag.care_education_placement.count]"], "impact": {"justification": "Table 1 compliance and financial criteria (Major): placements carry an annualised estimate of {{$.tests.off_contract.by_tag.care_education_placement.gbp|gbp}} [metric:$.tests.off_contract.by_tag.care_education_placement.gbp]; the social care exemption needs a recorded basis [rule:CPR-73].", "score": 4}, "likelihood": {"justification": "Care and education placements only: one non-recurrence indicator fired, {{$.tests.off_contract.by_tag.care_education_placement.count|int}} suppliers with no exact notice match [metric:$.tests.off_contract.by_tag.care_education_placement.count]. Repeat payment is the normal pattern here, so duplicates and clustering are not counted.", "score": 2}, "proposed_focus": "Request the commissioning basis (Appendix C row F, framework or notice) for the largest placement providers.", "repeat_finding": null, "title": "Care and education placement commissioning controls"}}, "round": 0}
-->
