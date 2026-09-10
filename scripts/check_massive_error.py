import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
from dotenv import load_dotenv
load_dotenv()

from alphahound.engine.storage import get_conn

with get_conn() as conn:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT error FROM pipeline_runs
            WHERE step = 'massive-history' AND status = 'error'
            ORDER BY started_at DESC LIMIT 1;
        """)
        row = cur.fetchone()

if row and row[0]:
    print(row[0])
else:
    print("No error found.")
