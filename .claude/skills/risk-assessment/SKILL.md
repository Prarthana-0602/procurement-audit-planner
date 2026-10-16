---
name: risk-assessment
description: The method for rating procurement audit risks on the council's own likelihood x impact scale and producing outputs/risk-register.md and the auditor's decision template. Loaded by the risk-assessor agent. You write judgments to outputs/risk-ratings.json; build_register.py resolves every citation and number and computes the scores. Also governs the revision run after the auditor's decisions.
---

# risk-assessment

You supply **judgment** (which risks, what scores, why). `build_register.py`
supplies **everything checkable** (citations, figures, score, band). Never type a
number from the data, never compute a score, never write the register by hand.
Run from the project root. If `outputs/rules.json`, `analytics.json` or
`history.json` is missing, stop and say so; never rate from memory.

## 1. Read the inputs by structure, not in full

Inspect with small Python snippets (`.keys()`, counts, `top20[:3]`); never print a
whole file. What exists today:

- `analytics.json`: `$.tests.<name>` for `threshold_clustering`, `split_purchases`,
  `off_contract`, `duplicates`, `expired_notice_spend`, `spend_vs_award`,
  `high_value_suppliers`. Each has `status`, `count` (or `counts`), `gbp`, `by_tag`,
  `top20`, `note`. Also `$.population.*`, `$.tags.<tag>.*`, `$.window.*`,
  `$.name_matching.*`, and `$.caveats[n]` (read the caveats before rating).
  Example paths: `$.tests.off_contract.count`,
  `$.tests.off_contract.by_tag.general_procurement.gbp`,
  `$.tests.off_contract.top20[0].gbp`, `$.population.gbp_analysed`.
- `rules.json`: `rules[].rule_id` (`CPR-59` is the £25,000 quote rule; `CPR-60`
  the notice rule; the anti-avoidance rule has `type: anti-avoidance`).
- `history.json`: audit items with ids: `OP-nn` (audit opinions), `FU-nn`
  (follow-ups), `RT-nn` (risk themes), `GAP-nn` (what the papers do not contain),
  `DISC-nn` (discrepancies). Adverse opinions today: `OP-12` (Personal Budgets,
  Limited Assurance), `FU-02` (Weak / Unsatisfactory), `FU-03` (Limited
  Assurance). `GAP-01`: no agreed actions with due dates exist, so never claim an
  action is overdue. The strategic risk register is not public, so do not cite it.

## 2. Write outputs/risk-ratings.json

```json
{
  "risks": [{
    "id": "R-01",
    "title": "Spend above the quote tier with no matching contract notice",
    "description": "Indicator that ... may ...",
    "likelihood": {"score": 4, "justification": "text with [metric:$.tests.off_contract.count] ...",
                   "rubric_override": {"score": 3, "reason": "..."}},
    "impact": {"score": 4, "justification": "... [rule:CPR-59] ..."},
    "repeat_finding": {"history": ["OP-12"], "note": "same theme: ..."},
    "evidence": ["bullet with a citation", "..."],
    "proposed_focus": "what the audit should look at"
  }],
  "revision": {"summary": "...", "changes": [{"risk_id": "R-01", "field": "impact", "reason": "..."}]}
}
```

`rubric_override`, `repeat_finding` and `revision` are optional. Risk ids are
`R-nn`, stable across revisions.

**Citations.** Tags inside any justification, evidence line or description:
`[rule:CPR-59]`, `[metric:$.tests.off_contract.count]`, `[history:OP-12]`.
A metric tag is a path into analytics.json; a rule tag is a `rule_id`; a history
tag is an item id. **Hard rule: each of the likelihood and impact justifications
needs at least one tag that resolves, or the builder drops the whole risk** (it
appears under "Excluded risks" with the reason). A tag that does not resolve is
marked `UNRESOLVED` and warned about; do not guess paths, look them up.

