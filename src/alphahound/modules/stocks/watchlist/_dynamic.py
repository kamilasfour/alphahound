"""Dynamic watchlist — top-mentioned tickers from recent raw_posts."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from alphahound.engine.storage import get_conn


def top_mentioned(module_id: str = "stocks", size: int = 20, window_hours: int = 24) -> list[str]:
    since = datetime.now(timezone.utc) - timedelta(hours=window_hours)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT e.canonical_symbol, COUNT(*) AS mentions
                FROM raw_posts r
                JOIN entities e ON e.entity_id = r.entity_id
                WHERE e.module_id = %s
                  AND r.time >= %s
                GROUP BY e.canonical_symbol
                ORDER BY mentions DESC
                LIMIT %s;
                """,
                (module_id, since, size),
            )
            return [row[0] for row in cur.fetchall()]
