"""Resolve thresholds from outputs/rules.json only."""
import json, sys

TYPES = {"procedure", "advertising", "approval", "exception"}
SRC = {"spend", "contracts"}


def load(path="outputs/rules.json"):
    r = json.load(open(path))
    rules = r["rules"]
    tiers = {}  # amount -> dict
    skipped = {}
    for x in rules:
        for side in ("threshold_low", "threshold_high"):
            b = x.get(side)
            if b and b.get("param") and r["parameters"].get(b["param"]) is None:
                s = skipped.setdefault(b["param"], set())
                s.add(x["rule_id"])
        if x["type"] not in TYPES or not (set(x["evidence_source"]) & SRC):
            continue
        for side in ("threshold_low", "threshold_high"):
            b = x.get(side)
            if not b or b.get("amount") is None:
                continue
            if side == "threshold_low":
                incl_start = bool(b["inclusive"])
            else:  # high bound exclusive ("less than T") -> T itself starts the next band
                incl_start = not bool(b["inclusive"])
            t = tiers.setdefault(b["amount"], {"amount": b["amount"], "rule_ids": set(), "clauses": set(),
                                               "votes": set()})
            t["rule_ids"].add(x["rule_id"]); t["clauses"].add(x["clause"])
            t["votes"].add(incl_start)
    out = []
    for a, t in sorted(tiers.items()):
        disagree = len(t["votes"]) > 1
        out.append({"amount": a, "inclusive_start": (True in t["votes"]) and not disagree,
                    "rule_ids": sorted(t["rule_ids"]), "clauses": sorted(t["clauses"]),
                    "inclusivity_disagreement": disagree})
    def pick(typ):
        c = [x for x in rules if x["clause"] == "Appendix B row B1" and x["type"] == typ
             and x.get("threshold_low") and x["threshold_low"].get("amount") is not None]
        if not c:
            sys.exit(f"STOP: no rule with clause 'Appendix B row B1' type {typ}")
        return c[0]["threshold_low"]["amount"], c[0]["rule_id"]
    q, qr = pick("procedure"); n, nr = pick("advertising")
    sk = [{"param": p, "rule_ids": sorted(ids),
           "reason": "value not stated in the Contract Rules PDF; no value supplied"}
          for p, ids in sorted(skipped.items())]
    for p, v in r["parameters"].items():
        if v is None and p not in skipped:
            sk.append({"param": p, "rule_ids": [], "reason": "value not stated in the Contract Rules PDF; no value supplied; no rule bound uses it"})
    return {"tiers": out, "quote_tier": q, "quote_rule": qr, "notice_tier": n, "notice_rule": nr,
            "skipped_tiers": sk}

if __name__ == "__main__":
    print(json.dumps(load(), indent=1))
