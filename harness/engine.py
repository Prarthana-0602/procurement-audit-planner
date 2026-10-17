"""Runs the repo's own skills and agents through the Claude Agent SDK.

Each stage works inside one run directory (a copy of the repo) with the project settings
loaded (CLAUDE.md, .claude/agents, .claude/skills). Nothing here rewrites a skill or agent.

Every agent runs as its own SDK session, awaited by the engine. Sessions may not launch sub-agents or
background commands (see `_no_background`), so a turn never ends while work is still going on somewhere.

Agent team: the SDK has no team API, so `run_team` is a relay orchestrator. It starts one SDK
session per teammate from the same .claude/agents/<name>.md files and carries the same
messages (PACK READY, CHALLENGE, RESPONSE, QA, DONE) between the sessions.
"""
import asyncio
import logging
import re
import subprocess
import sys
from contextlib import AsyncExitStack
from pathlib import Path

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ClaudeSDKClient, HookMatcher, ResultMessage, TextBlock, ToolUseBlock

from . import config, gates, runs
from .config import redact

log = logging.getLogger("harness.engine")
client_factory = ClaudeSDKClient  # tests replace this; production never does

TEAM = ["planner", "challenger", "qa-reviewer"]
ALIASES = {"qa": "qa-reviewer", "qa-reviewer": "qa-reviewer", "qareviewer": "qa-reviewer", "planner": "planner",
           "challenger": "challenger", "lead": "lead", "team-lead": "lead", "main": "lead"}
SEND = re.compile(r"^[ \t]*SEND TO[ \t]+([A-Za-z\-]+)[ \t]*:[ \t]*", re.M)
DONE = re.compile(r"^\s*(PLANNER|CHALLENGER|QA) DONE", re.I)

RELAY_NOTE = """

## Relay mode (added by the harness)

You are one of three separate sessions (planner, challenger, qa-reviewer) coordinated by a relay program,
not native teammates. SendMessage does not exist here. To message a teammate or the lead, write a line
starting `SEND TO <name>:` (name is planner, challenger, qa-reviewer or lead); that message continues until the
next `SEND TO` line or the end of your reply. Text before your first `SEND TO` is private commentary. Messages
from others arrive as your next user turn, headed `FROM <name>:`. When you have nothing to send or are waiting,
end your reply with no `SEND TO` line; the relay wakes you when a message arrives. The protocol words in your
instructions (PACK READY, CHALLENGE, RESPONSE, QA, DONE) apply unchanged. Wherever your instructions say you
wait, or that the lead spawned you, simply end your turn.

Do all work in the foreground: do not launch sub-agents and do not run commands in the background. Finish a
command before you reply; a reply ends your turn.
"""


STANDALONE_NOTE = """

## Standalone session (added by the harness)

You run as your own session, started by a program that waits for you to finish. No lead is available to answer
questions: if you are blocked, stop and say so in your final reply. Do all work yourself, in the foreground:
do not launch sub-agents and do not run commands in the background, because the session is over when you stop.
Finish every step, including your verification, before your final reply.
"""


class EngineError(RuntimeError):
    pass


# ----------------------------------------------------------------- helpers
def parse_agent_file(path: Path) -> dict:
    text = path.read_text()
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not m:
        raise EngineError(f"{path.name}: no frontmatter")
    front, body = m[1], m[2]
    tools = re.search(r"^tools:\s*(.+)$", front, re.M)
    skills = re.findall(r"^\s+-\s+(\S+)\s*$", front.split("skills:", 1)[1].split("\nmemory", 1)[0], re.M) if "skills:" in front else []
    return {"tools": [t.strip() for t in tools[1].split(",")] if tools else [], "skills": skills, "body": body}


def parse_messages(text: str) -> list[tuple[str, str]]:
    ms = list(SEND.finditer(text))
    out = []
    for i, m in enumerate(ms):
        end = ms[i + 1].start() if i + 1 < len(ms) else len(text)
        to = ALIASES.get(m[1].lower())
        body = text[m.end():end].strip()
        if to and body:
            out.append((to, body))
    return out


async def _no_background(input_data, tool_use_id, context) -> dict:
    """PreToolUse hook: refuse sub-agent launches and background commands in every session."""
    name, args = input_data.get("tool_name"), input_data.get("tool_input") or {}
    if name in ("Agent", "Task") or (name == "Bash" and args.get("run_in_background")):
        return {"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "permissionDecision": "deny",
            "permissionDecisionReason": "Not allowed here: do the work yourself, in the foreground. This session ends "
                                        "when you stop, so anything left running in the background would be lost."}}
    return {}


