"""Settings for the harness. Everything comes from environment variables."""
import os
import re
from pathlib import Path

REPO_ROOT = Path(os.environ.get("HARNESS_REPO", Path(__file__).resolve().parent.parent))
DATA_DIR = Path(os.environ.get("HARNESS_DATA", "/data"))
RUNS_DIR = DATA_DIR / "runs"
MODEL = os.environ.get("HARNESS_MODEL", "sonnet")  # a Sonnet alias or id, to keep cost down
MAX_BUDGET_USD = float(os.environ.get("HARNESS_MAX_BUDGET_USD", "5"))  # per SDK session
TURN_TIMEOUT_S = int(os.environ.get("HARNESS_TURN_TIMEOUT_S", "1800"))
MAX_TEAM_ROUNDS = int(os.environ.get("HARNESS_MAX_TEAM_ROUNDS", "40"))

# Committed Part A outputs shown in the "Completed run" view, in reading order.
DOCS = [
    ("risk-register", "Risk register", "risk-register.md"),
    ("auditor-comments", "Auditor decisions", "auditor-comments.md"),
    ("planning-memo", "Planning memo", "planning-memo.md"),
    ("risk-control-matrix", "Risk-control matrix", "risk-control-matrix.md"),
    ("audit-program", "Audit program", "audit-program.md"),
    ("challenges", "Challenges", "challenges.md"),
    ("review", "QA review and sign-off", "review.md"),
]

_KEY_PATTERN = re.compile(r"sk-ant-[A-Za-z0-9_\-]{8,}")


def redact(text: str) -> str:
    """Remove the API key (its value and anything shaped like one) from text."""
    text = str(text)
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if len(key) >= 8:
        text = text.replace(key, "[redacted]")
    return _KEY_PATTERN.sub("[redacted]", text)
