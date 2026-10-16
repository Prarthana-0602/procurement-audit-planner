"""Run the seven tests; write outputs/analytics-full/<test>.csv and outputs/analytics.json."""
import json, os, sys
from datetime import datetime, timezone
import pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
import thresholds, notices, matching

OUT = "outputs/analytics-full"
SETTINGS = {"clustering_band": 0.9, "split_window_days": 30, "duplicate_window_days": 7,
            "spend_vs_award_ratio_flag": 1.25, "fuzzy_cutoff": 0.85}
TAGS = ["agency_staff", "grant", "premises", "care_education_placement", "general_procurement"]


def r2(x): return round(float(x), 2)

def by_tag_payments(df):
    return {t: {"count": int(len(g)), "gbp": r2(g.amount.sum())} for t, g in df.groupby("tag")}

def by_tag_items(df, col="tag", gcol="gbp"):
    return {t: {"count": int(len(g)), "gbp": r2(g[gcol].sum())} for t, g in df.groupby(col)}

def clean_records(df, n=20):
    return json.loads(df.head(n).to_json(orient="records", date_format="iso"))

def main():
    meta = json.load(open(f"{OUT}/_clean_meta.json"))
    rules = json.load(open("outputs/rules.json"))
    th = thresholds.load()
    W = meta["window"]; F = W["annualise_factor"]
    sp = pd.read_csv(f"{OUT}/cleaned_spend.csv", parse_dates=["date"])
    sp["supplier"] = sp.supplier.fillna("")
    contracts_present = os.path.exists("data/contracts.csv")
    caveats = []
    # supplier table
    disp = sp.groupby("norm_supplier").supplier.agg(lambda s: s.value_counts().index[0])
    sup = sp.groupby("norm_supplier").agg(gbp=("amount", "sum"), payments=("amount", "size"),
                                          services=("service", lambda s: "; ".join(sorted(set(s))))).reset_index()
    sup["supplier"] = sup.norm_supplier.map(disp)
    tg = sp.pivot_table(index="norm_supplier", columns="tag", values="amount", aggfunc="sum", fill_value=0)
    sup["primary_tag"] = sup.norm_supplier.map(tg.idxmax(axis=1))
    sup["gbp_by_tag"] = sup.norm_supplier.map(lambda k: json.dumps({t: r2(v) for t, v in tg.loc[k].items() if v != 0}))
    sup["annualised_estimate"] = sup.gbp * F
    sup = sup.sort_values("gbp", ascending=False).reset_index(drop=True)
    sup["gbp"] = sup.gbp.round(2); sup["annualised_estimate"] = sup.annualised_estimate.round(2)

    # contracts
    nt, clog, cand, cand_count = None, {"present": False}, None, {}
    exact_status = {}
    if contracts_present:
        nt, cl = notices.load(W["start"], W["end"])
        clog = {"present": True, **{k: cl[k] for k in ["rows_read", "rows_kept", "rows_dropped", "earliest_published", "latest_published"]}}
        if cl["rows_kept"] < 50: caveats.append("Fewer than 50 council notice rows kept: possible export cap.")
        low = {y: c for y, c in cl["notices_by_pub_year"].items() if c < 3}
        if low: caveats.append(f"Publication years with fewer than 3 notices (possible export cap or partial year): {low}.")
        caveats.append(f"Earliest Published Date in contracts.csv is {cl['earliest_published']}; contracts awarded before that are invisible, so 'no matching notice found' is never evidence that no contract exists.")
        nt_idx = nt.groupby("norm_supplier")
        for k, g in nt_idx:
            exact_status[k] = g
        cand = matching.candidates(sup[["supplier", "norm_supplier", "gbp"]], nt)
        cand.to_csv(f"{OUT}/name_candidates.csv", index=False)
        cand_count = cand.groupby("norm_supplier").notice_id.nunique().to_dict()
        nt.drop(columns=["published_dt", "start_dt", "end_dt", "awarded_dt"]).to_csv(f"{OUT}/_notices_parsed.csv", index=False)
    sup["candidate_count"] = sup.norm_supplier.map(lambda k: int(cand_count.get(k, 0)))

    def notice_status(k):
        if not contracts_present: return "not assessed"
        g = exact_status.get(k)
        if g is None: return "none"
        s = set(g.window_status)
        return "live" if "live" in s else "future" if "future" in s else "expired"
    sup["notice_status"] = sup.norm_supplier.map(notice_status)

    tests = {}
    # ---- 1 clustering
    rows, tiers_out = [], []
    for t in th["tiers"]:
        T = t["amount"]; lo = SETTINGS["clustering_band"] * T
        m = (sp.amount >= lo) & ((sp.amount < T) if t["inclusive_start"] else (sp.amount <= T))
        h = sp[m].copy(); h["tier"] = T; h["tier_rule_ids"] = ";".join(t["rule_ids"])
        h["pct_of_tier"] = (h.amount / T * 100).round(2)
        rows.append(h)
        tiers_out.append({"tier": T, "status": "ran", "band": [lo, T], "upper_inclusive": not t["inclusive_start"],
                          "rule_ids": t["rule_ids"], "count": int(len(h)), "gbp": r2(h.amount.sum()),
                          "suppliers": int(h.norm_supplier.nunique())})
    c1 = pd.concat(rows).sort_values("amount", ascending=False)
    c1[["row_id", "tier", "tier_rule_ids", "date", "supplier", "norm_supplier", "service", "narrative", "amount", "pct_of_tier", "tag"]].to_csv(f"{OUT}/threshold_clustering.csv", index=False)
    for s in th["skipped_tiers"]:
        tiers_out.append({"tier": s["param"], "status": "skipped", "reason": s["reason"], "rule_ids": s["rule_ids"]})
    tests["threshold_clustering"] = {"status": "ran", "parameters": {"band_factor": SETTINGS["clustering_band"]},
        "note": "Single payments near a limit; not contract values. Risk indicator to investigate only.",
        "tiers": tiers_out, "counts": int(len(c1)), "gbp": r2(c1.amount.sum()), "by_tag": by_tag_payments(c1),
        "top20": clean_records(c1[["row_id", "tier", "supplier", "date", "amount", "tag"]])}

    # ---- 2 split
    pos = sp[sp.amount > 0].sort_values(["norm_supplier", "date", "row_id"])
    nonpos = int((sp.amount <= 0).sum())
    eps_all, tiers2 = [], []
    for t in th["tiers"]:
        T = t["amount"]; eps = []
        for k, g in pos.groupby("norm_supplier"):
            g = g.reset_index(drop=True)
            if len(g) < 2: continue
            used = set()
            for i in range(len(g)):
                if i in used: continue
                d0 = g.date[i]
                idx = [j for j in range(i, len(g)) if j not in used and (g.date[j] - d0).days <= SETTINGS["split_window_days"] and (g.date[j] - d0) <= pd.Timedelta(days=SETTINGS["split_window_days"])]
                if len(idx) < 2: continue
                sub = g.loc[idx]
                below = (sub.amount < T) if t["inclusive_start"] else (sub.amount <= T)
                tot = sub.amount.sum()
                reach = tot >= T if t["inclusive_start"] else tot > T
                if below.all() and reach:
                    used.update(idx)
                    tags = set(sub.tag)
                    eps.append({"tier": T, "supplier": g.supplier[i], "norm_supplier": k, "first_date": sub.date.min(), "last_date": sub.date.max(),
                                "payments": len(sub), "total_gbp": r2(tot), "max_payment": r2(sub.amount.max()),
                                "tag": tags.pop() if len(tags) == 1 else "mixed", "row_ids": ";".join(sub.row_id)})
        e = pd.DataFrame(eps, columns=["tier", "supplier", "norm_supplier", "first_date", "last_date", "payments", "total_gbp", "max_payment", "tag", "row_ids"])
        eps_all.append(e)
        tiers2.append({"tier": T, "status": "ran", "rule_ids": t["rule_ids"], "episodes": int(len(e)), "gbp": r2(e.total_gbp.sum()),
                       "suppliers": int(e.norm_supplier.nunique()), "by_tag": by_tag_items(e, gcol="total_gbp") if len(e) else {}})
    c2 = pd.concat(eps_all).sort_values("total_gbp", ascending=False)
    c2.to_csv(f"{OUT}/split_purchases.csv", index=False)
    for s in th["skipped_tiers"]:
        tiers2.append({"tier": s["param"], "status": "skipped", "reason": s["reason"], "rule_ids": s["rule_ids"]})
    tests["split_purchases"] = {"status": "ran", "parameters": {"window_days": SETTINGS["split_window_days"], "positive_amounts_only": True, "non_positive_rows_ignored": nonpos},
        "note": "Pattern to investigate: repeat payments to one supplier within 30 days whose sum reaches a tier each payment stays under. Low tiers are noisy (recurring commissioned care); read by tag.",
        "tiers": tiers2, "counts": int(len(c2)), "gbp": r2(c2.total_gbp.sum()), "by_tag": by_tag_items(c2, gcol="total_gbp"),
        "top20": clean_records(c2.drop(columns=["norm_supplier"]))}
    caveats.append("split_purchases: the lowest tier (5,000) is noisy and dominated by recurring payments; review by tag before drawing any conclusion. The 1,000 tier is not analysed (see parameters.tier_selection_note).")

    # ---- supplier-level helpers
    def sup_out(df):
        return df[["supplier", "norm_supplier", "gbp", "annualised_estimate", "payments", "services", "primary_tag", "gbp_by_tag", "notice_status", "candidate_count"]]
    def sup_json(df, extra=None):
        d = {"count": int(len(df)), "gbp": r2(df.gbp.sum()), "annualised_estimate_gbp": r2(df.annualised_estimate.sum()),
             "by_tag": by_tag_items(df, col="primary_tag"), "with_candidate": int((df.candidate_count > 0).sum())}
        return d

    # ---- 3 off contract
    if contracts_present:
        NT = th["notice_tier"]
        above = sup[sup.annualised_estimate > NT]
        flagged = above[above.notice_status == "none"]
        sup_out(flagged).to_csv(f"{OUT}/off_contract.csv", index=False)
        matched = above[above.notice_status != "none"]
        tests["off_contract"] = {"status": "ran", "parameters": {"notice_tier": NT, "rule_id": th["notice_rule"], "annualise_factor": F},
            "note": "Risk indicator: annualised estimate (3-month total x factor) above the notice tier with no exact-name notice found. Not evidence that no contract exists.",
            "suppliers_above_tier": int(len(above)), **sup_json(flagged),
            "exact_matched_above_tier": {s: int((matched.notice_status == s).sum()) for s in ["live", "expired", "future"]},
            "flagged_with_candidates": int((flagged.candidate_count > 0).sum()),
            "top20": clean_records(sup_out(flagged))}
        caveats += ["off_contract: Contracts Finder carries only contracts above its own publication level.",
                    "off_contract: framework and DPS call-offs may sit under a notice in another name.",
                    "off_contract: social-care placements may be covered by Appendix C row F.",
                    "off_contract: results are never used to question suppliers below the notice tier."]
    else:
        tests["off_contract"] = {"status": "skipped", "reason": "data/contracts.csv not present"}

    # ---- 4 duplicates
    d = sp[sp.amount > 0].sort_values(["norm_supplier", "amount", "date", "row_id"])
    grp = []
    for (k, a), g in d.groupby(["norm_supplier", "amount"]):
        if len(g) < 2: continue
        g = g.reset_index(drop=True); cur = [0]
        def emit(ix):
            if len(ix) < 2: return
            s = g.loc[ix]; tags = set(s.tag)
            same = s.date.nunique() == 1
            grp.append({"group": "same_timestamp" if same else "distinct_timestamp", "supplier": s.supplier.iloc[0], "norm_supplier": k, "amount": a,
                        "payments": len(s), "first_date": s.date.min(), "last_date": s.date.max(), "span_days": (s.date.max() - s.date.min()).days,
                        "gbp_repeat": r2(a * (len(s) - 1)), "tag": tags.pop() if len(tags) == 1 else "mixed", "row_ids": ";".join(s.row_id)})
        for j in range(1, len(g)):
            if (g.date[j] - g.date[j - 1]) <= pd.Timedelta(days=SETTINGS["duplicate_window_days"]): cur.append(j)
            else: emit(cur); cur = [j]
        emit(cur)
    c4 = pd.DataFrame(grp).sort_values("gbp_repeat", ascending=False)
    c4.to_csv(f"{OUT}/duplicates.csv", index=False)
    dj = {}
    for gname, g in c4.groupby("group"):
        dj[gname] = {"groups": int(len(g)), "payments": int(g.payments.sum()), "gbp_repeat": r2(g.gbp_repeat.sum()),
                     "by_tag": by_tag_items(g, gcol="gbp_repeat"), "top20": clean_records(g.drop(columns=["norm_supplier"]))}
    tests["duplicates"] = {"status": "ran", "parameters": {"window_days": SETTINGS["duplicate_window_days"], "positive_amounts_only": True},
        "note": "Pattern to investigate: same supplier, same amount, dates within 7 days. same_timestamp groups may be separate lines of one posting. gbp_repeat is the amount of payments after the first in each group.",
        "counts": int(len(c4)), "gbp_repeat": r2(c4.gbp_repeat.sum()), "by_tag": by_tag_items(c4, gcol="gbp_repeat"), "groups": dj}
    caveats.append("duplicates: recurring same-amount payments (care placements, rents) can match by design; read by tag.")

    # ---- 5 expired
    if contracts_present:
        ex = []
        for _, s in sup[sup.notice_status == "expired"].iterrows():
            g = exact_status[s.norm_supplier]
            ex.append({**s[["supplier", "norm_supplier", "gbp", "annualised_estimate", "payments", "primary_tag", "gbp_by_tag", "candidate_count"]].to_dict(),
                       "notices": int(g.notice_id.nunique()), "latest_notice_end": g.end_dt.max().date().isoformat(), "notice_ids": ";".join(sorted(set(g.notice_id)))})
        e5 = pd.DataFrame(ex).sort_values("gbp", ascending=False) if ex else pd.DataFrame(columns=["supplier", "gbp", "primary_tag"])
        e5.to_csv(f"{OUT}/expired_notice_spend.csv", index=False)
        tests["expired_notice_spend"] = {"status": "ran", "parameters": {"window_start": W["start"]},
            "note": "Risk indicator: payments in the window to suppliers whose every exact-matching notice ended before the window start. A newer contract may exist with no notice.",
            "count": int(len(e5)), "gbp": r2(e5.gbp.sum()), "by_tag": by_tag_items(e5.rename(columns={"primary_tag": "tag"}), col="tag") if len(e5) else {},
            "with_candidate": int((e5.candidate_count > 0).sum()) if len(e5) else 0, "top20": clean_records(e5.drop(columns=["norm_supplier"])) if len(e5) else []}
        caveats.append("expired_notice_spend: a newer contract, extension or framework call-off may exist with no notice (Appendix C row D).")
    else:
        tests["expired_notice_spend"] = {"status": "skipped", "reason": "data/contracts.csv not present"}

    # ---- 6 spend vs award
    if contracts_present:
        out6, skipped_years = [], 0
        for _, s in sup[sup.notice_status == "live"].iterrows():
            g = exact_status[s.norm_supplier]; lv = g[g.window_status == "live"].drop_duplicates("notice_id")
            if len(lv) != 1: continue
            r = lv.iloc[0]
            if r.suppliers_in_notice != 1 or not (pd.notna(r.awarded_value_num) and r.awarded_value_num > 0): continue
            if pd.isna(r.start_dt) or pd.isna(r.end_dt): skipped_years += 1; continue
            yrs = (r.end_dt - r.start_dt).days / 365.25
            if yrs <= 0: skipped_years += 1; continue
            ratio = s.annualised_estimate / (r.awarded_value_num / yrs)
            out6.append({"supplier": s.supplier, "norm_supplier": s.norm_supplier, "notice_id": r.notice_id, "awarded_value": r.awarded_value_num,
                         "contract_start": r.start_dt.date().isoformat(), "contract_end": r.end_dt.date().isoformat(), "contract_years": round(yrs, 4),
                         "gbp": s.gbp, "annualised_estimate": s.annualised_estimate, "ratio": round(ratio, 4), "primary_tag": s.primary_tag, "candidate_count": s.candidate_count})
        a6 = pd.DataFrame(out6).sort_values("ratio", ascending=False)
        f6 = a6[a6.ratio >= SETTINGS["spend_vs_award_ratio_flag"]]
        f6.to_csv(f"{OUT}/spend_vs_award.csv", index=False)
        a6.to_csv(f"{OUT}/_spend_vs_award_all_evaluated.csv", index=False)
        tests["spend_vs_award"] = {"status": "ran", "parameters": {"ratio_flag": SETTINGS["spend_vs_award_ratio_flag"]},
            "note": "Risk indicator: annualised spend estimate at or above 1.25x the award pro-rated per year. Award values may be estimates or maxima; the supplier may hold other contracts.",
            "evaluated": int(len(a6)), "skipped_nonpositive_duration_or_missing_dates": skipped_years,
            "count": int(len(f6)), "gbp": r2(f6.gbp.sum()), "by_tag": by_tag_items(f6, col="primary_tag", gcol="gbp") if len(f6) else {},
            "top20": clean_records(f6.drop(columns=["norm_supplier"]))}
        caveats.append("spend_vs_award: award values may be estimates or maxima, and the supplier may hold other contracts; ratio is a risk indicator only.")
    else:
        tests["spend_vs_award"] = {"status": "skipped", "reason": "data/contracts.csv not present"}

    # ---- 7 high value
    QT = th["quote_tier"]
    hv = sup[sup.annualised_estimate > QT].sort_values("gbp", ascending=False)
    sup_out(hv).to_csv(f"{OUT}/high_value_suppliers.csv", index=False)
    hj = {"status": "ran", "parameters": {"quote_tier": QT, "rule_id": th["quote_rule"], "annualise_factor": F},
          "note": "Population to request contract and quote evidence for; annualised estimate (3-month total x factor) above the quote tier.",
          **sup_json(hv), "top20": clean_records(sup_out(hv))}
    if contracts_present:
        hj["by_notice_status"] = {s: {"count": int((hv.notice_status == s).sum()), "gbp": r2(hv[hv.notice_status == s].gbp.sum())} for s in ["live", "expired", "future", "none"]}
    tests["high_value_suppliers"] = hj

    cj = ({"exact_matches": int(sup.notice_status.isin(["live", "expired", "future"]).sum()), "candidates": int(len(cand)),
           "suppliers_with_candidates": int(cand.norm_supplier.nunique()), "candidates_file": f"{OUT}/name_candidates.csv",
           "by_method": {k: int(v) for k, v in cand.method.value_counts().items()}}
          if contracts_present else {"exact_matches": 0, "candidates": 0, "candidates_file": None})
    caveats.append("Annualised figures are estimates (3-month total x 4); one-off or seasonal payments inflate them.")
    caveats.append("Redacted-supplier rows, pension/statutory rows, personal transfers and other public bodies are excluded from all tests (see population).")
    caveats.append("Spend carries no Companies House numbers; joins to notices are by normalised name only. Non-exact names are candidates for the auditor, never counted.")
    amb = [k for k in th["tiers"] if k["inclusivity_disagreement"]]
    ana = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "agent": "spend-analyst",
        "inputs": {"rules_json": {"file": "outputs/rules.json", "rules": len(rules["rules"]), "quote_check": "PASS"},
                   "spend_files": meta["spend_files"], "contracts": clog},
        "window": {"start": W["start"], "end": W["end"], "months": W["months"], "annualise_factor": F},
        "parameters": {"tiers": th["tiers"], "quote_tier": QT, "quote_tier_rule": th["quote_rule"], "notice_tier": th["notice_tier"], "notice_tier_rule": th["notice_rule"],
                       "skipped_tiers": th["skipped_tiers"],
                       "tier_selection_note": "Tiers = distinct amounts in rules of type procedure/advertising/approval/exception whose evidence_source includes spend or contracts. The 1,000 bound (CPR-58, evidence_source document-request only) is therefore not a tier; 500 (CPR-06) and 25,000 exception CPR-23 do not qualify either. 500,000 has an inclusivity disagreement between rules ("+", ".join(a for a in ["CPR-04","CPR-55","CPR-56","CPR-61","CPR-62","CPR-63","CPR-64"]) + "); exclusive-start (wider band) used.",
                       "settings": {**SETTINGS, "annualise_factor": F}, "exclusion_patterns": meta["exclusion_patterns"], "keep_as_supplier": meta["keep_as_supplier"],
                       "tag_config": "see scripts/clean.py config block"},
        "population": {"rows_read": meta["rows_read"], "rows_excluded": meta["excluded"], "rows_analysed": meta["rows_analysed"],
                       "gbp_analysed": meta["gbp_analysed"], "suppliers_analysed": meta["suppliers_analysed"], "non_positive_amount_rows": nonpos},
        "tags": meta["tags"], "name_matching": cj, "tests": tests, "caveats": caveats,
        "selfcheck": {"status": "not run", "file": "outputs/analytics-selfcheck.json"}}
    json.dump(ana, open("outputs/analytics.json", "w"), indent=1, default=str)
    for k, v in tests.items():
        print(k, v["status"], {x: v[x] for x in ["counts", "count", "gbp", "gbp_repeat"] if x in v}, v.get("by_tag") and max(v["by_tag"], key=lambda t: v["by_tag"][t]["gbp"]))
    print(json.dumps(cj)); print(json.dumps(tests["threshold_clustering"]["tiers"])[:900]); print([ (t["tier"], t.get("episodes")) for t in tiers2])
    print({g: (x["groups"], x["gbp_repeat"]) for g, x in dj.items()})

if __name__ == "__main__":
    main()
