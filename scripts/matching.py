import re
from difflib import SequenceMatcher
import pandas as pd

def ext_keys(name):
    """Extended keys for a raw supplier name (each side of t/a)."""
    s = str(name).upper().replace("&", " AND ")
    sides = re.split(r"\bT/A:?|\bT\s*/\s*A\b|\bTRADING AS\b", s)
    out = []
    for i, p in enumerate(sides):
        p = re.sub(r"[^\w\s]|_", " ", p)
        p = re.sub(r"\b(LTD|LIMITED|PLC|LLP)\b", " ", p)
        p = re.sub(r"^\s*THE\b", " ", p)
        p = re.sub(r"\s+", "", p)
        if p: out.append((p, "extended_key" if len(sides) == 1 else "t_a_side"))
    return out

def candidates(spend_sup, notices):
    """spend_sup: DataFrame [supplier(raw example), norm_supplier, gbp]; notices: notice rows.
    Returns candidate DataFrame for spend suppliers with no exact match."""
    exact = set(notices.norm_supplier)
    nk = []
    for _, r in notices.iterrows():
        for k, m in ext_keys(r.notice_supplier):
            nk.append((k, m, r.notice_id, r.notice_supplier, r.window_status))
    by_key = {}
    by_block = {}
    for t in nk:
        by_key.setdefault(t[0], []).append(t)
        by_block.setdefault(t[0][:3], []).append(t)
    rows = []
    for _, s in spend_sup[~spend_sup.norm_supplier.isin(exact)].iterrows():
        seen = set()
        for k, m in ext_keys(s.supplier):
            for t in by_key.get(k, []):
                key = (t[2], t[3])
                if key in seen: continue
                seen.add(key)
                rows.append((s.supplier, s.norm_supplier, t[3], t[2], "t_a_side" if "t_a_side" in (m, t[1]) else "extended_key", 1.0, t[4], s.gbp))
            for t in by_block.get(k[:3], []):
                key = (t[2], t[3])
                if key in seen: continue
                sc = SequenceMatcher(None, k, t[0]).ratio()
                if sc >= 0.85:
                    seen.add(key)
                    rows.append((s.supplier, s.norm_supplier, t[3], t[2], "fuzzy", round(sc, 3), t[4], s.gbp))
    return pd.DataFrame(rows, columns=["spend_supplier", "norm_supplier", "notice_supplier", "notice_id", "method", "score", "notice_status", "spend_3m_gbp"])
