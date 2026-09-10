"""Pipeline step runner — wraps a CLI command with DB tracking.

Called by ingest_all.ps1 for each pipeline step:

    python run_pipeline_step.py <step_name> <alphahound command args...>

Example:
    python run_pipeline_step.py divergence-scan signals divergence-scan
    python run_pipeline_step.py score-new signals score-new --max-posts 300

Writes a row to pipeline_runs with:
    - started_at / finished_at
    - status: ok | error
    - duration_ms
    - rows_affected: parsed from last line of stdout (e.g. "✅ Wrote 12 alerts.")
    - error: first 2000 chars of stderr on failure
"""
from __future__ import annotations

import re
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Bootstrap .env before importing storage
from dotenv import load_dotenv
here = Path(__file__).resolve().parent.parent
for candidate in [here / ".env", here.parent / ".env"]:
    if candidate.is_file():
        load_dotenv(candidate)
        break

from alphahound.engine.storage import start_pipeline_step, finish_pipeline_step  # noqa: E402


def _parse_rows(output: str) -> int | None:
    """Extract a number from lines like '✅ Wrote 12 alerts.' or '14 matches written.'"""
    for pattern in [
        r"wrote\s+(\d+)",
        r"(\d+)\s+(?:alerts?|matches?|scores?|signals?|rows?)\s+written",
        r"✅\s+\w[^:]*:\s+(\d+)",
        r"complete[:\s]+(\d+)",
    ]:
        m = re.search(pattern, output, re.IGNORECASE)
        if m:
            return int(m.group(1))
    return None


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: run_pipeline_step.py <step_name> <cli args...>", file=sys.stderr)
        return 1

    step_name = sys.argv[1]
    cmd_args  = ["alphahound"] + sys.argv[2:]
    host      = socket.gethostname()

    run_id = start_pipeline_step(step_name, host=host)

    try:
        result = subprocess.run(
            cmd_args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        output   = (result.stdout or "") + (result.stderr or "")
        rows     = _parse_rows(result.stdout or "")
        success  = result.returncode == 0

        # Print output so PS1 can still log it
        print(output, end="")

        finish_pipeline_step(
            run_id,
            status       = "ok" if success else "error",
            rows_affected= rows,
            error        = result.stderr[:2000] if not success else None,
        )
        return result.returncode

    except Exception as exc:
        finish_pipeline_step(run_id, status="error", error=str(exc)[:2000])
        print(f"FATAL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
