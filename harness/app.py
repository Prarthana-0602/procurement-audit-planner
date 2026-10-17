"""FastAPI app: one HTML page, a JSON API, background runs."""
import asyncio
import hmac
import os
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from . import config, engine, gates, runs
from .render import md_to_html

STATIC = Path(__file__).resolve().parent / "static"
_tasks: set[asyncio.Task] = set()
_start_lock = asyncio.Lock()


@asynccontextmanager
async def lifespan(_: FastAPI):
    config.RUNS_DIR.mkdir(parents=True, exist_ok=True)
    runs.mark_interrupted()
    yield


app = FastAPI(title="Procurement audit harness", lifespan=lifespan, docs_url=None, redoc_url=None)


def require_code(code: str | None) -> None:
    expected = os.environ.get("RUN_ACCESS_CODE", "")
    if not expected:
        raise HTTPException(503, "RUN_ACCESS_CODE is not configured on the server; runs are disabled")
    if not code or not hmac.compare_digest(code.encode(), expected.encode()):
        raise HTTPException(403, "wrong access code")


def spawn(coro) -> None:
    t = asyncio.create_task(coro)
    _tasks.add(t)
    t.add_done_callback(_tasks.discard)


def get_run(run_id: str) -> dict:
    try:
        return runs.load_state(run_id)
    except KeyError:
        raise HTTPException(404, "no such run")


def need_stage(run_id: str, stage: str) -> dict:
    s = get_run(run_id)
    if s["stage"] != stage or s["status"] != "waiting":
        raise HTTPException(409, f"run is at stage '{s['stage']}' ({s['status']}), not waiting at '{stage}'")
    return s


def read_doc(base: Path, filename: str) -> str:
    p = base / filename
    return md_to_html(p.read_text()) if p.exists() else "<p><em>Not produced yet.</em></p>"


# ---------------------------------------------------------------- pages and health
@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/api/config")
def api_config():
    a = runs.active_run()
    return {"runs_enabled": bool(os.environ.get("RUN_ACCESS_CODE")), "model": config.MODEL,
            "api_key_set": bool(os.environ.get("ANTHROPIC_API_KEY")), "active_run": a["id"] if a else None}


# ---------------------------------------------------------------- completed run (no API calls)
@lru_cache(maxsize=1)
def _completed() -> list[dict]:
    out = config.REPO_ROOT / "outputs"
    return [{"key": k, "title": t, "html": read_doc(out, f)} for k, t, f in config.DOCS]


@app.get("/api/completed")
def api_completed():
    return {"docs": _completed()}


# ---------------------------------------------------------------- new run
@app.get("/api/runs")
def api_runs():
    return {"runs": runs.list_runs()}


@app.post("/api/runs")
async def api_start(x_access_code: str | None = Header(default=None)):
    require_code(x_access_code)
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise HTTPException(503, "ANTHROPIC_API_KEY is not set on the server")
    async with _start_lock:  # one run at a time
        a = runs.active_run()
        if a:
            raise HTTPException(409, f"run {a['id']} is still active; finish or abandon it first")
        run_id = await asyncio.to_thread(runs.create)
    runs.emit(run_id, "stage", "Run created from a fresh copy of the repo.")
    spawn(engine.run_phase1(run_id))
    return {"id": run_id}


@app.get("/api/runs/{run_id}")
def api_run(run_id: str):
    return get_run(run_id)


@app.get("/api/runs/{run_id}/events")
def api_events(run_id: str, after: int = -1):
    get_run(run_id)
    return {"events": runs.events(run_id, after)}


@app.get("/api/runs/{run_id}/docs")
def api_run_docs(run_id: str):
    get_run(run_id)
    out = runs.run_dir(run_id) / "outputs"
    return {"docs": [{"key": k, "title": t, "html": read_doc(out, f)} for k, t, f in config.DOCS]}


@app.post("/api/runs/{run_id}/abandon")
def api_abandon(run_id: str, x_access_code: str | None = Header(default=None)):
    require_code(x_access_code)
    s = get_run(run_id)
    if s["status"] == "running":
        raise HTTPException(409, "a running stage cannot be abandoned; wait for it to finish")
    runs.update(run_id, status="abandoned", message="Abandoned by the auditor")
    return {"ok": True}


# ---------------------------------------------------------------- gate 1
class Decision(BaseModel):
    id: str
    decision: str
    comment: str = ""
    likelihood: int | None = None
    impact: int | None = None


class Gate1(BaseModel):
    reviewer: str
    decisions: list[Decision]


@app.get("/api/runs/{run_id}/gate1")
def api_gate1(run_id: str):
    get_run(run_id)
    d = runs.run_dir(run_id) / "outputs"
    if not (d / "auditor-comments.md").exists():
        raise HTTPException(409, "no register yet")
    return {"risks": gates.read_risks(d / "auditor-comments.md"), "register_html": read_doc(d, "risk-register.md")}


@app.post("/api/runs/{run_id}/gate1")
async def api_gate1_submit(run_id: str, body: Gate1, x_access_code: str | None = Header(default=None)):
    require_code(x_access_code)
    need_stage(run_id, "gate1")
    comments = runs.run_dir(run_id) / "outputs" / "auditor-comments.md"
    try:
        gates.write_decisions(comments, body.reviewer, [d.model_dump() for d in body.decisions])
    except gates.GateError as e:
        raise HTTPException(422, str(e))
    runs.update(run_id, stage="revision", status="running", message="Decisions saved; revising the register")
    runs.emit(run_id, "stage", "Gate 1 decisions written to auditor-comments.md.")
    spawn(engine.run_revision(run_id))
    return {"ok": True}


# ---------------------------------------------------------------- agent team and gate 2
@app.post("/api/runs/{run_id}/team")
async def api_team(run_id: str, x_access_code: str | None = Header(default=None)):
    require_code(x_access_code)
    need_stage(run_id, "team_ready")
    runs.update(run_id, stage="team", status="running", message="Starting the agent team")
    spawn(engine.run_team(run_id))
    return {"ok": True}


@app.get("/api/runs/{run_id}/gate2")
def api_gate2(run_id: str):
    get_run(run_id)
    d = runs.run_dir(run_id) / "outputs"
    if not (d / "review.md").exists():
        raise HTTPException(409, "no review yet")
    return {"verdict": gates.verdict(d / "review.md"), "review_html": read_doc(d, "review.md")}


class Gate2(BaseModel):
    auditor: str
    decision: str
    comment: str = ""


@app.post("/api/runs/{run_id}/gate2")
def api_gate2_submit(run_id: str, body: Gate2, x_access_code: str | None = Header(default=None)):
    require_code(x_access_code)
    need_stage(run_id, "gate2")
    try:
        gates.write_signoff(runs.run_dir(run_id) / "outputs" / "review.md", body.auditor, body.decision, body.comment)
    except gates.GateError as e:
        raise HTTPException(422, str(e))
    if body.decision == "signed off":
        runs.update(run_id, stage="done", status="done", message="Signed off")
    else:
        runs.update(run_id, stage="done", status="done", message="Returned to the team by the auditor")
    return {"ok": True}


@app.exception_handler(Exception)
async def unhandled(_, exc: Exception):
    return JSONResponse({"detail": "internal error"}, status_code=500)
