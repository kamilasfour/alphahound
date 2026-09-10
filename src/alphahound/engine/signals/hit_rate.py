"""Hit rate calculator — tracks signal accuracy over rolling windows.

Reads trade_log entries (venue='signal') and resolves outcomes by comparing
entry price against price at resolve_by date from the outlook in notes JSONB.

Outcome resolution logic:
    - side='buy'   → correct if price at resolve_by > entry price by >= MIN_PRICE_MOVE_PCT
    - side='short' → correct if price at resolve_by < entry price by >= MIN_PRICE_MOVE_PCT
    - Uses price_snapshots for resolution prices
    - Writes pnl back to trade_log when resolved
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from alphahound.engine.storage import get_conn

log = logging.getLogger(__name__)

OUTCOME_WINDOW_DAYS = 5
MIN_PRICE_MOVE_PCT  = 0.5
ROLLING_WINDOWS     = [7, 30, 90]


def compute_hit_rate(module_id: str = "stocks") -> dict:
    """Compute hit rate for all rolling windows. Returns summary dict."""
    now = datetime.now(timezone.utc)

    resolved = _resolve_trade_log_outcomes()
    log.info("Hit rate: resolved %d trade_log outcomes", resolved)

    results = {}
    for window_days in ROLLING_WINDOWS:
        since = now - timedelta(days=window_days)
        stats = _compute_window(module_id, since, now)
        if stats["total_signals"] > 0:
            _write_hit_rate(stats, window_days, now)
            results[f"{window_days}d"] = stats
            log.info(
                "Hit rate (%dd): %d/%d = %.1f%%",
                window_days,
                stats["correct_signals"],
                stats["total_signals"],
                stats["hit_rate_pct"],
            )
        else:
            log.info("Hit rate (%dd): no resolved signals in window", window_days)

    return results


def get_current_hit_rate() -> dict | None:
    """Get most recent 30d hit rate stats."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT window_days, hit_rate_pct, total_signals,
                       correct_signals, expectancy, by_ticker, computed_at
                FROM hit_rate
                WHERE window_days = 30
                ORDER BY computed_at DESC
                LIMIT 1;
                """
            )
            row = cur.fetchone()
    if not row:
        return None
    return {
        "window_days":     row[0],
        "hit_rate_pct":    row[1],
        "total_signals":   row[2],
        "correct_signals": row[3],
        "expectancy":      row[4],
        "by_ticker":       row[5],
        "computed_at":     row[6],
    }


# ---------------------------------------------------------------------------
# Outcome resolution — reads trade_log
# ---------------------------------------------------------------------------

def _resolve_trade_log_outcomes() -> int:
    """Resolve pending trade_log signals where resolve_by has passed."""
    now = datetime.now(timezone.utc)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT trade_id, entity_id, side, price,
                       notes::jsonb->>'resolve_by'         AS resolve_by,
                       (notes::jsonb->>'stop_price')::float AS stop_price
                FROM trade_log
                WHERE venue = 'signal'
                  AND pnl IS NULL
                  AND price IS NOT NULL
                  AND notes::jsonb->>'resolve_by' IS NOT NULL;
                """
            )
            cols = [d.name for d in cur.description]
            pending = [dict(zip(cols, row)) for row in cur.fetchall()]

    resolved = 0
    for row in pending:
        try:
            resolve_by = datetime.fromisoformat(row["resolve_by"]).replace(tzinfo=timezone.utc)
        except Exception:
            continue

        # Not ready yet
        if now < resolve_by:
            continue

        outcome = _check_price_outcome(
            entity_id   = row["entity_id"],
            entry_price = float(row["price"]),
            side        = row["side"],
            resolve_by  = resolve_by,
        )
        if outcome is not None:
            _update_trade_log_outcome(row["trade_id"], outcome)
            resolved += 1

    return resolved


