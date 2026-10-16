---
name: extract-rules
description: Extract every testable rule from data/contract-rules.pdf (West Berkshire Contract Rules) into outputs/rules.json, with clause, page, thresholds and a verbatim quote for each, then verify it. Use when the auditor runs /extract-rules or the rules file must be rebuilt.
---

# extract-rules

Turn `data/contract-rules.pdf` into `outputs/rules.json`, then prove it with
`verify_quotes.py`. Run everything from the project root. If the PDF is missing
or `pdftotext` is not installed, stop and say so; never work from memory.

## What the PDF looks like (read before extracting)

- 15 pages. The footer carries the page number, so **page N of the PDF = the
  footer number**. Clauses are numbered `1.1` … `11.14`, nesting up to four
  levels (`10.7.9.1`). Heading words such as "Preliminaries" are not clauses,
  but `6.23` is a heading that carries a clause number.
- Pages 1-10 are the rules. Appendices follow: **A** (delegated authority, 4
  value bands, p11), **B** (financial thresholds and mandatory processes, rows
  A, B1, B2, C, D, p12, footnotes p13), **C** (exclusions from competition,
  rows A-F, p14-15, closing note p15). Appendix rows are identified as
  `Appendix B row B1`, `Appendix A row 3`, and so on.
- **The PDF never states the Threshold amounts.** "the Threshold" /
  "the relevant Threshold" (defined in 1.4, footnote *** of Appendix B) is
  published elsewhere and differs for Goods & Services, Works/Concession and
  Light Touch. Only these figures are printed: £500,000, £2.5 million, £1,000,
  £25,000 (and £24,999.99), £5,000, 10% bond. Never supply a Threshold value.
- The PDF has placeholders (`Part []`, `Parts [] (Call-In)`) and drafting
  slips; these are recorded in `notes`, not silently repaired.

## Steps

1. **Extract and read.** `pdftotext data/contract-rules.pdf` (plain) and
   `pdftotext -layout data/contract-rules.pdf` (columns), both to the scratchpad;
   read all of both. Plain mode keeps each table cell's sentence contiguous,
   which is what quotes are checked against; layout mode shows which cell
   belongs to which row.
2. **List the clauses.** `.venv/bin/python .claude/skills/extract-rules/verify_quotes.py --inventory`
   prints every clause id and its start page (about 160). Every id there must
   end up in `rules` or `excluded`.
3. **Classify each clause.**
   - **Rule** if it states a threshold, a required action, or an approver that
     an auditor could test, using spend data, `contracts.csv`, committee papers,
     or documents requested from the council. Include rules testable only by
     document request (`evidence_source: ["document-request"]`).
   - **Excluded** if it is background, a definition, a statutory quotation,
     purpose, an intention without a testable requirement, a heading, or
     already fully captured by another entry. Give a one-line reason.
   - One clause may yield several rules (for example a table row with a
     procedure and an advertising requirement, or two value bands).
   - A parent may cover children via `also_covers`: `["7.4.1", "7.4.2"]`, or
     `"10.7.*"` for all descendants. Use this only when the quote and reason
     genuinely cover them.
4. **Write `outputs/rules.json`** in the schema below.
5. **Verify:** `.venv/bin/python .claude/skills/extract-rules/verify_quotes.py`.
   Fix every `E-` line and re-run until it prints `PASS`. If a quote fails,
   re-copy it from the PDF text; never edit the check, the page, or the quote
   to make the error go away without re-reading the source.
6. **Report:** rule count, excluded count, parameters left null, the notes, and
   the verifier output. Do not claim success unless the last run said PASS.

## Schema of `outputs/rules.json`

```json
{
  "source": {"file": "data/contract-rules.pdf", "pages": 15},
  "parameters": {
    "THRESHOLD_GOODS_SERVICES": null,
    "THRESHOLD_WORKS_CONCESSION": null,
    "THRESHOLD_LIGHT_TOUCH": null,
    "THRESHOLD_RELEVANT": null
  },
  "rules": [
    {
      "rule_id": "CPR-01",
      "clause": "Appendix B row B1",
      "page": 12,
      "type": "procedure",
      "scope": ["goods_services"],
      "condition": "Goods and services, total value £25,000 or more and less than the Threshold",
      "threshold_low":  {"amount": 25000, "param": null, "inclusive": true},
      "threshold_high": {"amount": null, "param": "THRESHOLD_GOODS_SERVICES", "inclusive": false},
      "required_action": "Invitations to quote sent via the Procurement Portal to at least three appropriate sources",
      "approver": null,
      "evidence_source": ["contracts", "document-request"],
      "verbatim_quote": "Invitations to quote must be sent via the Procurement Portal to at least three appropriate sources",
      "also_covers": [],
      "notes_ref": ["N-03"]
    }
  ],
  "excluded": [
    {"clause": "1.1", "page": 1, "reason": "Quotes the statutory power; background, no requirement.", "also_covers": []}
  ],
  "notes": [
    {
      "note_id": "N-01",
      "kind": "contradiction",
      "clauses": ["7.2", "Appendix B row B1"],
      "description": "One or two sentences saying what conflicts or is missing.",
      "evidence": [{"page": 6, "quote": "exact words from the PDF"}]
    }
  ]
}
```

Field rules (all enforced by the verifier):

