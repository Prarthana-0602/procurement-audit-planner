# Planning memo: West Berkshire Council procurement audit

**Status:** DRAFT pack v3, awaiting QA and auditor sign-off · built 2026-10-16 09:22 UTC · from risk register revision 1 · indicators to investigate, not findings of wrongdoing

## 1. Scope: approved risks

| Risk | Title | Likelihood | Impact | Score | Band | Auditor decision | Auditor comment |
|---|---|---|---|---|---|---|---|
| R-01 | Spend above the quote tier with no matching contract notice | 2 | 4 | 8 | High | Approve | Reviewer: Prarthana Patel, 2026-10-16. |
| R-02 | Split purchases and threshold-hugging payments | 3 | 3 | 9 | High | Approve | Reviewer: Prarthana Patel, 2026-10-16. |
| R-03 | Spend after notice expiry or beyond the awarded value | 3 | 3 | 9 | High | Approve | Reviewer: Prarthana Patel, 2026-10-16. |
| R-05 | Care and education placement commissioning controls | 3 | 4 | 12 | High | Amend | Reviewer: Prarthana Patel, 2026-10-16. L=3. OP-12 (Personal Budgets, Limited Assurance) is in the same adult social care commissioning area, so a recent adverse opinion makes recurrence more likely. |

4 risk(s) are in scope, each recommended by the risk-assessor and decided by the auditor. Scores are the register's; an Amend carries the auditor's override.

**Rejected by the auditor, not planned** (recorded in auditor-comments.md):

- R-04 Possible duplicate payments to the same supplier: Reviewer: Prarthana Patel, 2026-10-16. Duplicate payments are an accounts-payable control matter and the flagged groups are dominated by recurring care payments; cover in a separate AP review.

**Why each risk is in the plan**

- **R-01**: Approved. 150 general procurement suppliers sit above the quote tier with no exact notice match [metric:$.tests.off_contract.by_tag.general_procurement.count], so quote, notice and exception evidence is to be requested [rule:CPR-59].
- **R-02**: Approved. 47 general procurement payments sit just below a threshold [metric:$.tests.threshold_clustering.by_tag.general_procurement.count] and the anti-splitting rule applies [rule:CPR-15].
- **R-03**: Approved. 5 general procurement suppliers were paid after every matching notice ended [metric:$.tests.expired_notice_spend.by_tag.general_procurement.count]; extensions and variations need approval [rule:CPR-70] [rule:CPR-71].
- **R-05**: Approved with the auditor's likelihood amendment. Care and education placements are tested on their own: 311 placement suppliers show no exact notice match [metric:$.tests.off_contract.by_tag.care_education_placement.count] and the social care exemption needs a recorded basis [rule:CPR-73].

## 2. Background

The register approved by the auditor puts 4 risks in scope. Analysis of the full published spend population shows 150 general procurement suppliers with an annualised estimate above the quote tier and no exact notice match [metric:$.tests.off_contract.by_tag.general_procurement.count], 132 split-purchase candidates [metric:$.tests.split_purchases.by_tag.general_procurement.count] and 5 suppliers paid after every matching notice ended [metric:$.tests.expired_notice_spend.by_tag.general_procurement.count]. These are indicators to investigate, not findings.

## 3. Approach

The audit tests each in-scope risk against the controls the Contract Procedure Rules require, starting with the largest general procurement indicators, then the split and threshold indicators, then expiry and variation, and finally care and education placements as a separate test population that is never mixed with general procurement. Each test draws a deterministic sample from the analytics lists and asks the council for the supporting records listed in the request list. The split-purchase tests cover the quote tier and, in a separate test, the two upper tiers, so the highest-value groups are not left out of the sampled population.

## 4. Sampling

Samples are drawn by code from the full flagged lists in `outputs/analytics-full/`, sorted by the recipe shown in audit-program.md and taken in order, so a re-run draws the same items. Each sampled transaction is confirmed to exist in `cleaned_spend.csv`. Size follows the risk score: score 15 or more: 40 items, score 10 or more: 30 items, score 5 or more: 20 items, score 1 or more: 10 items. Items are suppliers, flagged groups or single payments depending on the list; up to 5 of each item's largest transactions are pulled.

| Test | Risk | Source list | Population | Items drawn | Transactions | Sample file |
|---|---|---|---|---|---|---|
| T-01 | R-01 | off_contract.csv | 150 | 20 | 54 | `samples/T-01.csv` |
| T-02 | R-01 | high_value_suppliers.csv | 183 | 20 | 45 | `samples/T-02.csv` |
| T-03 | R-01 | high_value_suppliers.csv | 183 | 10 | 30 | `samples/T-03.csv` |
| T-04 | R-02 | split_purchases.csv | 40 | 20 | 59 | `samples/T-04.csv` |
| T-05 | R-02 | threshold_clustering.csv | 8 | 8 | 8 | `samples/T-05.csv` |
| T-10 | R-02 | split_purchases.csv | 5 | 5 | 14 | `samples/T-10.csv` |
| T-06 | R-03 | expired_notice_spend.csv | 5 | 5 | 7 | `samples/T-06.csv` |
| T-07 | R-03 | spend_vs_award.csv | 6 | 6 | 12 | `samples/T-07.csv` |
| T-08 | R-05 | off_contract.csv | 311 | 30 | 88 | `samples/T-08.csv` |
| T-09 | R-05 | high_value_suppliers.csv | 315 | 15 | 42 | `samples/T-09.csv` |

In total 10 sample file(s) and 359 transactions.

## 5. Limitations

- All annualised figures are estimates built from the published spend window and may be inflated by one-off or seasonal payments [metric:$.caveats].
- Contracts Finder carries only contracts above its own publication level and call-offs may sit under a notice in another name, so absence of a notice is an indicator and not evidence that no contract exists.
- No agreed-action or follow-up data is available, so the plan cannot test whether past audit actions were closed.
- Spend carries no Companies House numbers, so joins to notices rely on normalised names and near-miss names are left for the auditor.
- The auditor asked that placement commissioning be considered in light of the adverse Personal Budgets opinion; this plan tests placements separately and does not extend to personal budget payments, which are excluded from the spend population as payments to individuals.
- Off-contract indicators also fire for grants, premises and agency staff spend; these tags are outside the approved risks, so no test samples them. The auditor is asked to confirm that they stay out of scope.
- Schools are not covered by a procurement test and personal budget payments are excluded from the spend population as payments to individuals; the auditor is asked to confirm that both exclusions stand.

## 6. Rule coverage

74 testable rules in rules.json: 49 cited by a risk, control or test, 25 listed as not tested with a reason. See risk-control-matrix.md.

## 7. Sign-off

The pack is cross-checked by the QA scripts; the auditor signs off in `outputs/review.md`.
