"""Alpaca paper trade executor — Sprint 9.

Called by:
    alphahound signals execute          — place paper orders for all current alerts
    alphahound signals execute --ticker X  — single ticker

Logic:
    1. Run trade-advice to get current recommendations (same as advise_all)
    2. Skip anything already open in Alpaca (position exists) or logged today
    3. Check portfolio exposure cap — stop opening positions if deployed >= MAX_DEPLOYED_PCT
    4. Place notional market order via AlpacaBroker
    5. Write alpaca_order_id + alpaca_status back to trade_log row

Market hours guard:
    If market is closed, prints next open time and exits cleanly.
    Orders placed outside market hours would queue as GTC — we don't want that
    for signals that may be stale by open. Always execute fresh at market open.

Portfolio exposure cap:
    MAX_DEPLOYED_PCT (default 0.60) limits total deployed capital to 60% of equity.
    Buying power is fetched once per execute_all() run and checked before each order.
    deployed_pct = (equity - buying_power) / equity
    If deployed_pct >= MAX_DEPLOYED_PCT, all further orders are skipped for that run.
    This prevents the engine from fully deploying the account across many simultaneous
    signals. Override via MAX_DEPLOYED_PCT env var (e.g. MAX_DEPLOYED_PCT=0.80).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone, timedelta

from alphahound.engine.execution.alpaca_broker import get_broker
from alphahound.engine.execution.technical_gate import check as tech_check, TechVerdict
from alphahound.engine.signals.macro_context import get_macro_context_cached, MacroVerdict
from alphahound.engine.signals.trade_advisor import (
    advise,
    advise_all,
    log_recommendation,
    Direction,
    TradeRecommendation,
)
from alphahound.engine.storage import get_conn

log = logging.getLogger(__name__)

MAX_DEPLOYED_PCT: float = float(os.environ.get("MAX_DEPLOYED_PCT", "0.60"))


def execute_all(module_id: str = "stocks", min_d: float = 4.0) -> list[dict]:
    """Place paper orders for all current recommendations.

    Returns list of execution results for CLI display.
    """
    broker = get_broker()

    if not broker.is_market_open():
        next_open = broker.next_market_open()
        next_str = next_open.strftime("%Y-%m-%d %H:%M UTC") if next_open else "unknown"
        return [{"status": "market_closed", "next_open": next_str}]

    recs = advise_all(module_id=module_id, min_d=min_d)
    if not recs:
        return [{"status": "no_alerts"}]

    # Macro context check — gates LONG execution on global risk-off
    # Already includes EWJ (Japan), FXI (China), EWG (Germany), EEM (Emerging Markets)
    # as part of its scoring — no separate global markets check needed
    macro = get_macro_context_cached()
    log.info("MacroContext: %s (score=%+.3f)", macro.verdict.value, macro.score)

    # Fetch account once — reused for exposure cap check on every order
    try:
        account = broker.get_account()
        log.info(
            "Account: equity=$%.0f buying_power=$%.0f",
            account["equity"], account["buying_power"],
        )
    except Exception as exc:
        log.warning("Could not fetch account for exposure check: %s", exc)
        account = None

    results = []
    for rec in recs:
        result = _execute_one(broker, rec, macro, account)
        results.append(result)

    return results


def execute_ticker(ticker: str) -> dict:
    """Place a paper order for a single ticker."""
    broker = get_broker()

    if not broker.is_market_open():
        next_open = broker.next_market_open()
        next_str = next_open.strftime("%Y-%m-%d %H:%M UTC") if next_open else "unknown"
        return {"status": "market_closed", "next_open": next_str}

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT entity_id FROM entities "
                "WHERE module_id='stocks' AND canonical_symbol=%s AND kind='ticker';",
                (ticker.upper(),),
            )
            row = cur.fetchone()

    if row is None:
        return {"status": "not_found", "ticker": ticker}

    rec = advise(str(row[0]))
    if rec is None or rec.direction == Direction.NO_TRADE:
        return {"status": "no_signal", "ticker": ticker}

    # Fetch account for single-ticker exposure check
    try:
        account = broker.get_account()
    except Exception:
        account = None

    return _execute_one(broker, rec, account=account)


def _execute_one(broker, rec: TradeRecommendation, macro=None, account: dict | None = None) -> dict:
    """Execute a single recommendation. Applies macro context size modifier.

    For HIGH/EXTREME tier signals with leveraged ETF routing:
    - rec.execute_ticker is the 3x ETF (e.g. FAZ, TQQQ)
    - rec.original_ticker is the signal source (e.g. XLF, QQQ)
    - Leveraged ETFs are always traded LONG (bear ETF = short exposure, no shorting needed)
    """
    # Use execute_ticker — may be a 3x leveraged ETF substitution
    ticker = rec.execute_ticker or rec.ticker

    # Skip if position already open in Alpaca (check execute_ticker)
    existing = broker.get_position(ticker)
    if existing is not None:
        log.info("Skipping %s — position already open (%s)", ticker, existing.side)
        return {"status": "already_open", "ticker": ticker, "side": existing.side}

    # Skip if already executed today (keyed on entity_id = original signal)
    if _already_executed_today(rec.entity_id):
        log.info("Skipping %s — already executed today", ticker)
        return {"status": "already_executed_today", "ticker": ticker}

    # Skip if position size is zero
    if rec.position_usd < 1.0:
        return {"status": "position_too_small", "ticker": ticker, "position_usd": rec.position_usd}

    # Portfolio exposure cap — use actual open position market value
    # NOT (equity - buying_power) which reads wrong on Alpaca margin accounts
    # (buying_power can be 2x equity giving a negative deployed_pct)
    if account is not None:
        equity        = account.get("equity", 0.0)
        position_value = account.get("long_market_value", 0.0) + account.get("short_market_value", 0.0)
        if equity > 0:
            deployed_pct = position_value / equity
            if deployed_pct >= MAX_DEPLOYED_PCT:
                log.info(
                    "Portfolio cap reached for %s: deployed=%.1f%% (position_value=$%.0f equity=$%.0f) >= max=%.1f%%",
                    ticker, deployed_pct * 100, position_value, equity, MAX_DEPLOYED_PCT * 100,
                )
                return {
                    "status":         "portfolio_cap_reached",
                    "ticker":         ticker,
                    "deployed_pct":   round(deployed_pct * 100, 1),
                    "max_pct":        round(MAX_DEPLOYED_PCT * 100, 1),
                    "equity":         round(equity, 2),
                    "position_value": round(position_value, 2),
                }

    # Macro context filter
    macro_size = 1.0
    macro_verdict = "NO_DATA"
    if macro is not None:
        macro_verdict = macro.verdict.value
        if macro.verdict == MacroVerdict.RISK_OFF and rec.direction == Direction.LONG:
            log.info("Macro RISK_OFF blocking LONG %s: %s", ticker, macro.reason)
            return {
                "status":        "macro_blocked",
                "ticker":        ticker,
                "macro_verdict": macro_verdict,
                "macro_score":   macro.score,
                "macro_reason":  macro.reason,
            }
        macro_size = macro.size_modifier

    # Technical gate — validate chart agrees with signal
    tech = tech_check(rec.entity_id, ticker, rec.direction.value)
    if tech.verdict == TechVerdict.REJECT:
        log.info("TechGate REJECTED %s: %s", ticker, tech.reason)
        return {
            "status":       "tech_rejected",
            "ticker":       ticker,
            "tech_verdict": tech.verdict.value,
            "tech_score":   tech.score,
            "tech_reason":  tech.reason,
            "indicators":   tech.indicators,
        }

    # Apply size modifiers: tech gate + macro
    notional = rec.position_usd * tech.size_modifier * macro_size
    if tech.verdict == TechVerdict.WEAK or macro_size < 1.0:
        log.info("Size reduced for %s: tech=%s macro=%s -> $%.0f",
                 ticker, tech.verdict.value, macro_verdict, notional)
    if notional < 1.0:
        return {"status": "position_too_small", "ticker": ticker, "position_usd": notional}

    # Map direction to Alpaca side
    # Leveraged ETFs are always traded LONG (bear ETF provides short exposure)
    if rec.is_leveraged:
        side = "buy"  # Always buy the leveraged ETF (even bear ETFs like FAZ, SQQQ)
    else:
        side = "buy" if rec.direction == Direction.LONG else "sell_short"

    try:
        order = broker.place_order(
            ticker=ticker,
            side=side,
            notional=notional,  # correctly sized: rec.position_usd * tech_modifier * macro_modifier
        )
    except Exception as exc:
        log.error("place_order failed for %s: %s", ticker, exc)
        return {"status": "error", "ticker": ticker, "error": str(exc)}

    # Log the recommendation to trade_log (writes if not already there)
    log_recommendation(rec)

    # Write alpaca_order_id back to trade_log
    _stamp_trade_log(rec, order.order_id, order.status)

    return {
        "status":          "placed",
        "ticker":          ticker,
        "original_ticker": rec.original_ticker,
        "is_leveraged":    rec.is_leveraged,
        "signal_tier":     rec.signal_tier.value,
        "side":            side,
        "notional":        rec.position_usd,
        "order_id":        order.order_id,
        "alpaca_status":   order.status,
        "conviction":      rec.conviction,
        "signal_prob":     rec.signal_prob,
        "d_value":         rec.d_value,
    }


def _already_executed_today(entity_id: str) -> bool:
    """Check if we already placed an Alpaca order for this entity today."""
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1 FROM trade_log
                    WHERE entity_id = %s
                      AND alpaca_order_id IS NOT NULL
                      AND time >= %s
                    LIMIT 1;
                    """,
                    (entity_id, today_start),
                )
                return cur.fetchone() is not None
    except Exception:
        return False


