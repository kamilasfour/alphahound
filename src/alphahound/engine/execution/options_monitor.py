"""Options Position Manager — Sprint 12.

Monitors all open options positions from options_trade_log,
queries Alpaca for current market values, and automatically
closes positions when they hit the gain target or stop loss.

CLOSE RULES
───────────
  Target gain:  close when position value >= entry_debit * (1 + TARGET_GAIN_PCT)
                Default: 50% gain (TARGET_GAIN_PCT = 0.50)
                e.g. MU spread cost $1,129 → close when worth $1,694

  Stop loss:    close when position value <= entry_debit * STOP_LOSS_PCT
                Default: 20% remaining (STOP_LOSS_PCT = 0.20)
                e.g. MU spread cost $1,129 → close when worth $226 (lost 80%)

  Expiry guard: close any position with DTE <= CLOSE_BEFORE_EXPIRY_DAYS
                Default: 5 days before expiry — never hold to expiry

WHY 50% GAIN TARGET
───────────────────
Options spreads have a theoretical maximum value at expiry. Getting out
at 50% of max gain captures most of the profit while avoiding the final
stretch where theta decay and gamma risk accelerate. The last 50% of
gain takes disproportionate time and risk to capture.

WHY 80% LOSS STOP
─────────────────
Cutting at 80% loss (keeping 20% of remaining value) preserves capital
for the next signal. A spread that's lost 80% has very little chance of
recovering before expiry. Exit and redeploy.

ALPACA OPTIONS POSITION QUERY
──────────────────────────────
Alpaca returns options positions via GET /v2/positions with asset_class=option.
Each position has symbol (OCC format), qty, market_value, cost_basis,
unrealized_pl, unrealized_plpc.

For spreads (2 legs), we sum both legs' market_value and compare against
the original estimated_debit stored in options_trade_log.

CLI: alphahound signals options-monitor [--close] [--dry-run]
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import httpx

from alphahound.engine.storage import get_conn

log = logging.getLogger(__name__)

# ─── Config ──────────────────────────────────────────────────────────────────

TARGET_GAIN_PCT          = float(os.environ.get("OPTIONS_TARGET_GAIN_PCT",   "0.50"))  # close at 50% gain
STOP_LOSS_PCT            = float(os.environ.get("OPTIONS_STOP_LOSS_PCT",      "0.20"))  # close when 80% lost
CLOSE_BEFORE_EXPIRY_DAYS = int(os.environ.get("OPTIONS_CLOSE_BEFORE_EXPIRY", "5"))      # close 5 days before expiry
MAX_HOLD_DAYS_CATALYST   = int(os.environ.get("OPTIONS_MAX_HOLD_CATALYST",   "3"))      # close 3 days after catalyst fires
MAX_HOLD_DAYS_NO_CATALYST= int(os.environ.get("OPTIONS_MAX_HOLD_NO_CATALYST","14"))     # close after 14 days if no catalyst


# ─── Data shapes ─────────────────────────────────────────────────────────────

@dataclass
class OptionsPosition:
    """A live options position with current market values."""
    trade_log_id:    int
    ticker:          str
    structure_type:  str
    direction:       str
    contracts:       int
    entry_debit:     float       # what we paid (per spread/strangle)
    current_value:   float       # current market value (per spread/strangle)
    unrealized_pl:   float       # current_value - entry_debit
    unrealized_pl_pct: float     # (current_value / entry_debit) - 1
    expiry:          Optional[date]
    dte:             int          # days to expiry
    catalyst_type:   Optional[str]
    catalyst_date:   Optional[date]
    composite_score: float
    entered_at:      datetime
    legs:            list[dict]  # from legs_json
    alpaca_legs:     list[dict]  # from Alpaca live positions
    close_reason:    Optional[str] = None  # populated when should_close is True

    @property
    def should_close(self) -> bool:
        return self.close_reason is not None

    @property
    def gain_target(self) -> float:
        return self.entry_debit * (1 + TARGET_GAIN_PCT)

    @property
    def stop_loss_floor(self) -> float:
        return self.entry_debit * STOP_LOSS_PCT

    def display(self) -> str:
        pl_str = f"+${self.unrealized_pl:.0f}" if self.unrealized_pl >= 0 else f"-${abs(self.unrealized_pl):.0f}"
        pct_str = f"{self.unrealized_pl_pct:+.1%}"
        days_held = (date.today() - self.entered_at.date()).days if self.entered_at else 0
        max_days = MAX_HOLD_DAYS_CATALYST + 3 if self.catalyst_date else MAX_HOLD_DAYS_NO_CATALYST
        time_str = f"  {days_held}d/{max_days}d held"
        close_str = f" → CLOSE: {self.close_reason}" if self.close_reason else ""
        return (
            f"  {self.ticker:<6} {self.structure_type:<22} "
            f"entry=${self.entry_debit:.0f}  now=${self.current_value:.0f}  "
            f"P&L={pl_str} ({pct_str})  {self.dte}DTE{time_str}{close_str}"
        )


# ─── Main entry points ────────────────────────────────────────────────────────

def monitor_positions(close: bool = False, dry_run: bool = False) -> list[OptionsPosition]:
    """Check all open options positions and optionally close the ones that hit targets.

    Args:
        close:   If True, submit closing orders for positions that hit targets
        dry_run: If True, show what would be closed without submitting orders

    Returns:
        List of OptionsPosition objects with current state
    """
    open_trades = _get_open_trades()
    if not open_trades:
        log.info("options monitor: no open trades in options_trade_log")
        return []

    alpaca_positions = _fetch_alpaca_options_positions()
    today = date.today()

    positions = []
    for trade in open_trades:
        pos = _build_position(trade, alpaca_positions, today)
        if pos is None:
            continue
        _evaluate_close_reason(pos, today)
        positions.append(pos)

        if pos.should_close:
            log.info("Position %s %s should close: %s  P&L=%+.0f (%.1f%%)",
                     pos.ticker, pos.structure_type, pos.close_reason,
                     pos.unrealized_pl, pos.unrealized_pl_pct * 100)

            if close and not dry_run:
                _close_position(pos)
            elif dry_run and pos.should_close:
                log.info("[DRY RUN] Would close %s: %s", pos.ticker, pos.close_reason)

    return positions


def get_open_positions_summary() -> list[dict]:
    """Return a summary of all open options positions for the dashboard API."""
    positions = monitor_positions(close=False)
    return [
        {
            "ticker":          p.ticker,
            "structure_type":  p.structure_type,
            "direction":       p.direction,
            "contracts":       p.contracts,
            "entry_debit":     round(p.entry_debit, 2),
            "current_value":   round(p.current_value, 2),
            "unrealized_pl":   round(p.unrealized_pl, 2),
            "unrealized_pl_pct": round(p.unrealized_pl_pct * 100, 1),
            "gain_target":     round(p.gain_target, 2),
            "stop_loss_floor": round(p.stop_loss_floor, 2),
            "dte":             p.dte,
            "expiry":          p.expiry.isoformat() if p.expiry else None,
            "catalyst_type":   p.catalyst_type,
            "catalyst_date":   p.catalyst_date.isoformat() if p.catalyst_date else None,
            "composite_score": p.composite_score,
            "entered_at":      p.entered_at.isoformat(),
            "should_close":    p.should_close,
            "close_reason":    p.close_reason,
        }
        for p in positions
    ]


# ─── Open trades query ────────────────────────────────────────────────────────

def _get_open_trades() -> list[dict]:
    """Fetch all placed options trades that haven't been closed yet."""
    # Ensure table exists before querying
    try:
        from alphahound.engine.execution.options_executor import _ensure_options_log_table
        _ensure_options_log_table()
    except Exception:
        pass
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, ticker, structure_type, direction, contracts,
                           estimated_debit, catalyst_type, catalyst_date,
                           composite_score, time, legs_json, order_ids
                    FROM options_trade_log
                    WHERE status = 'placed'
                      AND closed_at IS NULL
                    ORDER BY time DESC;
                """)
                cols = [d.name for d in cur.description]
                return [dict(zip(cols, r)) for r in cur.fetchall()]
    except Exception as exc:
        log.error("_get_open_trades failed: %s", exc)
        return []


# ─── Alpaca position query ────────────────────────────────────────────────────

def _alpaca_headers() -> dict:
    return {
        "APCA-API-KEY-ID":     os.environ.get("ALPACA_API_KEY", ""),
        "APCA-API-SECRET-KEY": os.environ.get("ALPACA_SECRET_KEY", ""),
        "Accept":              "application/json",
    }


def _alpaca_base() -> str:
    return os.environ.get("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")


def _fetch_alpaca_options_positions() -> list[dict]:
    """Fetch all open options positions from Alpaca."""
    try:
        resp = httpx.get(
            f"{_alpaca_base()}/v2/positions",
            headers=_alpaca_headers(),
            timeout=15.0,
        )
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, list):
            return []
        # Filter to options only (asset_class=option or OCC symbol pattern)
        return [p for p in data if p.get('asset_class') == 'option'
                or (len(p.get('symbol','')) > 10 and any(c in p.get('symbol','') for c in ('C0','P0')))]
    except Exception as exc:
        log.warning("_fetch_alpaca_options_positions failed: %s", exc)
        return []


# ─── Position builder ─────────────────────────────────────────────────────────

def _build_position(
    trade: dict,
    alpaca_positions: list[dict],
    today: date,
) -> Optional[OptionsPosition]:
    """Match a trade log entry to live Alpaca positions and build an OptionsPosition."""
    ticker         = trade["ticker"]
    structure_type = trade["structure_type"]
    contracts      = trade.get("contracts") or 1
    entry_debit    = float(trade.get("estimated_debit") or 0)
    legs_json      = trade.get("legs_json") or []

    if not entry_debit:
        return None

    # Parse expiry from legs
    expiry = None
    if legs_json:
        try:
            first_leg = legs_json[0] if isinstance(legs_json, list) else []
            if first_leg:
                expiry_str = first_leg.get("expiry", "")
                if expiry_str:
                    expiry = date.fromisoformat(expiry_str[:10])
        except (ValueError, IndexError, AttributeError):
            pass

    dte = (expiry - today).days if expiry else 999

    # Match Alpaca positions to our legs by reconstructing OCC symbol from leg data
    matched_legs = []
    total_market_value = 0.0

    if alpaca_positions and legs_json:
        # Build a lookup of Alpaca positions by symbol (strip spaces)
        alpaca_by_symbol = {}
        for ap in alpaca_positions:
            sym = ap.get('symbol', '').replace(' ', '').upper()
            alpaca_by_symbol[sym] = ap

        for leg in (legs_json if isinstance(legs_json, list) else []):
            # Reconstruct OCC symbol from leg data
            leg_symbol = _reconstruct_occ(ticker, leg)
            if not leg_symbol:
                continue
            clean_sym = leg_symbol.replace(' ', '').upper()
            ap = alpaca_by_symbol.get(clean_sym)
            if ap:
                mv = float(ap.get('market_value') or 0)
                total_market_value += mv
                matched_legs.append({
                    'symbol':        ap['symbol'],
                    'qty':           ap.get('qty'),
                    'market_value':  mv,
                    'cost_basis':    float(ap.get('cost_basis') or 0),
                    'unrealized_pl': float(ap.get('unrealized_pl') or 0),
                })
            else:
                log.debug('_build_position: no Alpaca match for %s (tried %s)', ticker, clean_sym)

    # If we couldn't match Alpaca positions (market closed, position not yet opened)
    # use entry_debit as current_value to show neutral P&L
    if not matched_legs:
        current_value = entry_debit
    else:
        # Alpaca market_value is the total dollar value for all contracts
        # Normalise to per-spread value
        current_value = abs(total_market_value) / contracts if contracts else abs(total_market_value)

    unrealized_pl     = current_value - entry_debit
    unrealized_pl_pct = (unrealized_pl / entry_debit) if entry_debit > 0 else 0.0

    # Parse catalyst date
    catalyst_date = None
    if trade.get("catalyst_date"):
        try:
            catalyst_date = date.fromisoformat(str(trade["catalyst_date"])[:10])
        except ValueError:
            pass

    return OptionsPosition(
        trade_log_id    = trade["id"],
        ticker          = ticker,
        structure_type  = structure_type,
        direction       = trade.get("direction", "NEUTRAL"),
        contracts       = contracts,
        entry_debit     = entry_debit,
        current_value   = current_value,
        unrealized_pl   = unrealized_pl,
        unrealized_pl_pct = unrealized_pl_pct,
        expiry          = expiry,
        dte             = dte,
        catalyst_type   = trade.get("catalyst_type"),
        catalyst_date   = catalyst_date,
        composite_score = float(trade.get("composite_score") or 0),
        entered_at      = trade["time"],
        legs            = legs_json if isinstance(legs_json, list) else [],
        alpaca_legs     = matched_legs,
    )


def _reconstruct_occ(ticker: str, leg: dict) -> Optional[str]:
    """Try to reconstruct an OCC symbol from a leg dict."""
    try:
        from alphahound.engine.execution.options_executor import _build_occ_symbol
        return _build_occ_symbol(
            ticker,
            leg.get("expiry", ""),
            leg.get("contract_type", "CALL"),
            float(leg.get("strike", 0)),
        )
    except Exception:
        return None


# ─── Close evaluation ─────────────────────────────────────────────────────────

def _evaluate_close_reason(pos: OptionsPosition, today: date) -> None:
    """Set pos.close_reason if the position should be closed. Mutates in place."""

    days_held = (today - pos.entered_at.date()).days if pos.entered_at else 0

    # 1. Expiry guard — close before it expires worthless
    if pos.dte <= CLOSE_BEFORE_EXPIRY_DAYS:
        pos.close_reason = f"Expiry in {pos.dte} days — closing before expiry"
        return

    # 2. Catalyst passed — close within 3 days after catalyst
    if pos.catalyst_date and today > pos.catalyst_date + timedelta(days=MAX_HOLD_DAYS_CATALYST):
        pos.close_reason = f"Catalyst {pos.catalyst_type} on {pos.catalyst_date} passed {(today - pos.catalyst_date).days}d ago — closing"
        return

    # 3. Max hold time — close if held too long regardless of P&L
    if pos.catalyst_date:
        # For catalyst trades, max hold is until 3 days after catalyst
        pass  # handled above
    else:
        # No catalyst — close after MAX_HOLD_DAYS_NO_CATALYST
        if days_held >= MAX_HOLD_DAYS_NO_CATALYST:
            pos.close_reason = f"Max hold time reached: {days_held}d held (limit {MAX_HOLD_DAYS_NO_CATALYST}d) — time exit"
            return

    # Only evaluate P&L targets if we have real Alpaca price data
    if not pos.alpaca_legs:
        return

    # 4. Target gain reached
    if pos.current_value >= pos.gain_target:
        gain = pos.unrealized_pl
        pos.close_reason = (
            f"Target gain reached: +${gain:.0f} ({pos.unrealized_pl_pct:+.1%}) "
            f"≥ {TARGET_GAIN_PCT:.0%} target"
        )
        return

    # 5. Stop loss hit
    if pos.current_value <= pos.stop_loss_floor:
        loss = pos.unrealized_pl
        pos.close_reason = (
            f"Stop loss hit: ${loss:.0f} ({pos.unrealized_pl_pct:+.1%}) "
            f"≤ {(1-STOP_LOSS_PCT):.0%} loss limit"
        )
        return


# ─── Position closing ─────────────────────────────────────────────────────────

def _close_position(pos: OptionsPosition) -> bool:
    """Submit closing orders for all legs of a position using DELETE /v2/positions/{symbol}."""
    log.info("Closing position %s %s — %s", pos.ticker, pos.structure_type, pos.close_reason)

    headers = _alpaca_headers()
    base    = _alpaca_base()
    success = True

    for leg in pos.alpaca_legs:
        symbol = leg.get("symbol", "").replace(" ", "")
        if not symbol:
            continue
        try:
            resp = httpx.delete(
                f"{base}/v2/positions/{symbol}",
                headers=headers,
                timeout=15.0,
            )
            if resp.status_code in (200, 204):
                log.info("Close order placed via DELETE: %s", symbol)
            elif resp.status_code == 422:
                err = resp.json().get('message', '')
                if 'market hours' in err.lower():
                    log.warning("Close failed — market closed. Will retry at open: %s", symbol)
                else:
                    log.error("Close order rejected for %s: %s", symbol, err)
                success = False
            else:
                resp.raise_for_status()
        except Exception as exc:
            log.error("Close order failed for %s: %s", symbol, exc)
            success = False

    if success:
        _mark_trade_closed(pos)

    return success


def _mark_trade_closed(pos: OptionsPosition) -> None:
    """Update options_trade_log to mark the trade as closed."""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE options_trade_log
                    SET closed_at = now(),
                        pnl       = %s,
                        status    = 'closed',
                        notes     = %s
                    WHERE id = %s;
                """, (
                    round(pos.unrealized_pl * pos.contracts, 2),
                    pos.close_reason,
                    pos.trade_log_id,
                ))
            conn.commit()
        log.info("Marked trade %d closed: P&L=%.2f  reason=%s",
                 pos.trade_log_id, pos.unrealized_pl * pos.contracts, pos.close_reason)
    except Exception as exc:
        log.warning("_mark_trade_closed failed: %s", exc)


