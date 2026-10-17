"""No-API tests. Run from the repo root:  .venv/bin/python -m unittest discover -s harness/tests -t ."""
import asyncio
import os
import shutil
import tempfile
import unittest
from pathlib import Path

os.environ.pop("ANTHROPIC_API_KEY", None)
os.environ["RUN_ACCESS_CODE"] = "right-code"

from fastapi.testclient import TestClient  # noqa: E402

from harness import app as app_mod, config, engine, gates, runs  # noqa: E402

TEMPLATE = """# Auditor decisions

| Risk | Title | Rating | Decision | Comment |
|---|---|---|---|---|
| R-01 | First | L2 x I4 = 8 High |  |  |
| R-02 | Second | L3 x I3 = 9 High |  |  |
"""


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._old = config.RUNS_DIR
        config.RUNS_DIR = self.tmp / "runs"
        config.RUNS_DIR.mkdir()

    def tearDown(self):
        config.RUNS_DIR = self._old
        shutil.rmtree(self.tmp, ignore_errors=True)


class WebTests(Base):
    def setUp(self):
        super().setUp()
        self.client = TestClient(app_mod.app)

    def test_page_and_health(self):
        self.assertEqual(self.client.get("/healthz").json(), {"ok": True})
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Completed run", r.text)

    def test_completed_run_renders_all_documents_without_api(self):
        docs = self.client.get("/api/completed").json()["docs"]
        self.assertEqual([d["key"] for d in docs], [k for k, _, _ in config.DOCS])
        for d in docs:
            self.assertGreater(len(d["html"]), 200, d["key"])
            self.assertNotIn("<!--", d["html"])
        review = next(d for d in docs if d["key"] == "review")["html"]
        self.assertIn("Prarthana Patel", review)

    def test_wrong_or_missing_access_code_is_rejected(self):
        self.assertEqual(self.client.post("/api/runs", headers={"X-Access-Code": "nope"}).status_code, 403)
        self.assertEqual(self.client.post("/api/runs").status_code, 403)
        self.assertEqual(runs.list_runs(), [])  # nothing was created

    def test_runs_disabled_without_server_code(self):
        os.environ.pop("RUN_ACCESS_CODE")
        try:
            self.assertEqual(self.client.post("/api/runs", headers={"X-Access-Code": "x"}).status_code, 503)
        finally:
            os.environ["RUN_ACCESS_CODE"] = "right-code"

    def test_right_code_but_no_api_key_does_not_start(self):
        r = self.client.post("/api/runs", headers={"X-Access-Code": "right-code"})
        self.assertEqual(r.status_code, 503)
        self.assertEqual(runs.list_runs(), [])

    def test_gate_endpoints_need_the_code(self):
        self.assertEqual(self.client.post("/api/runs/x/gate1", json={"reviewer": "a", "decisions": []}).status_code, 403)
        self.assertEqual(self.client.post("/api/runs/x/team").status_code, 403)
        self.assertEqual(self.client.post("/api/runs/x/gate2", json={"auditor": "a", "decision": "returned"}).status_code, 403)

    def test_api_config_never_exposes_the_key(self):
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-secret-secret-secret"
        try:
            self.assertNotIn("secret", self.client.get("/api/config").text)
            self.assertEqual(config.redact("x sk-ant-secret-secret-secret y"), "x [redacted] y")
        finally:
            os.environ.pop("ANTHROPIC_API_KEY")


class RunCopyTests(Base):
    def test_prepare_isolates_and_resets(self):
        before = (config.REPO_ROOT / "outputs" / "review.md").read_text()
        dest = config.RUNS_DIR / "t1"
        runs.prepare(dest)
        self.assertEqual(list((dest / "outputs").iterdir()), [])
        self.assertTrue((dest / "CLAUDE.md").exists() and (dest / ".claude" / "agents" / "planner.md").exists())
        self.assertTrue((dest / ".claude" / "skills" / "audit-program" / "build_pack.py").exists())
        # every committed file is in the copy, scripts included; only outputs/ starts empty
        self.assertEqual(runs.missing_from_copy(dest), [])
        for f in engine.REQUIRED_SCRIPTS:
            self.assertTrue((dest / f).is_file(), f)
        self.assertEqual(sorted(p.name for p in (dest / "scripts").iterdir()),
                         sorted(p.name for p in (config.REPO_ROOT / "scripts").iterdir() if p.name != "__pycache__"))
        self.assertTrue((dest / ".venv" / "bin" / "python").exists())
        self.assertFalse((dest / "harness").exists() or (dest / ".git").exists())
        self.assertEqual((dest / ".claude" / "settings.json").read_text().strip(), "{}")
        self.assertEqual((config.REPO_ROOT / "outputs" / "review.md").read_text(), before)  # committed outputs untouched
        self.assertIn("CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS", (config.REPO_ROOT / ".claude" / "settings.json").read_text())

    def test_one_run_at_a_time_and_restart_cleanup(self):
        rid = runs.create()
        self.assertEqual(runs.active_run()["id"], rid)
        runs.mark_interrupted()
        self.assertEqual(runs.load_state(rid)["status"], "failed")
        self.assertIsNone(runs.active_run())

    def test_events_are_redacted(self):
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-abcdefghijklmnop"
        try:
            rid = runs.create()
            runs.emit(rid, "text", "key is sk-ant-abcdefghijklmnop")
            self.assertEqual(runs.events(rid)[-1]["text"], "key is [redacted]")
        finally:
            os.environ.pop("ANTHROPIC_API_KEY")


