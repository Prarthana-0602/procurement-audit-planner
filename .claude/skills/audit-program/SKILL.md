---
name: audit-program
description: The method for turning auditor-approved risks into an audit program (risk, expected control, test step, targeted sample), a risk-control matrix, a planning memo and a PBC request list. Loaded by the planner agent. You write judgments to outputs/audit-plan.json; build_pack.py checks the scope, resolves every citation and figure, draws the samples and renders the three documents.
---

# audit-program

You supply **judgment** (which controls, which tests, what to sample, what to
request). `build_pack.py` supplies **everything checkable** (scope, citations,
figures, sample draws, rule coverage, the documents). Never type a number from the
data, never draw a sample yourself, never write the three documents by hand.
Run from the project root. If `outputs/rules.json`, `analytics.json`,
`risk-ratings.json`, `risk-register.md` or `auditor-comments.md` is missing, stop
and say so.

## 1. Gate first

```
.venv/bin/python .claude/skills/audit-program/build_pack.py --gate
```

It fails, and you stop, if any risk in the register has no Approve/Reject/Amend
decision in `auditor-comments.md`, if the register is still revision 0, if a
rejected risk is still in the register, or if an Amend's `L=`/`I=` is not in the
register. On success it prints the approved scope. **Approved and Amend risks are
in scope; a Reject is out** (removed from the register, recorded with its reason
in `auditor-comments.md`). Plan only the in-scope risks; the builder refuses a plan
that includes any other risk or omits one.

## 2. Read the inputs by structure, not in full

`risk-register.md` (scores, bands, conflicts), `auditor-comments.md` (decisions,
the auditor's reasons: an Amend or an Approve comment may change what to test),
`risk-ratings.json` (each risk's description, evidence and proposed focus),
`rules.json` (`rule_id`, `clause`, `type`, `condition`, `required_action`: read the
rules you cite), `analytics.json` (look metric paths up; read `$.caveats`).
`outputs/analytics-full/*.csv`: look at `head -3` and the column names only; never
print a whole file. The lists you can sample from:

| File | One row is | Pulls transactions by |
|---|---|---|
| `threshold_clustering.csv` | a payment just below a tier | its `row_id` |
| `split_purchases.csv`, `duplicates.csv` | a flagged group of payments | its `row_ids` |
| `off_contract.csv`, `high_value_suppliers.csv`, `expired_notice_spend.csv`, `spend_vs_award.csv` | a supplier | its `norm_supplier` in `cleaned_spend.csv` |
| `cleaned_spend.csv` | a payment | its `row_id` |

## 3. Write outputs/audit-plan.json

```json
{
  "version": 1,
  "memo": {"background": "...", "approach": "...", "limitations": ["...", "..."]},
  "risks": [{
    "risk_id": "R-01",
    "rationale": "why this approved risk is in the plan, cited",
    "controls": [{"id": "C-01", "description": "the control expected to exist [rule:CPR-59]"}],
    "tests": [{
      "id": "T-01", "control_ids": ["C-01"],
      "step": "what the auditor does, citing [rule:CPR-59] or [metric:$.tests.off_contract.count]",
      "sample": {"file": "off_contract.csv",
                 "filter": [{"col": "primary_tag", "op": "==", "value": "general_procurement"}],
                 "sort": [{"by": "annualised_estimate", "desc": true}],
                 "n": 15, "method": "top", "rows_per_item": 3},
      "pbc": ["PBC-01"]
    }]
  }],
  "pbc_items": [{"id": "PBC-01", "item": "what the council is asked to provide"}],
  "rules_not_tested": [{"rule_ids": ["CPR-04"], "reason": "why no test is planned"}]
}
```

**Controls.** Per risk, the control the rules say should exist (an approval, a
quote, a notice, a recorded basis). Every control description needs at least one
resolving `[rule:CPR-nn]`, or the builder fails with "uncited control". Every
control needs at least one test, and every test covers at least one control of the
same risk.

**Test steps.** One concrete thing the auditor does: obtain, compare, recalculate,
confirm approval. Each cites at least one `[rule:..]` or `[metric:..]` that
resolves. Each lists the PBC items it needs.

**Samples.** `file` is a CSV in `analytics-full/`. `filter` ops: `==`, `!=`, `>`,
`>=`, `<`, `<=`, `in`, `contains`. Always include a `sort`: the draw takes the top
`n` in that order (`method: "top"`) or evenly spaced through it (`"spread"`); ties
break on the file's first column, so the draw is deterministic. Prefer the
`general_procurement` tag for general risks and a separate test on
`care_education_placement` for a placement risk; never mix the two in one sample.
**Size is set by the risk's score** and `n` may not exceed it:
score 15 or more: 40 items; 10 to 14: 30; 5 to 9: 20; 4 or less: 10. Omit `n` to
take the full size; set it lower when a population is small or the step is narrow.
Up to `rows_per_item` (default 3, max 5) of each item's largest transactions are
pulled from `cleaned_spend.csv` and checked to exist there. A test that cannot
be sampled (a document review) sets `"sample": null` and a `no_sample_reason`.

**Rule coverage.** Every rule in `rules.json` must be cited by an in-scope risk,
control or test, or listed in `rules_not_tested` with a reason (one reason may
cover several `rule_ids`). A rule cannot be both. Do not list a rule as not tested
because it is inconvenient; the reason is for the auditor to read (for example the
evidence is a document request, or the threshold parameter is null in rules.json).

**Figures.** Every figure in prose is a placeholder: `{{$.path}}` (optionally
`|gbp`, `|int`, `|pct`) from analytics.json, or `{{@key}}` for a figure the builder
computes (`@scope.approved`, `@scope.sample_rows`, `@T-01.population`,
`@T-01.items`, `@T-01.rows`, `@R-01.score`, `@scope.rules_total`...). A typed
number draws a warning. Look paths up, never guess.

**Language.** Indicators to investigate, never wrongdoing by the council, a
department or a supplier. Say "may", "indicator", "to investigate". The builder
fails on accusatory words (fraud, corrupt, illegal...) and on any supplier name in
your prose. Supplier names live only in the sample files.

**Memo.** `background` (what the data and the register say), `approach` (what the
audit will do and in what order), and `limitations` (at least: annualised
estimates, call-offs under another name, no agreed-action data, anything the
auditor's comments raise). Auditor decisions and rejections are added by the
builder from `auditor-comments.md`.

## 4. Build, then report

```
.venv/bin/python .claude/skills/audit-program/build_pack.py
```

On any failure it prints every problem and writes nothing; fix your plan and
rebuild. On success it writes `outputs/planning-memo.md`,
`risk-control-matrix.md`, `audit-program.md` (ending with the PBC list),
`samples/T-*.csv` and `pack-figures.json` (every figure it computed, for the QA
number check). Increase `version` in the plan when you rebuild after challenges
or QA failures. Report: risks planned, tests, sample files and transactions,
rules cited versus not tested, warnings you left and why.

Tested by `.venv/bin/python .claude/skills/audit-program/test_build_pack.py`.