**Figures.** Every figure in prose is a placeholder `{{$.path}}`, optionally
`{{$.path|gbp}}`, `|int` or `|pct`. The builder fills it from analytics.json.
A placeholder that does not resolve drops the risk. A typed number ("£2m", "45
payments", "12%") draws a warning; small counting words ("two tests") are fine.
Ids such as CPR-59 and years are not figures. Indicators come with their caveats:
say "annualised estimate" for off-contract spend, and never use the off-contract
test to question suppliers below the publication tier.

**Spend metrics: general_procurement first.** Every spend test reports a
`by_tag` split. A risk that rests on a spend metric cites the
**general_procurement** figures as its primary evidence, for example
`$.tests.off_contract.by_tag.general_procurement.count` and `.gbp`, not the
all-tags totals. Care and education placement spend
(`by_tag.care_education_placement`) recurs by design: standing placements are
paid monthly to the same providers at the same amounts, so duplicates, repeat
payments and threshold clustering there are expected patterns, not indicators of
the same weight. Treat it separately:
- Give it its own risk (for example one on care-placement commissioning
  controls) or its own evidence line, labelled as care and education placements.
  Never fold it into a general procurement risk's evidence or justification.
- Do not count it toward a general procurement risk's likelihood rubric; the
  tests cited there are cited through their general_procurement figures.
- A care_education_placement risk is rated on its own evidence. Say in its
  justification that repeat payment is the normal pattern, and rely on tests
  that are not explained by recurrence (for example off-contract, expired
  notice) or on audit history such as `OP-12`.
- The other tags (`agency_staff`, `grant`, `premises`) are cited as secondary
  evidence, labelled by tag. If a test has no general_procurement entry in
  `by_tag`, say so rather than falling back to the all-tags total.

**Language.** Indicators to investigate, never wrongdoing by the council, a
department or a supplier. Say "may", "indicator", "to investigate". Do not name
suppliers in titles; supplier names stay in the analytics-full lists.

## 3. Likelihood rubric (binding; the builder checks it)

Likelihood answers: how likely is it that the control failure behind this
indicator is real and occurring in the next 12 months (council Table 2)?

| Distinct indicator tests cited with a non-zero count | Base likelihood |
|---|---|
| 0 | 1 Rare |
| 1 | 2 Unlikely |
| 2 | 3 Likely |
| 3 or more | 4 Almost Certain (cap) |

- Count only `threshold_clustering`, `split_purchases`, `off_contract`,
  `duplicates`, `expired_notice_spend`, `spend_vs_award`, cited by a metric tag
  under `$.tests.<name>` in the **likelihood** justification. `high_value_suppliers`
  is a population to request evidence for, not an indicator: it never counts.
  A test that was skipped or has a zero count does not count.
- **5 Certain is reached only by the repeat-finding uplift**: indicators alone
  never prove a risk is certain.
- **Repeat-finding uplift:** if the same theme was an adverse finding before
  (Limited Assurance, No Assurance, Weak or Unsatisfactory in `OP-`/`FU-` items),
  add `repeat_finding.history` with those ids; likelihood is base + 1 (cap 5). The
  builder checks each id is an audit item with an adverse opinion, and prints the
  uplift. Cite the audit in the justification too. If you cite an adverse audit
  but claim no uplift, the builder warns; decide whether it is the same theme.
  Reasonable or Substantial Assurance on the theme does not lower the score; cite
  it as context.
- If the rubric gives a score you think is wrong, do not just type another: add
  `likelihood.rubric_override {score, reason}` (the base before any uplift). The
  register prints the override and the reason for the auditor.
- A score that does not equal the rubric (plus uplift) without an override drops
  the risk. That is what makes two runs rate the same evidence the same way.

## 4. Impact (council Table 1)

Choose the highest Table 1 level whose criteria the evidence supports (financial
loss to the council as % of annual budget, assets, reputation, compliance /
litigation / regulatory). Name the criterion in the justification, then cite the
rule or metric behind it. Table 1 numbering is used (Negligible 1, Minor 2,
Medium 3, Major 4, Critical 5). Where an estimate falls in the 0.25%-0.3%
overlap between Medium and Major, rate the higher (Major). An indicator count
is not itself a loss: tie impact to the rule's requirement or the £ totals.

## 5. Scoring-method conflicts

The builder reads the recorded discrepancies in history.json that affect scoring
and prints, in the register header, one reading **used** and the other **marked**
(band label High vs Medium-High; Corporate Risk Register at 15+ vs 9+; Medium
impact 2 vs 3; the 0.25%-0.3% overlap). Never resolve a conflict silently or
argue it away in a justification. A conflict the builder has no rule for is
printed as UNRESOLVED for the auditor. If history.json reports no usable method,
the builder falls back to 1-5 Very low...Very high and says so in the header.

## 6. Build, then report

```
.venv/bin/python .claude/skills/risk-assessment/build_register.py
```

It writes `outputs/risk-register.md` (ends with "Auditor decisions") and
`outputs/auditor-comments.md`. Read its output: fix every EXCLUDED risk and every
warning that is yours, then rebuild. Report to the main agent: risks kept, risks
excluded and why, warnings you left and why, and the scoring-method conflicts
printed in the header. Then the human gate: the auditor fills in **Decision**
(Approve, Reject or Amend) and a **Comment** for each row of
`auditor-comments.md`. Approve = in scope. To dictate a score on an Amend, the
auditor writes `L=n` and/or `I=n` in the comment.

Existing decisions in `auditor-comments.md` are kept whenever the file is
rewritten. Never edit that file yourself.

## 7. Revision run (after the gate)

Re-run only when `auditor-comments.md` has decisions. Change **only** what they
ask: Reject, remove the risk from risk-ratings.json; Amend, make the requested
change (apply `L=`/`I=` scores exactly; the register marks them as auditor
overrides); Approve, touch nothing. Add a `revision` block: a summary and one
`changes` entry (`risk_id`, `field`, `reason`) per changed field, where `field`
is one of title, description, likelihood, impact, repeat_finding, evidence,
proposed_focus. Then run the builder. It compares with the previous register and
**fails, writing nothing**, if a decision is undecided or unapplied, an override
was not applied, a change was not asked for, a change is not declared (or is
declared but did not happen), a risk was added or silently removed, or an
approved risk now fails the checks. On success the register has a "Revision N:
what changed" header built from the real differences.

The builder embeds its previous-run state in a comment at the end of
`risk-register.md`; do not edit or delete it.
