"""
AlphaHound DB Query Tool
Run any SQL query against the database.

Usage:
    .\.venv\Scripts\python.exe scripts\db.py "SELECT COUNT(*) FROM raw_posts"
    .\.venv\Scripts\python.exe scripts\db.py  (interactive mode)
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
from dotenv import load_dotenv
load_dotenv()

from alphahound.engine.storage import get_conn
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

PT = ZoneInfo("America/Los_Angeles")

def run_query(sql):
    sql = sql.strip()
    if not sql:
        return
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                if cur.description:
                    cols  = [d.name for d in cur.description]
                    rows  = cur.fetchall()
                    # Column widths
                    widths = [len(c) for c in cols]
                    for row in rows:
                        for i, val in enumerate(row):
                            widths[i] = max(widths[i], len(str(val)))
                    # Header
                    header = "  ".join(c.ljust(widths[i]) for i, c in enumerate(cols))
                    print(header)
                    print("-" * len(header))
                    for row in rows:
                        print("  ".join(str(v).ljust(widths[i]) for i, v in enumerate(row)))
                    print("\n{} row{}".format(len(rows), 's' if len(rows) != 1 else ''))
                else:
                    conn.commit()
                    print("OK — {} row{} affected".format(
                        cur.rowcount, 's' if cur.rowcount != 1 else ''))
    except Exception as e:
        print("ERROR:", e)

# Handy shortcuts
SHORTCUTS = {
    "signals":    "SELECT e.canonical_symbol, de.d_value, de.time FROM divergence_events de JOIN entities e ON e.entity_id=de.entity_id WHERE de.time >= now()-interval '4 hours' ORDER BY de.d_value DESC",
    "pipeline":   "SELECT step, status, duration_ms/1000 as secs, rows_affected, started_at FROM pipeline_runs ORDER BY started_at DESC LIMIT 15",
    "backlog":    "SELECT source_class, COUNT(*) as unscored FROM raw_posts rp WHERE source_class IN ('news_wire','retail_social','analyst_curated') AND NOT EXISTS (SELECT 1 FROM sentiment_scores ss WHERE ss.entity_id=rp.entity_id AND ss.source_class=rp.source_class AND ss.time=rp.time) GROUP BY source_class",
    "adapters":   "SELECT adapter_id, enabled FROM source_adapters ORDER BY enabled DESC, adapter_id",
    "ingest":     "SELECT DISTINCT ON (adapter_id) adapter_id, started_at, posts_fetched, posts_written, error FROM ingest_runs ORDER BY adapter_id, started_at DESC",
    "positions":  "SELECT e.canonical_symbol, tl.side, tl.size, tl.alpaca_status FROM trade_log tl JOIN entities e ON e.entity_id=tl.entity_id WHERE tl.alpaca_order_id IS NOT NULL AND tl.closed_at IS NULL",
    "options":    "SELECT e.canonical_symbol, COUNT(*) as contracts, MAX(time) as latest FROM options_flow of2 JOIN entities e ON e.entity_id=of2.entity_id WHERE of2.time >= now()-interval '4 hours' GROUP BY e.canonical_symbol ORDER BY contracts DESC LIMIT 15",
    "congress":   "SELECT e.canonical_symbol, rp.raw->>'Representative' as rep, rp.raw->>'Transaction' as txn, rp.time FROM raw_posts rp JOIN entities e ON e.entity_id=rp.entity_id WHERE rp.adapter_id='stocks.quiver' AND rp.time >= now()-interval '24 hours' ORDER BY rp.time DESC LIMIT 10",
    "posts":      "SELECT source_class, COUNT(*) as posts FROM raw_posts WHERE time >= now()-interval '1 hour' GROUP BY source_class ORDER BY posts DESC",
    "health":     "SELECT generated_at, overall_status FROM health_checks ORDER BY generated_at DESC LIMIT 5",
    "hitrate":    "SELECT window_days, hit_rate_pct, total_signals, computed_at FROM hit_rate ORDER BY computed_at DESC LIMIT 5",
    "entities":   "SELECT COUNT(*) as total, module_id, kind FROM entities GROUP BY module_id, kind ORDER BY total DESC",
    "help":       None,
}

def show_help():
    print("\nShortcuts:")
    for k in SHORTCUTS:
        if k != "help":
            print("  {:12s}  {}".format(k, SHORTCUTS[k][:60] + "..."))
    print("\nOr type any SQL query.")
    print("Type 'exit' or Ctrl-C to quit.\n")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Single query from command line
        query = " ".join(sys.argv[1:])
        if query in SHORTCUTS:
            run_query(SHORTCUTS[query])
        else:
            run_query(query)
    else:
        # Interactive mode
        print()
        print("AlphaHound DB  |  type 'help' for shortcuts, 'exit' to quit")
        print("=" * 55)
        while True:
            try:
                sql = input("\nSQL> ").strip()
                if not sql:
                    continue
                if sql.lower() in ("exit", "quit", "q"):
                    break
                if sql.lower() == "help":
                    show_help()
                    continue
                if sql in SHORTCUTS:
                    q = SHORTCUTS[sql]
                    print("→", q[:80])
                    run_query(q)
                else:
                    run_query(sql)
            except KeyboardInterrupt:
                print()
                break
            except EOFError:
                break
