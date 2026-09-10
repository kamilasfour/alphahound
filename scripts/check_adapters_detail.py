import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
from dotenv import load_dotenv
load_dotenv()

from alphahound.engine.storage import get_conn

with get_conn() as conn:
    with conn.cursor() as cur:

        # Check adapter status
        cur.execute("""
            SELECT adapter_id, enabled,
                   ir.started_at, ir.error, ir.posts_fetched
            FROM source_adapters sa
            LEFT JOIN LATERAL (
                SELECT started_at, error, posts_fetched
                FROM ingest_runs WHERE adapter_id = sa.adapter_id
                ORDER BY started_at DESC LIMIT 1
            ) ir ON true
            ORDER BY enabled DESC, adapter_id;
        """)
        adapters = cur.fetchall()

        # Force disable EDGAR
        cur.execute("UPDATE source_adapters SET enabled=false WHERE adapter_id='stocks.edgar';")

        # Check quiver API
        cur.execute("""
            SELECT COUNT(*), MAX(time) FROM raw_posts
            WHERE adapter_id='stocks.quiver'
            AND time >= now() - interval '7 days';
        """)
        quiver = cur.fetchone()

        # Check stocktwits
        cur.execute("""
            SELECT COUNT(*), MAX(time) FROM raw_posts
            WHERE adapter_id='stocks.stocktwits'
            AND time >= now() - interval '24 hours';
        """)
        st = cur.fetchone()

    conn.commit()

print("\nADAPTER STATUS:")
for adapter_id, enabled, last_run, error, fetched in adapters:
    status = "ON " if enabled else "OFF"
    last = last_run.strftime('%I:%M %p') if last_run else "never"
    err = " ERR: {}".format(error[:40]) if error else ""
    print("  [{}] {:35s} last={} fetched={}{}" .format(
        status, adapter_id, last, fetched or 0, err))

print("\nQUIVER (congressional trades 7d): {} posts, latest={}".format(
    quiver[0], quiver[1].strftime('%Y-%m-%d %I:%M %p') if quiver[1] else "never"))

print("STOCKTWITS (last 24h): {} posts, latest={}".format(
    st[0], st[1].strftime('%I:%M %p') if st[1] else "never"))

print("\nEDGAR disabled.")
