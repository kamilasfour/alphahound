"""
AlphaHound Smart Scoring Task
Replaces the fixed-cap score-new command.

Logic:
    - Check current backlog size
    - If backlog > CATCHUP_THRESHOLD: run until fully clear (no cap)
    - If backlog <= CATCHUP_THRESHOLD: run normal burst (cap=NORMAL_CAP)

This prevents the backlog from growing while not hogging CPU when caught up.

Usage:
    .\.venv\Scripts\python.exe scripts\score_smart.py

Scheduled: AlphaHound-Score every 15 min
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
from dotenv import load_dotenv
load_dotenv()

from alphahound.engine.storage import get_conn
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import subprocess

PT = ZoneInfo("America/Los_Angeles")
now = datetime.now(timezone.utc)

CATCHUP_THRESHOLD = 3000   # if backlog > 3k, run larger burst
NORMAL_CAP        = 2000   # normal burst size
CATCHUP_CAP       = 5000   # max even in catchup mode — never run unbounded
PYTHON = r"C:\alphahound_project\.venv\Scripts\python.exe"
ALPHA  = r"C:\alphahound_project\.venv\Scripts\alphahound.exe"

def get_backlog():
    """Fast backlog estimate using simple count diff — no correlated subquery."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    (SELECT COUNT(*) FROM raw_posts WHERE time >= now() - interval '24 hours') -
                    (SELECT COUNT(*) FROM sentiment_scores WHERE time >= now() - interval '24 hours')
                    AS backlog;
            """)
            return max(0, cur.fetchone()[0] or 0)

def delete_watermarks():
    """Ensure watermarks never block scoring."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM scoring_watermark;")
        conn.commit()

if __name__ == "__main__":
    # Always delete watermarks first — they cause the backlog to hide
    delete_watermarks()

    backlog = get_backlog()
    pt_time = now.astimezone(PT).strftime("%I:%M %p PT")

    if backlog > CATCHUP_THRESHOLD:
        print("[{}] Backlog {:,} > {:,} threshold — CATCHUP MODE: scoring up to {:,}".format(
            pt_time, backlog, CATCHUP_THRESHOLD, CATCHUP_CAP))
        cmd = [ALPHA, "signals", "score-new", "--max-posts", str(CATCHUP_CAP)]
    else:
        print("[{}] Backlog {:,} — normal burst: scoring up to {:,}".format(
            pt_time, backlog, NORMAL_CAP))
        cmd = [ALPHA, "signals", "score-new", "--max-posts", str(NORMAL_CAP)]

    result = subprocess.run(cmd, cwd=r"C:\alphahound_project")

    # Report final backlog
    final = get_backlog()
    print("[{}] Done. Backlog: {:,} → {:,}".format(pt_time, backlog, final))
    sys.exit(result.returncode)
