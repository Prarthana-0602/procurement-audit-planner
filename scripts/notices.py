"""Parse data/contracts.csv into one row per (notice, supplier)."""
import re, sys
import pandas as pd
from clean import norm

KEEP_ORGS = {"west berkshire council", "west berkshire"}


def load(window_start, window_end):
    raw = pd.read_csv("data/contracts.csv", dtype=str, encoding="utf-8-sig")
    need = ["Notice Identifier", "Organisation Name", "Published Date", "Awarded Date", "Awarded Value",
            "Contract start date", "Contract end date", "Status", "Title"]
    miss = [c for c in need if c not in raw.columns]
    scol = [c for c in raw.columns if c.startswith("Supplier [Name|")]
    if miss or len(scol) != 1:
        sys.exit(f"STOP: contracts.csv missing columns {miss} / supplier col {scol}")
    scol = scol[0]
    kept = raw[raw["Organisation Name"].fillna("").str.strip().str.lower().isin(KEEP_ORGS)].copy()
    log = {"rows_read": len(raw), "rows_kept": len(kept), "rows_dropped": len(raw) - len(kept)}
    recs = []
    for _, r in kept.iterrows():
        blocks = [b for b in re.split(r"\]\s*\[", (r[scol] or "").strip()) if b.strip()]
        blocks = [b.strip().lstrip("[").rstrip("]") for b in blocks]
        for b in blocks:
            p = b.split("|")
            if len(p) != 6:
                sys.exit(f"STOP: supplier block with {len(p)} parts in notice {r['Notice Identifier']}")
            recs.append({"notice_id": r["Notice Identifier"], "title": r["Title"], "notice_status": r["Status"],
                         "published": r["Published Date"], "awarded_date": r["Awarded Date"],
                         "awarded_value": r["Awarded Value"], "start": r["Contract start date"], "end": r["Contract end date"],
                         "notice_supplier": p[0].strip(), "ref_type": p[2].strip(), "ref": p[3].strip(),
                         "ch_number": p[3].strip() if p[2].strip() == "COMPANIES_HOUSE" else "",
                         "suppliers_in_notice": len(blocks)})
        if not blocks:
            log["notices_without_supplier"] = log.get("notices_without_supplier", 0) + 1
    n = pd.DataFrame(recs)
    n["published_dt"] = pd.to_datetime(n.published.str[:10], format="%Y-%m-%d", errors="coerce")
    for c, d in [("start", "start_dt"), ("end", "end_dt"), ("awarded_date", "awarded_dt")]:
        n[d] = pd.to_datetime(n[c].where(n[c].fillna("").str.strip() != ""), format="%d/%m/%Y", errors="coerce")
        bad = n[c].fillna("").str.strip().ne("") & n[d].isna()
        if bad.any(): sys.exit(f"STOP: unparseable {c} dates")
    if n.published_dt.isna().any(): sys.exit("STOP: unparseable Published Date")
    n["awarded_value_num"] = pd.to_numeric(n.awarded_value, errors="coerce")
    ws, we = pd.Timestamp(window_start), pd.Timestamp(window_end)
    def st(r):
        if pd.notna(r.start_dt) and r.start_dt > we: return "future"
        if pd.notna(r.end_dt) and r.end_dt < ws: return "expired"
        return "live"
    n["window_status"] = n.apply(st, axis=1)
    n["norm_supplier"] = n.notice_supplier.map(norm)
    log["earliest_published"] = n.published_dt.min().date().isoformat()
    log["latest_published"] = n.published_dt.max().date().isoformat()
    log["notices_kept"] = int(n.notice_id.nunique())
    log["supplier_rows"] = len(n)
    yc = n.drop_duplicates("notice_id").published_dt.dt.year.value_counts().sort_index()
    log["notices_by_pub_year"] = {int(k): int(v) for k, v in yc.items()}
    log["status_counts"] = {k: int(v) for k, v in n.drop_duplicates("notice_id").window_status.value_counts().items()}
    log["blank_end_dates"] = int(n.end_dt.isna().sum())
    return n, log
