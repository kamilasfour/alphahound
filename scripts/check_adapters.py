"""Check which adapters are enabled in source_adapters table and when they last ran.

Usage:
    .\.venv\Scripts\python.exe scripts\check_adapters.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
from dotenv import load_dotenv
load_dotenv()

from alphahound.engine.storage import get_conn
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

PT = ZoneInfo("America/Los_Angeles")
now = datetime.now(timezone.utc)

with get_conn() as conn:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT
                sa.source_name,
                sa.source_class,
                sa.tier,
                sa.enabled,
                ir.started_at,
                ir.post_count,
                ir.error
            FROM source_adapters sa
            LEFT JOIN LATERAL (
                SELECT started_at, post_count, error
                FROM ingest_runs
                WHERE adapter_id = sa.source_name
                ORDER BY started_at DESC LIMIT 1
            ) ir ON true
            ORDER BY sa.enabled DESC, sa.tier, sa.source_name;
        """)
        rows = cur.fetchall()

print()
print("=" * 75)
print("  ADAPTER STATUS")
print("  {}".format(now.astimezone(PT).strftime('%a %b %d %I:%M %p PT')))
print("=" * 75)
print()
print("{:<30} {:<22} {:>5} {:>5} {:>8}  {}".format(
    "ADAPTER", "SOURCE CLASS", "TIER", "ON?", "AGO(h)", "LAST POSTS / ERROR"))
print("-" * 75)

for source_name, source_class, tier, enabled, last_run, post_count, error in rows:
    status = "YES" if enabled else "NO"
    if last_run:
        hours_ago = round((now - last_run.replace(tzinfo=timezone.utc)).total_seconds() / 3600, 1)
        ago_str = "{}h".format(hours_ago)
    else:
        ago_str = "never"
    detail = ""
    if error:
        detail = "ERR: {}".format(error[:40])
    elif post_count is not None:
        detail = "{} posts".format(post_count)
    flag = ""
    if not enabled:
        flag = " [DISABLED]"
    if not last_run:
        flag = " [NEVER RUN]"
    print("{:<30} {:<22} {:>5} {:>5} {:>8}  {}{}".format(
        source_name, source_class or "?", tier or "?",
        status, ago_str, detail, flag))

print()
print("=" * 75)