class GateTests(Base):
    def test_decisions_written_and_validated(self):
        f = self.tmp / "auditor-comments.md"
        f.write_text(TEMPLATE)
        with self.assertRaises(gates.GateError):  # partial set refused
            gates.write_decisions(f, "A. Auditor", [{"id": "R-01", "decision": "Approve"}])
        with self.assertRaises(gates.GateError):  # Amend without a score
            gates.write_decisions(f, "A. Auditor", [{"id": "R-01", "decision": "Amend", "comment": "x"}, {"id": "R-02", "decision": "Approve"}])
        gates.write_decisions(f, "A. Auditor", [
            {"id": "R-01", "decision": "Amend", "likelihood": 3, "comment": "multi\nline | pipe"},
            {"id": "R-02", "decision": "Reject", "comment": "Out of scope."}], today="2026-01-02")
        rows = gates.read_risks(f)
        self.assertEqual(rows[0]["decision"], "Amend")
        self.assertEqual(rows[0]["comment"], "Reviewer: A. Auditor, 2026-01-02. L=3. multi line / pipe")
        self.assertEqual(rows[1]["decision"], "Reject")

    def test_signoff_block(self):
        f = self.tmp / "review.md"
        shutil.copy(config.REPO_ROOT / "outputs" / "review.md", f)
        gates.write_signoff(f, "Pat Auditor", "returned", "Needs rework", today="2026-01-02")
        text = f.read_text()
        self.assertIn("- [ ] Signed off", text)
        self.assertIn("- [x] Returned", text)
        self.assertIn("Auditor: Pat Auditor   Date: 2026-01-02   Comment: Needs rework", text)
        gates.write_signoff(f, "Pat Auditor", "signed off", "ok", today="2026-01-03")
        self.assertIn("- [x] Signed off", f.read_text())
        f.write_text(f.read_text().replace("## Verdict: READY FOR SIGN-OFF", "## Verdict: BLOCKED"))
        with self.assertRaises(gates.GateError):
            gates.write_signoff(f, "Pat Auditor", "signed off", "ok")


