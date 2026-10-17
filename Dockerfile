FROM python:3.12-slim

# poppler-utils: pdftotext/pdfinfo for the quote verifiers. util-linux (setpriv) drops root after fixing /data.
# No Node: the claude-agent-sdk wheel bundles the Claude Code CLI.
RUN apt-get update && apt-get install -y --no-install-recommends poppler-utils util-linux \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt harness/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r harness/requirements.txt

# The repo itself: CLAUDE.md, .claude (agents, skills), data, scripts, committed outputs, and the harness.
COPY CLAUDE.md ./
COPY .claude ./.claude
COPY data ./data
COPY scripts ./scripts
COPY outputs ./outputs
COPY harness ./harness

# Claude Code refuses bypassPermissions as root, so the app runs as an unprivileged user.
RUN useradd --create-home --uid 1000 app
COPY harness/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV HARNESS_DATA=/data PORT=8080 PYTHONUNBUFFERED=1
EXPOSE 8080
ENTRYPOINT ["/entrypoint.sh"]
