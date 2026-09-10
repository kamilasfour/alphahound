"""Position closer — Sprint 9.

Called by:
    alphahound signals close-positions          — check + close aged positions
    alphahound signals close-positions --ticker X  — force close one ticker

Logic:
    1. Pull all trade_log rows that have an alpaca_order_id but no closed_at
    2. For each open position, check if it should be closed:
       a. resolve_by date has passed  (hard exit)
       b. stop loss breached          (stop exit)
       c. divergence D < 1.5          (signal faded exit)
    3. Close via AlpacaBroker.close_position()
    4. Update trade_log: pnl, closed_at, close_order_id, alpaca_status
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone, date

from alphahound.engine.execution.alpaca_broker import get_broker
from alphahound.engine.storage import get_conn

log = logging.getLogger(__name__)

FADE_D_THRESHOLD = 1.5   # close if divergence drops below this


def close_aged_positions() -> list[dict]:
    """Check all open paper positions and close those that hit exit criteria."""
    broker = get_broker()
    open_trades = _get_open_trades()

    if not open_trades:
        return [{"status": "no_open_positions"}]

    results = []
    for trade in open_trades:
        result = _evaluate_and_close(broker, trade)
        results.append(result)

    return results


def force_close(ticker: str) -> dict:
    """Force close a position regardless of exit criteria."""
    broker = get_broker()

    order = broker.close_position(ticker)
    if order is None:
        return {"status": "no_position", "ticker": ticker}

    # Find the trade_log row and stamp it
    _stamp_closed(ticker=ticker, close_order_id=order.order_id, pnl=None)

    return {
        "status":          "force_closed",
        "ticker":          ticker,
        "close_order_id":  order.order_id,
        "alpaca_status":   order.status,
    }


def _evaluate_and_close(broker, trade: dict) -> dict:
    ticker     = trade["ticker"]
    entity_id  = trade["entity_id"]
    notes      = trade["notes"] or {}
    resolve_by = trade["resolve_by"]   # date or None
    stop_price = notes.get("stop_price")
    side       = trade["side"]          # 'buy' or 'short'

    # Get current position from Alpaca
    pos = broker.get_position(ticker)
    if pos is None:
        # Position already closed externally — just stamp trade_log
        _stamp_closed(ticker=ticker, close_order_id=None, pnl=None,
                      entity_id=entity_id, alpaca_order_id=trade["alpaca_order_id"])
        return {"status": "already_closed_externally", "ticker": ticker}

    current_price = pos.current_price
    reason        = None

    # 1. Hard exit — resolve_by date passed
    if resolve_by and date.today() >= resolve_by:
        reason = f"hard_exit (resolve_by {resolve_by})"

    # 2. Stop loss breached
    if reason is None and stop_price is not None:
        if side == "buy" and current_price <= stop_price:
            reason = f"stop_loss (price ${current_price:.2f} <= stop ${stop_price:.2f})"
        elif side == "short" and current_price >= stop_price:
            reason = f"stop_loss (price ${current_price:.2f} >= stop ${stop_price:.2f})"

    # 3. Signal faded — divergence D dropped below threshold
    if reason is None:
        current_d = _get_current_d(entity_id)
        if current_d is not None and current_d < FADE_D_THRESHOLD:
            reason = f"signal_faded (D={current_d:.2f} < {FADE_D_THRESHOLD})"

    if reason is None:
        return {
            "status":         "holding",
            "ticker":         ticker,
            "unrealized_pl":  pos.unrealized_pl,
            "unrealized_pct": pos.unrealized_pl_pct,
        }

    # Close the position
    order = broker.close_position(ticker)
    if order is None:
        return {"status": "close_failed", "ticker": ticker, "reason": reason}

    pnl = pos.unrealized_pl
    _stamp_closed(
        ticker=ticker,
        close_order_id=order.order_id,
        pnl=pnl,
        entity_id=entity_id,
        alpaca_order_id=trade["alpaca_order_id"],
    )

    return {
        "status":         "closed",
        "ticker":         ticker,
        "reason":         reason,
        "pnl":            pnl,
        "pnl_pct":        pos.unrealized_pl_pct,
        "close_order_id": order.order_id,
    }


def _get_open_trades() -> list[dict]:
    """Return all trade_log rows with an open Alpaca paper position."""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        tl.time,
                        tl.entity_id,
                        tl.side,
                        tl.size,
                        tl.price,
                        tl.notes,
                        tl.alpaca_order_id,
                        e.canonical_symbol
                    FROM trade_log tl
                    JOIN entities e ON e.entity_id = tl.entity_id
                    WHERE tl.alpaca_order_id IS NOT NULL
                      AND tl.closed_at IS NULL
                    ORDER BY tl.time ASC;
                    """
                )
                rows = cur.fetchall()
    except Exception as exc:
        log.error("_get_open_trades failed: %s", exc)
        return []

    trades = []
    for time, entity_id, side, size, price, notes, alpaca_order_id, ticker in rows:
        notes_dict = notes if isinstance(notes, dict) else {}
        # Parse resolve_by from outlook in notes
        resolve_by = None
        outlook = notes_dict.get("outlook", {})
        if isinstance(outlook, dict) and outlook.get("resolve_by"):
            try:
                resolve_by = date.fromisoformat(outlook["resolve_by"])
            except (ValueError, TypeError):
                pass

        trades.append({
            "time":            time,
            "entity_id":       str(entity_id),
            "side":            side,
            "size":            size,
            "price":           price,
            "notes":           notes_dict,
            "alpaca_order_id": alpaca_order_id,
            "ticker":          ticker,
            "resolve_by":      resolve_by,
        })

    return trades


def _get_current_d(entity_id: str) -> float | None:
    """Get latest divergence D value for an entity."""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT d_value FROM divergence_events "
                    "WHERE entity_id = %s ORDER BY time DESC LIMIT 1;",
                    (entity_id,),
                )
                row = cur.fetchone()
        return float(row[0]) if row else None
    except Exception:
        return None


def _stamp_closed(
    ticker: str,
    close_order_id: str | None,
    pnl: float | None,
    entity_id: str | None = None,
    alpaca_order_id: str | None = None,
) -> None:
    """Update trade_log row with close details."""
    now = datetime.now(timezone.utc)
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                if alpaca_order_id:
                    cur.execute(
                        """
                        UPDATE trade_log
                        SET closed_at      = %s,
                            close_order_id = %s,
                            pnl            = %s,
                            alpaca_status  = 'closed'
                        WHERE alpaca_order_id = %s;
                        """,
                        (now, close_order_id, pnl, alpaca_order_id),
                    )
                else:
                    # Fallback: match by entity + open position
                    cur.execute(
                        """
                        UPDATE trade_log
                        SET closed_at      = %s,
                            close_order_id = %s,
                            pnl            = %s,
                            alpaca_status  = 'closed'
                        WHERE entity_id = %s
                          AND closed_at IS NULL
                          AND alpaca_order_id IS NOT NULL;
                        """,
                        (now, close_order_id, pnl, entity_id),
                    )
            conn.commit()
    except Exception as exc:
        log.warning("_stamp_closed failed for %s: %s", ticker, exc)
