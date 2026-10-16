---
name: verifier-quote-lessons
description: How-to lessons for building history.json quotes that pass scripts/verify_history.py
metadata:
  type: feedback
---

- Fragment quotes ("a | b | c") must be in layout order and within 4 non-blank layout lines; fragments and whole quotes have minimum lengths (4 and 10 squashed chars). For a cell shorter than that, join it with its row neighbour in one fragment (e.g. "Moderate 4-6 None Monitor risk").
- An opinion field must sit contiguously inside its own quote after removing " | ". A wrapped opinion cell with another column's value between its lines (e.g. "Limited / Satisfactory / Assurance") cannot hold both opinions: put the second in a nested object with its own quote.
- Plain text drops some dashes in table cells; -layout drops some wrapped lines (a title line vanished). Check both.
- Prose and multi-line table cells are often contiguous in plain text: use single-fragment quotes from plain for per-cell scale entries.
