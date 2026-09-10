"""Create health_checks table if it doesn't exist.

Usage:
    .\.venv\Scripts\python.exe scripts\migrate_health_checks.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
from dotenv import load_dotenv
load_dotenv()

from alphahound.engine.storage import get_conn

with get_conn() as conn:
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS health_checks (
                id           BIGSERIAL PRIMARY KEY,
                generated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                overall_status TEXT NOT NULL,
                items        JSONB NOT NULL,
                UNIQUE (generated_at)
            );

            CREATE INDEX IF NOT EXISTS idx_health_checks_generated_at
                ON health_checks (generated_at DESC);
        """)
    conn.commit()

print("health_checks table ready.")
