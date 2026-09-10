import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
from dotenv import load_dotenv
load_dotenv()

from alphahound.engine.storage import get_conn
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
PT = ZoneInfo("America/Los_Angeles")
now = datetime.now(timezone.utc)

with get_conn() as conn:
    with conn.cursor() as cur:

        # Every adapter - last run, posts fetched, posts wrote, error
        cur.execute("""
            SELECT
                sa.adapter_id,
                sa.enabled,
                sa.source_class,
                sa.tier,
                ir.started_at,
                ir.posts_fetched,
                ir.posts_written,
                ir.error
            FROM source_adapters sa
            LEFT JOIN LATERAL (
                SELECT started_at, posts_fetched, posts_written, error
                FROM ingest_runs
                WHERE adapter_id = sa.adapter_id
                ORDER BY started_at DESC LIMIT 1
            ) ir ON true
            ORDER BY sa.enabled DESC, sa.tier, sa.adapter_id;
        """)
        adapters = cur.fetchall()

        # Raw posts written per adapter last 24h
        cur.execute("""
            SELECT adapter_id, COUNT(*) as posts
            FROM raw_posts
            WHERE time >= now() - interval '24 hours'
            GROUP BY adapter_id;
        """)
        posts_24h = {r[0]: r[1] for r in cur.fetchall()}

        # Options flow last 24h
        cur.execute("SELECT COUNT(*) FROM options_flow WHERE time >= now() - interval '24 hours';")
        options_count = cur.fetchone()[0]

        # Congressional trades last 7d
        cur.execute("SELECT COUNT(*) FROM raw_posts WHERE adapter_id='stocks.quiver' AND time >= now() - interval '7 days';")
        quiver_posts = cur.fetchone()[0]

        # Price daily latest
        cur.execute("SELECT COUNT(DISTINCT entity_id), MAX(date) FROM price_daily;")
        price_daily = cur.fetchone()

        # Price snapshots latest
        cur.execute("SELECT COUNT(DISTINCT entity_id), MAX(time) FROM price_snapshots;")
        price_snaps = cur.fetchone()

        # Kalshi
        cur.execute("SELECT COUNT(*) FROM raw_posts WHERE adapter_id='stocks.kalshi' AND time >= now() - interval '7 days';")
        kalshi_posts = cur.fetchone()[0]

print()
print("=" * 75)
print("  FULL SYSTEM AUDIT — {}".format(now.astimezone(PT).strftime('%a %b %d %I:%M %p PT')))
print("=" * 75)

print("\nADAPTERS:")
print("  {:35s} {:4s} {:22s} {:4s} {:>7s} {:>7s}  {}".format(
    "ADAPTER", "ON?", "SOURCE CLASS", "TIER", "FETCH", "WROTE", "STATUS"))
print("  " + "-"*75)

for adapter_id, enabled, source_class, tier, started, fetched, written, error in adapters:
    status = "ON " if enabled else "OFF"
    age = ""
    if started:
        mins = int((now - started.replace(tzinfo=timezone.utc)).total_seconds()/60)
        age = "{}m ago".format(mins)
    posts = posts_24h.get(adapter_id, 0)
    err = ""
    if error:
        err = " ERR: {}".format(error[:30])
    elif not enabled:
        err = " [DISABLED]"
    elif fetched == 0 and started:
        err = " [0 FETCHED]"
    elif written == 0 and fetched and fetched > 0 and source_class not in ('price_data',):
        err = " [0 WROTE - BUG]"

    print("  {:35s} {:4s} {:22s} {:4s} {:>7} {:>7}  {}{}".format(
        adapter_id, status, source_class or "?", tier or "?",
        fetched or 0, written or 0, age, err))

print()
print("DATA AVAILABILITY:")
print("  Options flow (24h):      {:,}".format(options_count))
print("  Congressional (7d):      {:,}".format(quiver_posts))
print("  Price daily bars:        {:,} tickers, latest={}".format(
    price_daily[0], price_daily[1]))
print("  Price snapshots:         {:,} tickers, latest={}".format(
    price_snaps[0],
    price_snaps[1].astimezone(PT).strftime('%I:%M %p PT') if price_snaps[1] else "never"))
print("  Kalshi predictions (7d): {:,}".format(kalshi_posts))

print()
print("PROBLEMS FOUND:")
problems = []
for adapter_id, enabled, source_class, tier, started, fetched, written, error in adapters:
    if not enabled:
        continue
    if error:
        problems.append("❌ {} — ERROR: {}".format(adapter_id, error[:60]))
    elif not started:
        problems.append("❌ {} — NEVER RUN".format(adapter_id))
    elif fetched == 0 and source_class not in ('price_data',):
        mins = int((now - started.replace(tzinfo=timezone.utc)).total_seconds()/60)
        problems.append("⚠️  {} — 0 fetched (last run {}m ago)".format(adapter_id, mins))
    elif written == 0 and fetched and fetched > 0 and source_class not in ('price_data',):
        problems.append("❌ {} — {} fetched but 0 wrote".format(adapter_id, fetched))

if quiver_posts == 0:
    problems.append("❌ stocks.quiver — 0 congressional trades written in 7 days")
if kalshi_posts == 0:
    problems.append("⚠️  stocks.kalshi — 0 prediction market posts in 7 days")

if not problems:
    print("  None — all systems healthy")
for p in problems:
    print("  {}".format(p))

print()
print("=" * 75)
