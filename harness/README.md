# Harness: Part B

A FastAPI app that runs this repo's own `CLAUDE.md`, `.claude/agents` and `.claude/skills` through the Claude Agent SDK (`claude-agent-sdk`, Sonnet, `ANTHROPIC_API_KEY`). The skills and agents are reused unchanged.

- **Completed run:** renders the committed `outputs/` (register, decisions, memo, matrix, program, challenges, review and sign-off). No API calls.
- **New run:** needs `RUN_ACCESS_CODE`. Stages: `/extract-rules`, then spend-analyst and findings-analyst, then risk-assessor, then Gate 1 (decisions form), the register revision, the agent team, and Gate 2 (QA verdict and sign-off form). Every run works in `/data/runs/<id>`, a fresh copy of the repo with `outputs/` emptied; one run at a time.
- **Agent team:** the SDK has no team API, so `engine.run_team` is a relay orchestrator: one SDK session per teammate, built from `.claude/agents/<name>.md` (same tools, minus `SendMessage`), carrying the same PACK READY / CHALLENGE / RESPONSE / QA / DONE messages between them. Native agent teams were not tried, because that needs paid calls.

Environment: `ANTHROPIC_API_KEY`, `RUN_ACCESS_CODE` (both Fly secrets), `HARNESS_MODEL` (default `sonnet`), `HARNESS_MAX_BUDGET_USD` (per session, default 5), `HARNESS_DATA` (default `/data`). The key is never logged or returned; progress text is redacted.

Tests (no API calls): `.venv/bin/python -m unittest discover -s harness/tests -t .`

Deploy (not done yet): `fly launch --no-deploy --copy-config`, `fly volumes create data --size 3`, `fly secrets set ANTHROPIC_API_KEY=... RUN_ACCESS_CODE=...`, `fly deploy`.
