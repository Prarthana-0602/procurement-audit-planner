"""Runs: each lives in its own copy of the repo under RUNS_DIR/<id>; committed outputs are never touched."""
import json
import os
import secrets
import shutil
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

from . import config
from .config import redact

COPY_IGNORE = shutil.ignore_patterns(".git", ".venv", "__pycache__", "harness", "history-work", "runs", ".DS_Store")
ACTIVE = {"running", "waiting"}  # a run in either status blocks a new one

_lock = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def run_dir(run_id: str) -> Path:
    if not run_id.replace("-", "").replace("_", "").isalnum():
        raise KeyError(run_id)
    p = config.RUNS_DIR / run_id
    if not p.is_dir():
        raise KeyError(run_id)
    return p


def prepare(dest: Path) -> None:
    """Copy the repo into dest and reset it to a fresh project: no outputs, no generated scripts."""
    config.RUNS_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copytree(config.REPO_ROOT, dest, ignore=COPY_IGNORE)
    # Part A results are not carried into a new run.
    shutil.rmtree(dest / "outputs", ignore_errors=True)
    (dest / "outputs").mkdir()
    scripts = dest / "scripts"
    for item in list(scripts.iterdir()) if scripts.is_dir() else []:
        if item.name != "checks":  # the QA scripts are part of the method, not an analyst product
            shutil.rmtree(item) if item.is_dir() else item.unlink()
    # The agent files call .venv/bin/python. A wrapper that execs this interpreter (and so its installed
    # requirements) works whether that is the container's Python or a venv; a symlink would lose pyvenv.cfg.
    py = dest / ".venv" / "bin" / "python"
    py.parent.mkdir(parents=True)
    py.write_text(f'#!/bin/sh\nexec "{sys.executable}" "$@"\n')
    py.chmod(0o755)
    # Runs relay the team themselves (see engine.py); do not enable native agent teams inside a run.
    (dest / ".claude" / "settings.json").write_text("{}\n")


def create() -> str:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-") + secrets.token_hex(2)
    dest = config.RUNS_DIR / run_id
    prepare(dest)
    save_state(run_id, {"id": run_id, "created": _now(), "stage": "phase1", "status": "running",
                        "message": "Starting", "cost_usd": 0.0, "error": None})
    (dest / "events.jsonl").touch()
    return run_id


def load_state(run_id: str) -> dict:
    return json.loads((run_dir(run_id) / "state.json").read_text())


def save_state(run_id: str, state: dict) -> None:
    p = config.RUNS_DIR / run_id / "state.json"
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=1))
    os.replace(tmp, p)


def update(run_id: str, **fields) -> dict:
    with _lock:
        s = load_state(run_id)
        s.update(fields)
        save_state(run_id, s)
        return s


def add_cost(run_id: str, usd: float) -> None:
    with _lock:
        s = load_state(run_id)
        s["cost_usd"] = round(s.get("cost_usd", 0.0) + (usd or 0.0), 4)
        save_state(run_id, s)


def emit(run_id: str, kind: str, text: str, who: str = "") -> None:
    """Append a progress event. Always redacted, never longer than 800 chars."""
    with _lock:
        path = config.RUNS_DIR / run_id / "events.jsonl"
        n = path.read_bytes().count(b"\n") if path.exists() else 0
        rec = {"n": n, "t": _now(), "kind": kind, "who": who, "text": redact(text)[:800]}
        with path.open("a") as f:
            f.write(json.dumps(rec) + "\n")


def events(run_id: str, after: int = -1) -> list[dict]:
    path = run_dir(run_id) / "events.jsonl"
    out = []
    for line in path.read_text().splitlines():
        rec = json.loads(line)
        if rec["n"] > after:
            out.append(rec)
    return out


def list_runs() -> list[dict]:
    if not config.RUNS_DIR.is_dir():
        return []
    out = []
    for p in sorted(config.RUNS_DIR.iterdir(), reverse=True):
        if (p / "state.json").exists():
            out.append(json.loads((p / "state.json").read_text()))
    return out


def active_run() -> dict | None:
    for s in list_runs():
        if s["status"] in ACTIVE:
            return s
    return None


def mark_interrupted() -> None:
    """After a restart no task is running: anything still 'running' was cut off."""
    for s in list_runs():
        if s["status"] == "running":
            update(s["id"], status="failed", error="interrupted by a server restart")
