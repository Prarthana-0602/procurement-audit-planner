# Audit program

**Status:** DRAFT pack v3, awaiting QA and auditor sign-off · built 2026-10-16 09:22 UTC · from risk register revision 1 · indicators to investigate, not findings of wrongdoing

## R-01: Spend above the quote tier with no matching contract notice

**Rating:** L2 × I4 = 8 High · auditor decision: Approve · sample size by score: up to 20 items per test

Indicator that general procurement spend above the quote tier may have been placed without a competitive process or a published notice. Notices are only published above the Contracts Finder level and a call-off may sit under a notice in another name, so this is a population to investigate, not a finding.

**Proposed focus (risk-assessor):** Request contract, quote and exception evidence for the largest general procurement suppliers with no matching notice; test against the quote rule and Appendix C exceptions.

**Expected controls**

- **C-01**: Purchases at or above the quote tier follow invitations to quote through the Procurement Portal, and larger ones follow full tender [rule:CPR-59] [rule:CPR-61] [rule:CPR-63] [rule:CPR-65] [rule:CPR-17].
- **C-02**: A contract notice is published and the award is notified so it appears on the contracts register [rule:CPR-60] [rule:CPR-62] [rule:CPR-64] [rule:CPR-66] [rule:CPR-11] [rule:CPR-12] [rule:CPR-40] [rule:CPR-08]. The notice is approved and issued by the Service Lead for Procurement and Commissioning or their delegate [rule:CPR-13]. Details of every invitation to tender are published [rule:CPR-07].
- **C-03**: Any exception or waiver of competition is approved by the right officer, fully documented and reported [rule:CPR-23] [rule:CPR-24] [rule:CPR-25] [rule:CPR-26] [rule:CPR-27] [rule:CPR-28] [rule:CPR-29] [rule:CPR-30] [rule:CPR-31] [rule:CPR-32] [rule:CPR-67].
- **C-04**: The award is approved at the level the contract value requires and a written record of the procurement is kept [rule:CPR-02] [rule:CPR-03] [rule:CPR-04] [rule:CPR-05] [rule:CPR-54] [rule:CPR-55] [rule:CPR-56] [rule:CPR-57] [rule:CPR-36] [rule:CPR-37] [rule:CPR-34] [rule:CPR-35].
- **C-05**: Use of a purchasing scheme or framework is supported by advice that the council may use it [rule:CPR-33] [rule:CPR-69].

**Test steps**

| Test | Controls | Step | Sample | PBC |
|---|---|---|---|---|
| T-01 | C-01, C-02 | For the largest general procurement suppliers flagged with no exact notice match, obtain the quotes or tender record and the published notice, or the basis for none, and compare with the quote rule [rule:CPR-59] and the indicator count [metric:$.tests.off_contract.by_tag.general_procurement.count]. Confirm any notice was approved and issued by the Service Lead for Procurement and Commissioning or their delegate [rule:CPR-13]. Confirm the invitation to tender was published where required [rule:CPR-07]. | off_contract.csv: filter: primary_tag == general_procurement; sort: annualised_estimate desc; top; 20 of 150 suppliers → 54 transactions in `samples/T-01.csv` | PBC-01, PBC-02 |
| T-02 | C-03, C-05 | For a spread of general procurement suppliers above the quote tier, obtain any exception, waiver or framework basis and confirm approval by the named officer [rule:CPR-30] [rule:CPR-33]; population in metric [metric:$.tests.high_value_suppliers.by_tag.general_procurement.count]. | high_value_suppliers.csv: filter: primary_tag == general_procurement; sort: annualised_estimate desc; spread; 20 of 183 suppliers → 45 transactions in `samples/T-02.csv` | PBC-03 |
| T-03 | C-04 | For the sampled suppliers, obtain the award approval at the level the contract value requires and confirm it is signed by the named approver: the relevant Service Director for the lowest band [rule:CPR-54]; the Service Director on the written report approved by the relevant board for the next band [rule:CPR-55]; the Service Director with the Portfolio Holder for a Key Decision [rule:CPR-56]; the Executive for the highest band [rule:CPR-57]. Also confirm the procurement record is held [rule:CPR-36]. | high_value_suppliers.csv: filter: primary_tag == general_procurement; sort: gbp desc; top; 10 of 183 suppliers → 30 transactions in `samples/T-03.csv` | PBC-04 |

## R-02: Split purchases and threshold-hugging payments

**Rating:** L3 × I3 = 9 High · auditor decision: Approve · sample size by score: up to 20 items per test

Indicator that general procurement purchases may have been split or kept just below a procedure threshold, which the aggregation rules prohibit. Recurring payments also produce these patterns, so each is to be investigated.

**Proposed focus (risk-assessor):** Review flagged general procurement supplier sets for a single underlying need and check how the total value was estimated.

**Expected controls**

- **C-06**: Contract value is a genuine estimate over the whole term and purchases are not artificially split [rule:CPR-14] [rule:CPR-15].
- **C-07**: Repeat or similar purchases are valued together and advice is sought on the applicable procedure [rule:CPR-16].

**Test steps**