def _stamp_trade_log(rec: TradeRecommendation, order_id: str, status: str) -> None:
    """Write alpaca_order_id, status, and fill price onto the trade_log row.
    Polls Alpaca for up to 10s to get the filled_avg_price."""
    import time as _time
    broker = get_broker()

    # Poll for fill — market orders usually fill in <2s
    filled_price = None
    for _ in range(5):
        _time.sleep(2)
        order = broker.get_order(order_id)
        if order and order.filled_avg_price:
            filled_price = order.filled_avg_price
            status = order.status
            break

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE trade_log
                    SET alpaca_order_id = %s,
                        alpaca_status   = %s,
                        filled_price    = %s,
                        status          = CASE WHEN %s IS NOT NULL THEN 'open' ELSE 'pending' END
                    WHERE entity_id = %s
                      AND venue = 'signal'
                      AND alpaca_order_id IS NULL
                      AND time = (
                          SELECT MAX(time) FROM trade_log
                          WHERE entity_id = %s AND venue = 'signal'
                      );
                    """,
                    (order_id, status, filled_price, filled_price, rec.entity_id, rec.entity_id),
                )
            conn.commit()
        log.info("trade_log stamped for %s: order=%s fill=$%s status=%s",
                 rec.ticker, order_id, filled_price, status)
    except Exception as exc:
        log.warning("_stamp_trade_log failed for %s: %s", rec.ticker, exc)