def _options(d: Path, append: str | None = None, tools: list[str] | None = None) -> ClaudeAgentOptions:
    prompt = {"type": "preset", "preset": "claude_code"}
    if append:
        prompt["append"] = append
    return ClaudeAgentOptions(
        cwd=str(d), setting_sources=["project"], skills="all", permission_mode="bypassPermissions",
        model=config.MODEL, max_budget_usd=config.MAX_BUDGET_USD, system_prompt=prompt, tools=tools,
        hooks={"PreToolUse": [HookMatcher(matcher="Agent|Task|Bash", hooks=[_no_background])]},
        stderr=lambda line: log.info("cli: %s", redact(line)[:300]),
    )


def _brief(block: ToolUseBlock) -> str:
    i = block.input or {}
    detail = i.get("command") or i.get("file_path") or i.get("skill") or i.get("description") or i.get("subagent_type") or ""
    if block.name in ("Agent", "Task"):
        detail = f"{i.get('subagent_type', '')} {i.get('description', '')}".strip()
    return f"{block.name} {str(detail)[:140]}".strip()


async def _turn(client, run_id: str, who: str, prompt: str) -> str:
    """One conversational turn: send a prompt, stream progress events, return the assistant text."""
    async def go() -> str:
        await client.query(prompt)
        texts: list[str] = []
        async for m in client.receive_response():
            if isinstance(m, AssistantMessage):
                label = who if m.parent_tool_use_id is None else f"{who}/sub-agent"
                for b in m.content:
                    if isinstance(b, TextBlock) and b.text.strip():
                        texts.append(b.text)
                        runs.emit(run_id, "text", b.text.strip(), label)
                    elif isinstance(b, ToolUseBlock):
                        runs.emit(run_id, "tool", _brief(b), label)
            elif isinstance(m, ResultMessage):
                runs.add_cost(run_id, m.total_cost_usd or 0.0)
                if m.is_error:
                    raise EngineError(f"{who}: session ended with an error ({m.subtype}, {m.api_error_status})")
        return "\n".join(texts)
    try:
        return await asyncio.wait_for(go(), config.TURN_TIMEOUT_S)
    except asyncio.TimeoutError:
        raise EngineError(f"{who}: no result within {config.TURN_TIMEOUT_S}s")


async def _lead_session(run_id: str, d: Path, prompt: str) -> str:
    async with client_factory(_options(d)) as client:
        return await _turn(client, run_id, "lead", prompt)


def _agent_options(d: Path, name: str, note: str) -> ClaudeAgentOptions:
    """Options for a session built from .claude/agents/<name>.md: its body is the system prompt, its tools the tool list."""
    spec = parse_agent_file(d / ".claude" / "agents" / f"{name}.md")
    tools = [t for t in spec["tools"] if t != "SendMessage"]
    if spec["skills"]:
        tools.append("Skill")
    return _options(d, append=spec["body"] + note, tools=tools)


async def _agent_session(run_id: str, d: Path, name: str, prompt: str) -> str:
    """Run one agent file as its own session and wait until it has finished."""
    runs.emit(run_id, "stage", f"{name} started")
    async with client_factory(_agent_options(d, name, STANDALONE_NOTE)) as client:
        text = await _turn(client, run_id, name, prompt)
    runs.emit(run_id, "stage", f"{name} finished")
    return text


# Scripts the pipeline calls by path: the verifiers, the builders and the QA runner.
REQUIRED_SCRIPTS = [
    ".claude/skills/extract-rules/verify_quotes.py",
    "scripts/verify_history.py",
    ".claude/skills/risk-assessment/build_register.py",
    ".claude/skills/audit-program/build_pack.py",
    "scripts/checks/run_checks.py",
]


