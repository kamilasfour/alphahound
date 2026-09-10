import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
from dotenv import load_dotenv
load_dotenv()
from alphahound.engine.storage import get_conn

with get_conn() as conn:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'source_adapters'
            ORDER BY ordinal_position;
        """)
        cols = [r[0] for r in cur.fetchall()]
        print("source_adapters columns:", cols)

        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'ingest_runs'
            ORDER BY ordinal_position;
        """)
        cols2 = [r[0] for r in cur.fetchall()]
        print("ingest_runs columns:", cols2)

        # Show a sample row from source_adapters
        cur.execute("SELECT * FROM source_adapters LIMIT 3;")
        rows = cur.fetchall()
        print("sample rows:", rows)
