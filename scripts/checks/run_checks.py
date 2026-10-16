#!/usr/bin/env python3
"""Run the four QA checks and print one table and a verdict.
    .venv/bin/python scripts/checks/run_checks.py [--root DIR] [--interim]
--interim skips the challenges.md closure test inside check_trace (for runs made while
the challenger is still working). The final run before sign-off never uses it.
Exit code 0 only if all four checks pass."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_numbers, check_quotes, check_samples, check_trace  # noqa: E402
from common import PROJECT  # noqa: E402


def run(root, interim=False):
    return [check_quotes.check(root), check_numbers.check(root), check_trace.check(root, interim=interim),
            check_samples.check(root)]


def render(results, interim=False):
    lines = ["| Check | Result | Problems | Detail |", "|---|---|---|---|"]
    for r in results:
        detail = (r["items"][0] if r["items"] else r["summary"]).replace("|", "/")
        lines.append(f"| {r['name']} | {r['status']} | {len(r['items'])} | {detail} |")
    failed = [r["name"] for r in results if r["status"] == "FAIL"]
    lines += ["", ("VERDICT: ALL CHECKS PASS" if not failed else "VERDICT: FAILED: " + ", ".join(failed))
              + (" (interim run: challenges.md closure not checked)" if interim else "")]
    for r in results:
        if r["items"]:
            lines += ["", f"{r['name']}: {len(r['items'])} problem(s)"] + [f"  - {i}" for i in r["items"][:25]]
            if len(r["items"]) > 25:
                lines.append(f"  ... and {len(r['items']) - 25} more")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", default=str(PROJECT))
    ap.add_argument("--interim", action="store_true")
    a = ap.parse_args(argv)
    results = run(Path(a.root), a.interim)
    print(render(results, a.interim))
    return 1 if any(r["status"] == "FAIL" for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