class RelayTests(Base):
    def test_parsing(self):
        msgs = engine.parse_messages("thinking\nSEND TO challenger: PACK READY v1\nmore\nSEND TO QA-Reviewer: PACK READY v1\n")
        self.assertEqual(msgs, [("challenger", "PACK READY v1\nmore"), ("qa-reviewer", "PACK READY v1")])
        for n in engine.TEAM:
            spec = engine.parse_agent_file(config.REPO_ROOT / ".claude" / "agents" / f"{n}.md")
            self.assertIn("SendMessage", spec["tools"])
            self.assertTrue(spec["body"].strip())
        self.assertEqual(engine.parse_agent_file(config.REPO_ROOT / ".claude" / "agents" / "planner.md")["skills"], ["audit-program"])

    def test_relay_runs_a_scripted_team_to_three_done_messages(self):
        rid = runs.create()
        d = runs.run_dir(rid)
        script = {
            "planner": ["SEND TO challenger: PACK READY v1: 4 risks\nSEND TO qa-reviewer: PACK READY v1: 4 risks",
                        "SEND TO challenger: RESPONSE #1: accepted\nSEND TO qa-reviewer: PACK READY v2\nSEND TO challenger: PACK READY v2",
                        "SEND TO lead: PLANNER DONE v2"],
            "challenger": ["SEND TO planner: CHALLENGE #1: weak sample", "CHALLENGER DONE not yet", "SEND TO lead: CHALLENGER DONE"],
            "qa-reviewer": ["SEND TO planner: QA v1: PASS", "SEND TO planner: QA v2: PASS", "WRITE;SEND TO lead: QA DONE v2: READY FOR SIGN-OFF"],
        }
        seen = {n: [] for n in script}

        class Fake:
            def __init__(self, opts):
                self.name = None  # set by the factory
                self.opts = opts
                self.pending = None

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def query(self, prompt):
                self.pending = prompt

            async def receive_response(self):
                from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock
                name = self.name
                seen[name].append(self.pending)
                reply = script[name][len(seen[name]) - 1]
                if reply.startswith("WRITE;"):
                    reply = reply[6:]
                    (d / "outputs").mkdir(exist_ok=True)
                    (d / "outputs" / "review.md").write_text("## Verdict: READY FOR SIGN-OFF\n")
                    (d / "outputs" / "audit-plan.json").write_text("{}")
                    (d / "outputs" / "challenges.md").write_text("x")
                yield AssistantMessage(content=[TextBlock(text=reply)], model="fake")
                yield ResultMessage(subtype="success", duration_ms=1, duration_api_ms=1, is_error=False, num_turns=1,
                                    session_id="s", total_cost_usd=0.01)

        # name each fake from the system prompt it was built with (the agent file body)
        bodies = {n: engine.parse_agent_file(config.REPO_ROOT / ".claude" / "agents" / f"{n}.md")["body"][:200] for n in script}

        def factory(opts):
            f = Fake(opts)
            sp = opts.system_prompt["append"]
            f.name = next(n for n, b in bodies.items() if sp.startswith(b))
            return f

        old_factory, old_py = engine.client_factory, engine._py
        engine.client_factory = factory
        engine._py = lambda *a, **k: (0, "GATE PASS: test")
        try:
            asyncio.run(engine.run_team(rid))
        finally:
            engine.client_factory, engine._py = old_factory, old_py
        st = runs.load_state(rid)
        self.assertEqual((st["stage"], st["status"]), ("gate2", "waiting"), st)
        self.assertTrue(seen["planner"][0].startswith("FROM lead: The gate check passed"))
        self.assertIn("FROM planner:\nPACK READY v1", seen["challenger"][0])  # relayed between sessions
        self.assertIn("FROM challenger:\nCHALLENGE #1", seen["planner"][1])
        self.assertAlmostEqual(st["cost_usd"], 0.09, places=2)

    def test_agent_options_use_the_agent_files(self):
        rid = runs.create()
        d = runs.run_dir(rid)
        planner = engine._agent_options(d, "planner", engine.RELAY_NOTE)
        self.assertNotIn("SendMessage", planner.tools)
        self.assertIn("Skill", planner.tools)  # planner declares the audit-program skill
        self.assertIn("SEND TO", planner.system_prompt["append"])
        self.assertEqual(planner.setting_sources, ["project"])
        self.assertEqual(planner.permission_mode, "bypassPermissions")
        self.assertEqual(planner.model, config.MODEL)
        qa = engine._agent_options(d, "qa-reviewer", engine.RELAY_NOTE)
        self.assertEqual(sorted(qa.tools), ["Bash", "Read", "Write"])  # as in qa-reviewer.md, minus SendMessage


