# QA review

Pack version: v3 · register revision 1 · run 2026-10-16 02:22 · final run (no --interim)

Note: the challenger's CHALLENGER DONE message referred to pack v2; the final run is on v3, the version reported in PLANNER DONE v3. challenges.md lists "Pack reviewed: v3".

## Results

| Check | Result | Problems | Detail |
|---|---|---|---|
| check_quotes | PASS | 0 | PASS: 74 rules, 43 excluded, 15 notes, 160 PDF clauses; 0 error(s), 2 warning(s); 0 register excerpt(s) checked against rules.json |
| check_numbers | PASS | 0 | 19 figure(s) in the three documents all found in the source values |
| check_trace | PASS | 0 | rules, approved risks, High risks and challenges all trace |
| check_samples | PASS | 0 | 285 distinct transaction(s) in 10 sample file(s) and the program exist in cleaned_spend.csv and at their sheet row in the workbooks, same supplier and amount |

VERDICT: ALL CHECKS PASS

## History

| Version | Result | Failing checks |
|---|---|---|
| v1 | PASS (interim) | none |
| v2 | PASS (interim) | none |
| v3 | PASS (final) | none |

## Verdict: READY FOR SIGN-OFF

The final run on v3 printed "VERDICT: ALL CHECKS PASS".

## For the auditor

| # | Risk | Question |
|---|---|---|
| 2 | R-01 | [metric:$.tests.off_contract.by_tag.grant.count]: off-contract indicators also fire for grant, premises and agency_staff spend, which no test covers. Ask: auditor to confirm these tags stay out of scope. |
| 3 | R-05 | [history:OP-12] [history:FU-02] [history:FU-03]: Limited Assurance on Personal Budgets and adverse school follow-ups have no covering risk or test. Ask: auditor to confirm or change the exclusion. |
| 7 | R-01 | [metric:$.tests.off_contract.by_tag.general_procurement.gbp]: only risk at L2 although its indicator value exceeds R-02's at L3. Ask: auditor to confirm L=2 or amend. |

## Auditor sign-off

I have read the planning memo, the risk-control matrix and the audit program, and the
challenges marked for the auditor above.

- [x] Signed off: the pack is accepted as the audit plan
- [ ] Returned: the pack goes back to the team (reason below)

Auditor: Prarthana Patel   Date: 2026-10-16   Comment: Auditor responses to challenges for the auditor: #2 — grant, premises and agency-staff spend stay out of R-01 for this audit, which focuses on general procurement; noted for a future review. #3 — correction to my R-05 amend comment: OP-12 sits in Children with Disabilities and SEN, not adult social care. The amend to L3 stands because SEN overlaps the education-placement side of R-05. #7 — R-01 likelihood 2 stands: likelihood follows the fixed rubric on corroborating indicator tests, and the £ value is reflected in impact 4.
