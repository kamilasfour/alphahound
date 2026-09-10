"""Alpaca paper trading broker — Sprint 9.

Wraps the Alpaca Trade API for paper order execution.
Called by `alphahound signals execute` and `alphahound signals close-positions`.

All operations are PAPER TRADING only.
Live trading requires changing ALPACA_BASE_URL in .env to the live endpoint.

Environment variables required:
    ALPACA_API_KEY      — from alpaca.markets dashboard
    ALPACA_SECRET_KEY   — from alpaca.markets dashboard
    ALPACA_BASE_URL     — https://paper-api.alpaca.markets
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

log = logging.getLogger(__name__)


@dataclass
class AlpacaOrder:
    order_id:         str
    ticker:           str
    side:             Literal["buy", "sell_short"]
    qty:              float
    notional:         float | None
    status:           str
    filled_avg_price: float | None
    submitted_at:     datetime


@dataclass
class AlpacaPosition:
    ticker:            str
    side:              Literal["long", "short"]
    qty:               float
    avg_entry:         float
    current_price:     float
    unrealized_pl:     float
    unrealized_pl_pct: float


class AlpacaBroker:
    """Thin wrapper around alpaca-trade-api for paper trading."""

    def __init__(self) -> None:
        api_key    = os.environ.get("ALPACA_API_KEY", "")
        secret_key = os.environ.get("ALPACA_SECRET_KEY", "")
        base_url   = os.environ.get("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

        if not api_key or not secret_key:
            raise RuntimeError(
                "ALPACA_API_KEY and ALPACA_SECRET_KEY must be set in .env"
            )

        import alpaca_trade_api as tradeapi  # type: ignore
        self._api = tradeapi.REST(api_key, secret_key, base_url)
        log.info("AlpacaBroker initialised — base_url=%s", base_url)

    # ------------------------------------------------------------------
    # Account
    # ------------------------------------------------------------------

    def get_account(self) -> dict:
        """Return key account fields including position market values."""
        acct = self._api.get_account()
        return {
            "account_number":    acct.account_number,
            "status":            acct.status,
            "equity":            float(acct.equity),
            "cash":              float(acct.cash),
            "buying_power":      float(acct.buying_power),
            "portfolio_value":   float(acct.portfolio_value),
            # Used for portfolio cap — actual deployed capital
            "long_market_value":  float(acct.long_market_value  or 0),
            "short_market_value": abs(float(acct.short_market_value or 0)),
        }

    # ------------------------------------------------------------------
    # Orders
    # ------------------------------------------------------------------

    def place_order(
        self,
        ticker:   str,
        side:     Literal["buy", "sell_short"],
        notional: float,
    ) -> AlpacaOrder:
        """Place a market order.

        LONG orders: placed as fractional notional (Alpaca supports this for buys).
        SHORT orders: Alpaca does NOT support fractional notional shorts.
                      We fetch the current ask price and convert notional → whole shares.

        Args:
            ticker:   Stock symbol e.g. 'XLF'
            side:     'buy' for LONG, 'sell_short' for SHORT
            notional: Dollar amount — e.g. 500.00
        """
        if notional < 1.0:
            raise ValueError(f"Notional ${notional:.2f} is below Alpaca minimum of $1")

        if side == "sell_short":
            # Shorts must use integer share qty — fetch latest price to convert
            try:
                quote = self._api.get_latest_quote(ticker.upper())
                price = float(quote.ap) if quote.ap else float(quote.bp)
            except Exception:
                # Fall back to last trade price
                trade = self._api.get_latest_trade(ticker.upper())
                price = float(trade.p)

            qty = max(1, int(notional / price))  # whole shares only
            log.info("Placing sell (short) order: %s %d shares (~$%.2f notional @ $%.2f)",
                     ticker, qty, qty * price, price)

            order = self._api.submit_order(
                symbol=ticker.upper(),
                qty=qty,
                side="sell",
                type="market",
                time_in_force="day",
            )
        else:
            # LONG: fractional notional order
            log.info("Placing buy order: %s $%.2f notional", ticker, notional)
            order = self._api.submit_order(
                symbol=ticker.upper(),
                notional=round(notional, 2),
                side="buy",
                type="market",
                time_in_force="day",
            )

        return AlpacaOrder(
            order_id=order.id,
            ticker=ticker.upper(),
            side=side,
            qty=float(order.qty) if order.qty else 0.0,
            notional=notional,
            status=order.status,
            filled_avg_price=float(order.filled_avg_price) if order.filled_avg_price else None,
            submitted_at=datetime.now(timezone.utc),
        )

    def get_order(self, order_id: str) -> AlpacaOrder | None:
        """Fetch current status of an order by ID."""
        try:
            order = self._api.get_order(order_id)
            return AlpacaOrder(
                order_id=order.id,
                ticker=order.symbol,
                side=order.side,
                qty=float(order.qty) if order.qty else 0.0,
                notional=float(order.notional) if order.notional else None,
                status=order.status,
                filled_avg_price=float(order.filled_avg_price) if order.filled_avg_price else None,
                submitted_at=datetime.fromisoformat(order.submitted_at.replace("Z", "+00:00")),
            )
        except Exception as exc:
            log.warning("get_order(%s) failed: %s", order_id, exc)
            return None

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order. Returns True if cancelled."""
        try:
            self._api.cancel_order(order_id)
            log.info("Cancelled order %s", order_id)
            return True
        except Exception as exc:
            log.warning("cancel_order(%s) failed: %s", order_id, exc)
            return False

    # ------------------------------------------------------------------
    # Positions
    # ------------------------------------------------------------------

    def get_position(self, ticker: str) -> AlpacaPosition | None:
        """Get current open position for a ticker. None if flat."""
        try:
            pos = self._api.get_position(ticker.upper())
            side: Literal["long", "short"] = "long" if float(pos.qty) > 0 else "short"
            return AlpacaPosition(
                ticker=pos.symbol,
                side=side,
                qty=abs(float(pos.qty)),
                avg_entry=float(pos.avg_entry_price),
                current_price=float(pos.current_price),
                unrealized_pl=float(pos.unrealized_pl),
                unrealized_pl_pct=float(pos.unrealized_plpc) * 100,
            )
        except Exception:
            return None

    def get_all_positions(self) -> list[AlpacaPosition]:
        """Return all open positions."""
        positions = []
        try:
            for pos in self._api.list_positions():
                side: Literal["long", "short"] = "long" if float(pos.qty) > 0 else "short"
                positions.append(AlpacaPosition(
                    ticker=pos.symbol,
                    side=side,
                    qty=abs(float(pos.qty)),
                    avg_entry=float(pos.avg_entry_price),
                    current_price=float(pos.current_price),
                    unrealized_pl=float(pos.unrealized_pl),
                    unrealized_pl_pct=float(pos.unrealized_plpc) * 100,
                ))
        except Exception as exc:
            log.warning("list_positions failed: %s", exc)
        return positions

    def close_position(self, ticker: str) -> AlpacaOrder | None:
        """Close the full position for a ticker at market."""
        pos = self.get_position(ticker)
        if pos is None:
            log.info("close_position(%s): no open position", ticker)
            return None

        try:
            order = self._api.close_position(ticker.upper())
            log.info("Closed position %s — order_id=%s", ticker, order.id)
            return AlpacaOrder(
                order_id=order.id,
                ticker=ticker.upper(),
                side=order.side,
                qty=float(order.qty) if order.qty else 0.0,
                notional=None,
                status=order.status,
                filled_avg_price=float(order.filled_avg_price) if order.filled_avg_price else None,
                submitted_at=datetime.now(timezone.utc),
            )
        except Exception as exc:
            log.warning("close_position(%s) failed: %s", ticker, exc)
            return None

    def close_all_positions(self) -> list[dict]:
        """Close all open positions at market. Returns summary list."""
        results = []
        positions = self.get_all_positions()
        if not positions:
            log.info("close_all_positions: no open positions")
            return results
        for pos in positions:
            order = self.close_position(pos.ticker)
            results.append({
                "ticker":  pos.ticker,
                "side":    pos.side,
                "qty":     pos.qty,
                "status":  order.status if order else "error",
                "order_id": order.order_id if order else None,
            })
        return results

    # ------------------------------------------------------------------
    # Market hours
    # ------------------------------------------------------------------

    def is_market_open(self) -> bool:
        """Return True if US equities market is currently open.
        
        Uses ET time directly. Alpaca clock API is unreliable on this server.
        Server runs PST: NYSE 9:30 AM ET = 6:30 AM PT = 14:30 UTC.
        """
        from zoneinfo import ZoneInfo
        now_et = datetime.now(timezone.utc).astimezone(ZoneInfo('America/New_York'))
        h, m, dow = now_et.hour, now_et.minute, now_et.weekday()
        # Mon-Fri, 9:30 AM - 4:00 PM ET
        return (
            dow < 5 and
            (h > 9 or (h == 9 and m >= 30)) and
            h < 16
        )

    def next_market_open(self) -> datetime | None:
        """Return UTC datetime of next market open (9:30 AM ET)."""
        from zoneinfo import ZoneInfo
        from datetime import timedelta
        now_et = datetime.now(timezone.utc).astimezone(ZoneInfo('America/New_York'))
        # Find next weekday at 9:30 AM ET
        candidate = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
        if now_et >= candidate:
            candidate += timedelta(days=1)
        # Skip weekends
        while candidate.weekday() >= 5:
            candidate += timedelta(days=1)
        return candidate.astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_broker: AlpacaBroker | None = None


def get_broker() -> AlpacaBroker:
    """Return singleton broker instance (lazy init)."""
    global _broker
    if _broker is None:
        _broker = AlpacaBroker()
    return _broker
