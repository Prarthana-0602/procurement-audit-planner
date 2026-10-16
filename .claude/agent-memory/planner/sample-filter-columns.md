---
name: sample-filter-columns
description: Sample filter column names differ by analytics-full file (tag vs primary_tag)
metadata:
  type: reference
---

split_purchases.csv, threshold_clustering.csv, duplicates.csv use column `tag`; supplier-level files (off_contract, high_value_suppliers, expired_notice_spend, spend_vs_award) use `primary_tag`. Check headers before writing filters; builder fails with "bad filter". The `tier` filter value works as a string, e.g. "25000".
