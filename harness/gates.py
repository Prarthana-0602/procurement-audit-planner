"""The two human gates: writing the auditor's decisions and the sign-off block."""
import re
from datetime import datetime, timezone
from pathlib import Path

ROW = re.compile(r"^\| (R-\d+) \| (.*?) \| (.*?) \| (.*?) \| (.*?) \|\s*$")
DECISIONS = ("Approve", "Amend", "Reject")


class GateError(ValueError):
    pass


def _one_line(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).replace("|", "/").strip()


def read_risks(comments: Path) -> list[dict]:
    risks = []
    for line in comments.read_text().splitlines():
        m = ROW.match(line)
        if m:
            risks.append({"id": m[1], "title": m[2], "rating": m[3], "decision": m[4].strip(), "comment": m[5].strip()})
    if not risks:
        raise GateError("auditor-comments.md has no risk rows")
    return risks


def write_decisions(comments: Path, reviewer: str, decisions: list[dict], today: str | None = None) -> None:
    """Fill Decision and Comment for every risk. Refuses a partial set."""
    reviewer = _one_line(reviewer)
    if not reviewer:
        raise GateError("reviewer name is required")
    today = today or datetime.now(timezone.utc).date().isoformat()
    by_id = {d.get("id"): d for d in decisions}
    risks = read_risks(comments)
    missing = [r["id"] for r in risks if r["id"] not in by_id]
    if missing:
        raise GateError(f"a decision is needed for every risk; missing {', '.join(missing)}")
    new = {}
    for r in risks:
        d = by_id[r["id"]]
        decision = d.get("decision")
        if decision not in DECISIONS:
            raise GateError(f"{r['id']}: decision must be Approve, Amend or Reject")
        comment = _one_line(d.get("comment"))
        scores = ""
        if decision == "Amend":
            parts = []
            for key, label in (("likelihood", "L"), ("impact", "I")):
                v = d.get(key)
                if v in (None, "", 0):
                    continue
                if not isinstance(v, int) or not 1 <= v <= 5:
                    raise GateError(f"{r['id']}: {key} must be 1 to 5")
                parts.append(f"{label}={v}")
            if not parts:
                raise GateError(f"{r['id']}: an Amend needs a likelihood and/or an impact")
            scores = " ".join(parts) + "."
        if decision in ("Amend", "Reject") and not comment:
            raise GateError(f"{r['id']}: a comment is required for {decision}")
        new[r["id"]] = (decision, " ".join(x for x in (f"Reviewer: {reviewer}, {today}.", scores, comment) if x))
    out = []
    for line in comments.read_text().splitlines():
        m = ROW.match(line)
        if m and m[1] in new:
            out.append(f"| {m[1]} | {m[2]} | {m[3]} | {new[m[1]][0]} | {new[m[1]][1]} |")
        else:
            out.append(line)
    comments.write_text("\n".join(out) + "\n")


def verdict(review: Path) -> str:
    m = re.search(r"^## Verdict: (.+)$", review.read_text(), re.M)
    return m[1].strip() if m else "UNKNOWN"


def write_signoff(review: Path, auditor: str, decision: str, comment: str, today: str | None = None) -> None:
    """Fill the sign-off block at the end of review.md. Sign-off needs a READY verdict."""
    auditor, comment = _one_line(auditor), _one_line(comment)
    if not auditor:
        raise GateError("auditor name is required")
    if decision not in ("signed off", "returned"):
        raise GateError("decision must be 'signed off' or 'returned'")
    if decision == "signed off" and verdict(review) != "READY FOR SIGN-OFF":
        raise GateError("the pack can only be signed off when the QA verdict is READY FOR SIGN-OFF")
    if decision == "returned" and not comment:
        raise GateError("a reason is required when returning the pack")
    today = today or datetime.now(timezone.utc).date().isoformat()
    text = review.read_text()
    signed = "x" if decision == "signed off" else " "
    returned = "x" if decision == "returned" else " "
    text, n1 = re.subn(r"^- \[[ x]\] Signed off:", f"- [{signed}] Signed off:", text, flags=re.M)
    text, n2 = re.subn(r"^- \[[ x]\] Returned:", f"- [{returned}] Returned:", text, flags=re.M)
    line = f"Auditor: {auditor}   Date: {today}   Comment: {comment}"
    text, n3 = re.subn(r"^Auditor: .*$", lambda _: line, text, flags=re.M)
    if not (n1 == n2 == n3 == 1):
        raise GateError("review.md has no recognisable sign-off block")
    review.write_text(text)
