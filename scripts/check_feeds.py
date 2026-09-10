import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

from dotenv import load_dotenv
load_dotenv()

from alphahound.engine.storage import get_conn

with get_conn() as conn:
    with conn.cursor() as cur:
        # Check substack feeds
        cur.execute("SELECT slug, display_name, rss_url, enabled FROM substack_feeds ORDER BY slug;")
        feeds = cur.fetchall()

        # Check alpha vantage recent posts
        cur.execute("""
            SELECT adapter_id, COUNT(*) as posts, MAX(time) as latest
            FROM raw_posts
            WHERE source_class = 'analyst_curated'
            GROUP BY adapter_id;
        """)
        av_posts = cur.fetchall()

print()
print("SUBSTACK FEEDS:")
if not feeds:
    print("  NO FEEDS CONFIGURED — table is empty!")
else:
    for slug, name, url, enabled in feeds:
        print(f"  {'ON ' if enabled else 'OFF'} {slug:<30} {name}")

print()
print("ANALYST_CURATED POSTS BY ADAPTER:")
if not av_posts:
    print("  None")
for adapter, count, latest in av_posts:
    print(f"  {adapter:<40} {count:>6} posts  latest={latest}")
print()