def _preflight(d: Path) -> None:
    """Fail before any API spend if a script or tool the pipeline calls is missing."""
    import shutil
    absent = [f for f in REQUIRED_SCRIPTS if not (d / f).is_file()]
    if absent:
        raise EngineError("pipeline script(s) missing from the run copy: " + ", ".join(absent))
    lost = runs.missing_from_copy(d)
    if lost:
        raise EngineError(f"{len(lost)} repo file(s) missing from the run copy, e.g. " + ", ".join(lost[:5]))
    py = d / ".venv" / "bin" / "python"
    if not py.exists():
        raise EngineError(".venv/bin/python is missing in the run copy")
    p = subprocess.run([str(py), "-c", "import pandas, openpyxl"], cwd=d, capture_output=True, text=True)
    if p.returncode:
        raise EngineError("pandas/openpyxl are not importable by .venv/bin/python: " + redact(p.stderr.strip())[-200:])
    for tool in ("pdftotext", "pdfinfo"):
        if not shutil.which(tool):
            raise EngineError(f"{tool} is not installed (poppler-utils)")


def _py(d: Path, *args: str, timeout: int = 600) -> tuple[int, str]:
    """Run a project script with this interpreter, without the API key in its environment."""
    import os
    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
    p = subprocess.run([sys.executable, *args], cwd=d, capture_output=True, text=True, timeout=timeout, env=env)
    return p.returncode, redact((p.stdout + p.stderr).strip())


def _need(d: Path, *files: str) -> None:
    missing = [f for f in files if not (d / f).exists()]
    if missing:
        raise EngineError("expected output missing: " + ", ".join(missing))


def _fail(run_id: str, e: Exception) -> None:
    runs.emit(run_id, "error", f"{type(e).__name__}: {e}")
    runs.update(run_id, status="failed", error=redact(f"{type(e).__name__}: {e}")[:500], message="Failed")


# ----------------------------------------------------------------- stage: phase 1
async def run_analysts(run_id: str, d: Path) -> None:
    """spend-analyst and findings-analyst: two sessions, run concurrently, both awaited before any output check."""
    spend = _agent_session(run_id, d, "spend-analyst", (
        "Do your full task for this project as described in your instructions: analyse the spend workbooks and "
        "contracts.csv against outputs/rules.json, write outputs/analytics.json and outputs/analytics-full/, and run "
        "the self-check so outputs/analytics-selfcheck.json exists. Reply with your report in under 150 words."))
    findings = _agent_session(run_id, d, "findings-analyst", (
        "Do your full task for this project as described in your instructions: read the committee papers, write "
        "outputs/history.json and run scripts/verify_history.py until it passes. Reply with your report in under "
        "150 words."))
    results = await asyncio.gather(spend, findings, return_exceptions=True)
    for r in results:
        if isinstance(r, BaseException):
            raise r
    _need(d, "outputs/analytics.json", "outputs/analytics-selfcheck.json", "outputs/history.json")


async def run_phase1(run_id: str) -> None:
    d = runs.run_dir(run_id)
    try:
        _preflight(d)
        runs.update(run_id, message="Extracting rules (extract-rules skill)")
        await _lead_session(run_id, d, (
            "Run the extract-rules skill (the step a human starts by typing /extract-rules): follow "
            ".claude/skills/extract-rules/SKILL.md until verify_quotes.py passes. Reply in under 100 words."))
        _need(d, "outputs/rules.json")
        rc, out = _py(d, ".claude/skills/extract-rules/verify_quotes.py")
        runs.emit(run_id, "check", f"verify_quotes.py exit {rc}: {out[-300:]}")
        if rc:
            raise EngineError("rules.json failed verify_quotes.py")

        runs.update(run_id, message="Spend and findings analysis (spend-analyst and findings-analyst, in parallel)")
        await run_analysts(run_id, d)
        rc, out = _py(d, "scripts/verify_history.py")
        runs.emit(run_id, "check", f"verify_history.py exit {rc}: {out[-300:]}")
        if rc:
            raise EngineError("history.json failed verify_history.py")

        runs.update(run_id, message="Rating risks (risk-assessor)")
        await _agent_session(run_id, d, "risk-assessor", (
            "Do your full task for this project as described in your instructions: build the risk register "
            "(outputs/risk-ratings.json, then run build_register.py until it is clean). Reply with your report in "
            "under 150 words."))
        _need(d, "outputs/risk-ratings.json", "outputs/risk-register.md", "outputs/auditor-comments.md")
        runs.update(run_id, stage="gate1", status="waiting", message="Gate 1: waiting for the auditor's decisions")
        runs.emit(run_id, "stage", "Register built. Gate 1: the auditor decides each risk.")
    except Exception as e:  # noqa: BLE001 - every failure must land in the run state
        _fail(run_id, e)