| Test | Controls | Step | Sample | PBC |
|---|---|---|---|---|
| T-04 | C-06, C-07 | For general procurement supplier sets with several payments whose combined value crosses the quote tier, obtain the value estimate and order history and judge whether one need was split [rule:CPR-15] [metric:$.tests.split_purchases.by_tag.general_procurement.count]. | split_purchases.csv: filter: tag == general_procurement and tier == 25000; sort: total_gbp desc; top; 20 of 40 groups → 59 transactions in `samples/T-04.csv` | PBC-05 |
| T-05 | C-06 | For general procurement payments just below the quote tier, obtain the order, estimate and approval and check how the value was set [rule:CPR-14] [metric:$.tests.threshold_clustering.by_tag.general_procurement.count]. | threshold_clustering.csv: filter: tag == general_procurement and tier == 25000; sort: amount desc; top; 8 of 8 transactions → 8 transactions in `samples/T-05.csv` | PBC-05 |
| T-10 | C-06, C-07 | For the highest-value general procurement supplier sets in the upper tiers, obtain the value estimate and the approval at the level the combined value requires, and judge whether one need was split [rule:CPR-15] [rule:CPR-56] [rule:CPR-57] [metric:$.tests.split_purchases.by_tag.general_procurement.count]. | split_purchases.csv: filter: tag == general_procurement and tier in ['500000', '2500000']; sort: total_gbp desc; top; 5 of 5 groups → 14 transactions in `samples/T-10.csv` | PBC-05 |

## R-03: Spend after notice expiry or beyond the awarded value

**Rating:** L3 × I3 = 9 High · auditor decision: Approve · sample size by score: up to 20 items per test

Indicator that spend may continue after a published contract ended, or exceed the award, without a recorded extension or variation. A newer contract may exist with no notice, and award values may be estimates.

**Proposed focus (risk-assessor):** Obtain extension and variation approvals, or replacement contracts, for the flagged suppliers.

**Expected controls**

- **C-08**: An extension to an existing contract has the approval of the statutory finance officer [rule:CPR-70].
- **C-09**: A variation of scope has prior written approval from the Monitoring Officer and the statutory finance officer, and board approval where it follows an extension [rule:CPR-71] [rule:CPR-72].

**Test steps**

| Test | Controls | Step | Sample | PBC |
|---|---|---|---|---|
| T-06 | C-08 | For each general procurement supplier paid after notice expiry, obtain the extension approval or the replacement contract [rule:CPR-70] [metric:$.tests.expired_notice_spend.by_tag.general_procurement.count]. Check the approval is signed by the statutory finance officer. | expired_notice_spend.csv: filter: primary_tag == general_procurement; sort: annualised_estimate desc; top; 5 of 5 suppliers → 7 transactions in `samples/T-06.csv` | PBC-06 |
| T-07 | C-09 | For general procurement suppliers whose annualised estimate is well above the award, obtain variation approvals and the award basis [rule:CPR-71] [metric:$.tests.spend_vs_award.by_tag.general_procurement.count]. Check the approval is signed by both the Monitoring Officer and the statutory finance officer, and for any extension that the relevant board approved it [rule:CPR-72]. | spend_vs_award.csv: filter: primary_tag == general_procurement; sort: ratio desc; top; 6 of 6 suppliers → 12 transactions in `samples/T-07.csv` | PBC-06 |

## R-05: Care and education placement commissioning controls

**Rating:** L3 × I4 = 12 High · auditor decision: Amend · sample size by score: up to 30 items per test

Care and education placements, shown separately from general procurement. Indicator that placement spend above the quote tier may lack a matching notice; Appendix C row F may exempt many placements, so evidence of the basis is to be requested.

**Proposed focus (risk-assessor):** Request the commissioning basis (Appendix C row F, framework or notice) for the largest placement providers.

**Expected controls**

- **C-10**: Where the social care exemption is used, the reasons for the choice of provider are recorded on the individual's case notes by the responsible Service Directors [rule:CPR-73].
- **C-11**: Where the exemption applies above the threshold the relevant board approves the contract; Provider Selection Regime decisions are recorded [rule:CPR-74] [rule:CPR-68].

**Test steps**

| Test | Controls | Step | Sample | PBC |
|---|---|---|---|---|
| T-08 | C-10 | For the largest placement providers with no exact notice match, obtain the recorded reasons for the choice of provider and the commissioning basis [rule:CPR-73] [metric:$.tests.off_contract.by_tag.care_education_placement.count]. Confirm the record is made by the responsible Service Director. | off_contract.csv: filter: primary_tag == care_education_placement; sort: annualised_estimate desc; top; 30 of 311 suppliers → 88 transactions in `samples/T-08.csv` | PBC-07 |
| T-09 | C-11 | For a spread of placement providers above the quote tier, confirm board approval of the exemption and the Provider Selection Regime record [rule:CPR-74] [metric:$.tests.high_value_suppliers.by_tag.care_education_placement.count]. | high_value_suppliers.csv: filter: primary_tag == care_education_placement; sort: annualised_estimate desc; spread; 15 of 315 suppliers → 42 transactions in `samples/T-09.csv` | PBC-08 |

## Request list (PBC): prepared by client

| PBC | Item requested | Needed for |
|---|---|---|
| PBC-01 | Quotes, tender evaluation records and the order or contract for each sampled general procurement supplier. | T-01 |
| PBC-02 | The published contract notice and award notification, or the council's stated reason none exists. Evidence of who approved and issued each notice. The council's publication log of invitations to tender. | T-01 |
| PBC-03 | Exception or waiver reports, officer approvals, and framework or purchasing scheme call-off evidence. | T-02 |
| PBC-04 | For each sampled supplier, the award approval at the Appendix A level for its contract value (Service Director, board-approved report, Portfolio Holder Key Decision or Executive decision, as applicable), showing the approver, and the procurement record. | T-03 |
| PBC-05 | Value estimates, order history and approvals for the flagged payment sets. | T-04, T-05, T-10 |
| PBC-06 | Extension and variation approvals, replacement contracts and the award value basis. Each approval to show the approving officer (statutory finance officer for extensions; Monitoring Officer and statutory finance officer for variations). | T-06, T-07 |
| PBC-07 | Placement commissioning records showing the reasons for the choice of provider. Records to show the responsible Service Director. | T-08 |
| PBC-08 | Board approvals of social care exemptions and Provider Selection Regime decision records. | T-09 |
