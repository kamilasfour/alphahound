import sys; sys.path.insert(0, 'src')
from dotenv import load_dotenv; load_dotenv()
from alphahound.engine.storage import get_conn
with get_conn() as conn:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*) FROM raw_posts rp
            WHERE NOT EXISTS (
                SELECT 1 FROM sentiment_scores ss WHERE ss.post_id = rp.post_id
            )
            AND rp.time >= now() - interval '24 hours';
        """)
        print(f"Unscored posts (24h): {cur.fetchone()[0]:,}")

        cur.execute("""
            SELECT COUNT(*) FROM raw_posts rp
            WHERE NOT EXISTS (
                SELECT 1 FROM sentiment_scores ss WHERE ss.post_id = rp.post_id
            );
        """)
        print(f"Unscored posts (all time): {cur.fetchone()[0]:,}")