# ----------------------------------------------------------------- stage: revision
async def run_revision(run_id: str) -> None:
    d = runs.run_dir(run_id)
    try:
        runs.update(run_id, stage="revision", status="running", message="Revising the register (risk-assessor)")
        await _agent_session(run_id, d, "risk-assessor", (
            "The auditor has completed outputs/auditor-comments.md. Do the revision run as described in your "
            "instructions and the risk-assessment skill's revision section, and run build_register.py until it is "
            "clean. Reply with your report in under 150 words."))
        rc, out = _py(d, ".claude/skills/audit-program/build_pack.py", "--gate")
        runs.emit(run_id, "check", f"gate check exit {rc}: {out[-300:]}")
        if rc:
            raise EngineError("the register revision did not pass the gate check")
        runs.update(run_id, stage="team_ready", status="waiting", message="Revision done. Ready to run the agent team")
        runs.emit(run_id, "stage", "Revision complete; gate check passed.")
    except Exception as e:  # noqa: BLE001
        _fail(run_id, e)


# ----------------------------------------------------------------- stage: agent team (relay)
def _bootstrap(name: str, gate_out: str) -> str:
    others = ", ".join(n for n in TEAM if n != name)
    base = f"FROM lead: The gate check passed ({gate_out}). Your teammates are {others}. "
    if name == "planner":
        return base + "Start at once. Load the audit-program skill with the Skill tool first."
    return base + "The planner starts first; the messages below are what has arrived for you."


async def run_team(run_id: str) -> None:
    d = runs.run_dir(run_id)
    try:
        rc, gate_out = _py(d, ".claude/skills/audit-program/build_pack.py", "--gate")
        if rc:
            raise EngineError("gate closed: " + gate_out[-300:])
        runs.update(run_id, stage="team", status="running", message="Agent team running (planner, challenger, qa-reviewer)")
        runs.emit(run_id, "stage", "Gate open. Starting three sessions with relayed messages.")
        inbox: dict[str, list[tuple[str, str]]] = {n: [] for n in TEAM}
        inbox["planner"].append(("lead", ""))
        started: set[str] = set()
        done: set[str] = set()
        nudges = 0
        async with AsyncExitStack() as stack:
            clients: dict[str, object] = {}
            for _ in range(config.MAX_TEAM_ROUNDS):
                active = [n for n in TEAM if inbox[n]]
                if len(done) == 3:
                    break
                if not active:
                    nudges += 1
                    if nudges > 3:
                        raise EngineError("the team stalled without all three DONE messages")
                    for n in TEAM:
                        if n not in done and n in started:
                            inbox[n].append(("lead", "Status check from the lead: if you have finished, send your DONE "
                                                     "message to lead; otherwise say what you are waiting for."))
                    continue
                if any(src != "lead" for n in active for src, _ in inbox[n]):
                    nudges = 0  # a teammate message arrived: the team is making progress, not stalled
                for n in active:
                    if n not in clients:
                        clients[n] = await stack.enter_async_context(client_factory(_agent_options(d, n, RELAY_NOTE)))

                async def one(n: str) -> str:
                    msgs, inbox[n] = inbox[n], []
                    parts = [f"FROM {src}:\n{body}" if body else "" for src, body in msgs]
                    text = "\n\n".join(p for p in parts if p)
                    if n not in started:
                        started.add(n)
                        text = _bootstrap(n, gate_out) + ("\n\n" + text if text else "")
                    return await _turn(clients[n], run_id, n, text)

                replies = await asyncio.gather(*(one(n) for n in active))
                for n, reply in zip(active, replies):
                    for to, body in parse_messages(reply):
                        first = body.splitlines()[0][:200]
                        runs.emit(run_id, "msg", f"{n} -> {to}: {first}")
                        if to == "lead":
                            if DONE.match(body):
                                done.add(n)
                        elif to in TEAM and to != n:
                            inbox[to].append((n, body))
                            if n == "planner" and body.lstrip().startswith("PACK READY"):
                                done.clear()  # an earlier DONE refers to an older pack version
        if len(done) < 3:
            raise EngineError(f"round limit reached with DONE from {sorted(done)} only")
        _need(d, "outputs/review.md", "outputs/audit-plan.json", "outputs/challenges.md")
        v = gates.verdict(d / "outputs" / "review.md")
        runs.update(run_id, stage="gate2", status="waiting", message=f"Gate 2: QA verdict {v}")
        runs.emit(run_id, "stage", f"Team finished. QA verdict: {v}")
    except Exception as e:  # noqa: BLE001
        _fail(run_id, e)