def _check_price_outcome(
    entity_id: str,
    entry_price: float,
    side: str,
    resolve_by: datetime,
) -> dict | None:
    """Look up price at resolve_by and determine if signal was correct."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            # Price at or after resolve_by date
            cur.execute(
                """
                SELECT price FROM price_snapshots
                WHERE entity_id = %s AND time >= %s
                ORDER BY time ASC LIMIT 1;
                """,
                (entity_id, resolve_by),
            )
            row = cur.fetchone()

    if not row or not row[0] or entry_price == 0:
        return None

    exit_price = float(row[0])
    pct_change = ((exit_price - entry_price) / entry_price) * 100

    if side == "buy":
        correct = pct_change > MIN_PRICE_MOVE_PCT
    elif side == "short":
        correct = pct_change < -MIN_PRICE_MOVE_PCT
    else:
        return None

    pnl_pct = pct_change if side == "buy" else -pct_change

    return {
        "pnl":     round(pnl_pct, 3),
        "correct": correct,
    }


def _update_trade_log_outcome(trade_id: str, outcome: dict) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE trade_log
                SET pnl = %s
                WHERE trade_id = %s;
                """,
                (outcome["pnl"], trade_id),
            )
        conn.commit()


# ---------------------------------------------------------------------------
# Hit rate computation
# ---------------------------------------------------------------------------

def _compute_window(module_id: str, since: datetime, now: datetime) -> dict:
    """Compute hit rate stats from resolved trade_log entries."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    tl.side,
                    tl.pnl,
                    e.canonical_symbol
                FROM trade_log tl
                JOIN entities e ON e.entity_id = tl.entity_id
                WHERE tl.venue = 'signal'
                  AND tl.pnl IS NOT NULL
                  AND tl.time >= %s
                  AND tl.time <= %s
                  AND e.module_id = %s
                ORDER BY tl.time DESC;
                """,
                (since, now, module_id),
            )
            rows = cur.fetchall()

    if not rows:
        return {
            "total_signals":   0,
            "correct_signals": 0,
            "hit_rate_pct":    0.0,
            "avg_gain_pct":    None,
            "avg_loss_pct":    None,
            "expectancy":      None,
            "by_source_class": {},
            "by_ticker":       {},
        }

    total   = len(rows)
    correct = sum(1 for r in rows if r[1] is not None and r[1] > 0)
    gains   = [r[1] for r in rows if r[1] is not None and r[1] > 0]
    losses  = [abs(r[1]) for r in rows if r[1] is not None and r[1] <= 0]

    hit_rate  = (correct / total) * 100 if total > 0 else 0
    avg_gain  = (sum(gains) / len(gains)) if gains else None
    avg_loss  = (sum(losses) / len(losses)) if losses else None
    miss_rate = 1 - (hit_rate / 100)

    expectancy = None
    if avg_gain and avg_loss:
        expectancy = ((hit_rate / 100) * avg_gain) - (miss_rate * avg_loss)

    # by_ticker breakdown
    by_ticker: dict[str, dict] = {}
    for side, pnl, symbol in rows:
        if symbol not in by_ticker:
            by_ticker[symbol] = {"total": 0, "correct": 0}
        by_ticker[symbol]["total"] += 1
        if pnl is not None and pnl > 0:
            by_ticker[symbol]["correct"] += 1

    return {
        "total_signals":   total,
        "correct_signals": correct,
        "hit_rate_pct":    round(hit_rate, 2),
        "avg_gain_pct":    round(avg_gain, 3) if avg_gain else None,
        "avg_loss_pct":    round(avg_loss, 3) if avg_loss else None,
        "expectancy":      round(expectancy, 3) if expectancy else None,
        "by_source_class": {},
        "by_ticker":       by_ticker,
    }


def _write_hit_rate(stats: dict, window_days: int, now: datetime) -> None:
    import psycopg
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO hit_rate (
                    computed_at, window_days,
                    total_signals, correct_signals, hit_rate_pct,
                    avg_gain_pct, avg_loss_pct, expectancy,
                    by_source_class, by_ticker
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (computed_at, window_days) DO UPDATE
                SET hit_rate_pct    = EXCLUDED.hit_rate_pct,
                    total_signals   = EXCLUDED.total_signals,
                    correct_signals = EXCLUDED.correct_signals,
                    avg_gain_pct    = EXCLUDED.avg_gain_pct,
                    avg_loss_pct    = EXCLUDED.avg_loss_pct,
                    expectancy      = EXCLUDED.expectancy,
                    by_ticker       = EXCLUDED.by_ticker;
                """,
                (
                    now, window_days,
                    stats["total_signals"], stats["correct_signals"],
                    stats["hit_rate_pct"],
                    stats["avg_gain_pct"], stats["avg_loss_pct"],
                    stats["expectancy"],
                    psycopg.types.json.Json(stats["by_source_class"]),
                    psycopg.types.json.Json(stats["by_ticker"]),
                ),
            )
        conn.commit()
