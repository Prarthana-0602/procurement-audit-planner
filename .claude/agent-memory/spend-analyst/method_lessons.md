---
name: method-lessons
description: How-to lessons for the spend-analyst pipeline (library quirks, method choices); no data or findings
metadata:
  type: feedback
---

- Run scripts from project root; scripts import each other via sys.path (scripts/ dir) or PYTHONPATH=scripts. Use non-capturing groups (?:...) in str.contains patterns to avoid pandas warnings. macOS sed -i needs a backup arg: do edits in Python instead.
- Header row is row 1 in one workbook and row 2 in others; one workbook has hundreds of trailing blank rows. Record row numbers before dropping blanks.
- Tier selection by literal rule (type + evidence_source spend/contracts) omits the 1,000 bound (CPR-58 is document-request only). Report this to the lead each run.
- Duplicates chained by 7-day gaps give long groups for recurring care payments; split episodes over 30 days catch monthly recurring invoices at large suppliers. State both in the report.