- **Top level** has exactly `source`, `parameters`, `rules`, `excluded`, `notes`.
- **`rule_id`**: `CPR-01`, `CPR-02`, … sequential, no gaps, in document order.
- **`clause`**: an id from `--inventory`. **`page`**: PDF page (1-15) where the
  quote is; the clause's start page or the next one.
- **`type`**: `procedure`, `advertising`, `approval`, `exception`,
  `anti-avoidance`, `valuation`, `record-keeping`, `contract-terms`,
  `formality`. The no-splitting/aggregation clause (6.16) is `anti-avoidance`;
  at least one rule must have that type.
- **`scope`**: list from `goods_services`, `works`, `concession`, `light_touch`;
  or `["all"]` alone.
- **Thresholds**: `threshold_low` / `threshold_high` are `null` when open-ended
  or absent, else `{amount, param, inclusive}` with exactly one of `amount`
  (non-negative **integer** pounds) or `param` (a name declared in
  `parameters`). `inclusive` is whether the printed bound includes that value:
  "£25,000 or more" → inclusive true; "less than £25,000" → inclusive false;
  "above £500,000" → inclusive false; "up to" → inclusive true.
  "more than £24,999.99" has pence: record `amount: 25000, inclusive: true`
  and add a note explaining the conversion. Amounts are VAT-exclusive only
  where the PDF says so; say it in `condition`.
- **`parameters`**: every threshold the PDF names but does not state. Values are
  always `null`. Use `THRESHOLD_GOODS_SERVICES`, `THRESHOLD_WORKS_CONCESSION`,
  `THRESHOLD_LIGHT_TOUCH` where the clause names the type, and
  `THRESHOLD_RELEVANT` where it says only "the (relevant) Threshold" (it
  resolves to one of the three by contract type). Add more only if the PDF
  names another unstated figure. Downstream agents fill the values from a
  published source, with the auditor's approval; this skill never does.
- **`required_action`**, **`condition`**: short paraphrase of what the PDF
  says, no added requirements. **`approver`**: the role as the PDF names it
  (for example "Service Director", "S.151 Officer", "Monitoring Officer",
  "relevant board", "Executive"), or `null`. Do not translate roles.
- **`evidence_source`**: one or more of `spend` (the monthly spend workbooks),
  `contracts` (`contracts.csv`), `committee-papers`, `document-request` (needs
  files from the council such as exception reports, contract files, seal
  register).
- **`verbatim_quote`**: copied exactly, one contiguous passage from the stated
  page, at least 10 characters. Quote the sentence or table cell that carries
  the requirement, not the clause number. Whitespace and line breaks are
  ignored when checking; wording, punctuation and case are not. pdftotext drops
  a hyphen at a line break ("Call-In" appears as "CallIn"); the check tolerates
  that.
- **`excluded`** (one line, no newline in `reason`): every clause not in
  `rules`. A clause may not appear in both lists or twice in `excluded`.
- **`notes`**: `N-01`, `N-02`, … sequential. `kind`: `contradiction` (two
  passages disagree), `gap` (the rules leave a case uncovered), `placeholder`
  (unfilled drafting such as `Part []`), `ambiguity` (can be read two ways).
  Each carries at least one verbatim `evidence` quote with its page. Rules
  that depend on a noted issue list it in `notes_ref`.

## Drafting problems to look for

These were spotted when this skill was written. Confirm each against the text
before recording it, quote the passages, and add any others you find. Record
only what you can quote.

- 7.2 says "more than £24,999.99" while Appendix B writes "£25,000 or more".
- 7.2 limits exceptions to contracts above that value, yet 7.4.1 sets approval
  for exceptions "up to the Threshold" (nothing says what applies below £25,000).
- 5.2 (a £5,000 tender-publication line) reads as a continuation of the 5.1
  list of published items, and Appendix B row A mandates no advertising below
  £25,000.
- Appendix A: row 1 "up to relevant Threshold" and row 2 "less than £500,000"
  can overlap or leave a gap depending on the Threshold; Appendix B row C
  ("Above £500,000 and less than the Threshold") implies a Threshold above
  £500,000 for some contract types. Row 2 writes "threshold" in lower case.
- Appendix B: nothing covers value of £1,000 or less (row A starts "Above
  £1,000"); footnote *** is never referenced in the table; row D's scope reads
  "Goods and Services Works, Concession contracts…" without a separator.
- Appendix C: the closing note requires the relevant board to approve every
  exempted contract above the Threshold, but row D (extensions) names only the
  S151 Officer. Row C contains a broken sentence ("no further competition is
  being undertaken a competition has already…") and ends "; or" with no
  following alternative.
- Placeholders: `Part []` (title), `Parts [] (Call-In)` and `[] (Forward Plan)`
  in Appendix A.
- Role names are "Service Director", "Head of Service", "Executive Director"
  in different clauses; do not unify them.
- Duplicated or overlapping clauses (for example 7.1 and 7.7; 9.2 and 9.3
  retention periods).

## Files in this skill

- `verify_quotes.py`: the checker (`--inventory` lists clauses).
- `test_verify_quotes.py`: self-test; builds a clean fixture, applies
  deliberate errors and confirms each is caught. Run it after editing the
  verifier: `.venv/bin/python .claude/skills/extract-rules/test_verify_quotes.py`.
- `fixtures/bad_rules.json`: a fixture with several deliberate errors, written
  by the self-test.