class AnalystWaitTests(Base):
    """The failed live run: the lead started the analysts in the background and the engine checked 6 s later."""

    def _factory(self, d, log, delays, writes):
        class Slow:
            def __init__(self, name):
                self.name = name

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def query(self, prompt):
                pass

            async def receive_response(self):
                from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock
                log.append(("start", self.name))
                await asyncio.sleep(delays[self.name])  # still working: no result yet
                for f in writes[self.name]:
                    (d / "outputs").mkdir(exist_ok=True)
                    (d / "outputs" / f).write_text("{}")
                log.append(("finish", self.name))
                yield AssistantMessage(content=[TextBlock(text="report")], model="fake")
                yield ResultMessage(subtype="success", duration_ms=1, duration_api_ms=1, is_error=False, num_turns=1,
                                    session_id="s", total_cost_usd=0.01)

        bodies = {n: engine.parse_agent_file(config.REPO_ROOT / ".claude" / "agents" / f"{n}.md")["body"][:200] for n in delays}

        def factory(opts):
            return Slow(next(n for n, b in bodies.items() if opts.system_prompt["append"].startswith(b)))
        return factory

    def test_engine_waits_for_both_analysts_and_runs_them_concurrently(self):
        rid = runs.create()
        d = runs.run_dir(rid)
        log = []
        writes = {"spend-analyst": ["analytics.json", "analytics-selfcheck.json"], "findings-analyst": ["history.json"]}
        old = engine.client_factory
        engine.client_factory = self._factory(d, log, {"spend-analyst": 0.4, "findings-analyst": 0.1}, writes)
        try:
            asyncio.run(engine.run_analysts(rid, d))  # returns only once the slow one has finished
        finally:
            engine.client_factory = old
        self.assertEqual(sorted(log[:2]), [("start", "findings-analyst"), ("start", "spend-analyst")])  # concurrent
        self.assertEqual(log[-1], ("finish", "spend-analyst"))  # the slower one finished last, before we returned
        for f in ("analytics.json", "analytics-selfcheck.json", "history.json"):
            self.assertTrue((d / "outputs" / f).exists())
        self.assertAlmostEqual(runs.load_state(rid)["cost_usd"], 0.02)

    def test_missing_output_after_both_finish_is_an_error(self):
        rid = runs.create()
        d = runs.run_dir(rid)
        old = engine.client_factory
        engine.client_factory = self._factory(d, [], {"spend-analyst": 0.0, "findings-analyst": 0.0},
                                              {"spend-analyst": ["analytics.json"], "findings-analyst": []})
        try:
            with self.assertRaises(engine.EngineError):
                asyncio.run(engine.run_analysts(rid, d))
        finally:
            engine.client_factory = old

    def test_one_failing_analyst_fails_the_stage(self):
        rid = runs.create()
        d = runs.run_dir(rid)
        old = engine.client_factory

        def boom(opts):
            raise RuntimeError("cli crashed")
        engine.client_factory = boom
        try:
            with self.assertRaises(RuntimeError):
                asyncio.run(engine.run_analysts(rid, d))
        finally:
            engine.client_factory = old

    def test_sessions_cannot_background_work(self):
        deny = asyncio.run(engine._no_background({"tool_name": "Agent", "tool_input": {}}, "id", None))
        self.assertEqual(deny["hookSpecificOutput"]["permissionDecision"], "deny")
        deny = asyncio.run(engine._no_background({"tool_name": "Bash", "tool_input": {"command": "x", "run_in_background": True}}, "id", None))
        self.assertEqual(deny["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertEqual(asyncio.run(engine._no_background({"tool_name": "Bash", "tool_input": {"command": "ls"}}, "id", None)), {})
        for n in ("spend-analyst", "findings-analyst", "risk-assessor"):
            rid = runs.create()
            o = engine._agent_options(runs.run_dir(rid), n, engine.STANDALONE_NOTE)
            self.assertNotIn("Agent", o.tools)
            self.assertIn("foreground", o.system_prompt["append"])
            self.assertIn("PreToolUse", o.hooks)
        self.assertIn("Skill", engine._agent_options(d := runs.run_dir(runs.create()), "risk-assessor", "").tools)


class PreflightTests(Base):
    def test_run_copy_python_has_requirements_and_poppler_works(self):
        rid = runs.create()
        d = runs.run_dir(rid)
        engine._preflight(d)  # raises if .venv/bin/python, pandas/openpyxl or poppler are missing
        import subprocess
        out = subprocess.run([str(d / ".venv" / "bin" / "python"), "-c", "import sys; print(sys.version_info[0])"],
                             capture_output=True, text=True, cwd=d)
        self.assertEqual(out.stdout.strip(), "3")
        rc, _ = engine._py(d, ".claude/skills/extract-rules/verify_quotes.py", "--inventory")  # uses pdftotext on data/
        self.assertEqual(rc, 0)

    def test_preflight_fails_fast_on_a_missing_script(self):
        for victim in engine.REQUIRED_SCRIPTS + ["scripts/clean.py"]:  # a required script, and any other repo file
            rid = runs.create()
            d = runs.run_dir(rid)
            (d / victim).unlink()
            with self.assertRaises(engine.EngineError) as cm:
                engine._preflight(d)
            self.assertIn(Path(victim).name, str(cm.exception))

    def test_preflight_names_the_missing_piece(self):
        rid = runs.create()
        d = runs.run_dir(rid)
        (d / ".venv" / "bin" / "python").unlink()
        with self.assertRaises(engine.EngineError) as cm:
            engine._preflight(d)
        self.assertIn(".venv/bin/python", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