# ─── Hit rate update ──────────────────────────────────────────────────────────

def resolve_closed_trades() -> int:
    """Mark closed trades as WIN or LOSS in hit rate tracking. Returns count resolved."""
    resolved = 0
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                # Find closed options trades not yet resolved in hit rate
                cur.execute("""
                    SELECT t.id, t.ticker, t.entity_id, t.pnl,
                           t.composite_score, t.catalyst_type, t.closed_at
                    FROM options_trade_log t
                    WHERE t.status = 'closed'
                      AND t.pnl IS NOT NULL
                      AND NOT EXISTS (
                          SELECT 1 FROM hit_rate_log h
                          WHERE h.source_id = t.id::text
                            AND h.source_type = 'options_trade'
                      )
                    ORDER BY t.closed_at DESC
                    LIMIT 100;
                """)
                trades = cur.fetchall()

                for trade_id, ticker, entity_id, pnl, score, cat_type, closed_at in trades:
                    outcome = "WIN" if (pnl or 0) > 0 else "LOSS"
                    try:
                        cur.execute("""
                            INSERT INTO hit_rate_log
                                (time, entity_id, ticker, outcome, pnl,
                                 composite_score, catalyst_type, source_id, source_type)
                            VALUES (now(), %s, %s, %s, %s, %s, %s, %s, 'options_trade')
                            ON CONFLICT DO NOTHING;
                        """, (entity_id, ticker, outcome, pnl, score, cat_type, str(trade_id)))
                        resolved += 1
                    except Exception as exc:
                        log.debug("resolve_closed_trades: hit_rate_log insert failed: %s", exc)

            conn.commit()
    except Exception as exc:
        log.warning("resolve_closed_trades failed: %s", exc)

    if resolved:
        log.info("Resolved %d closed options trades into hit_rate_log", resolved)
    return resolved
