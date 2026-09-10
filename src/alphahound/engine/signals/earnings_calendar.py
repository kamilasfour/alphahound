"""Earnings calendar — pulls upcoming earnings dates for watchlist tickers.

Source: Finnhub /calendar/earnings endpoint (already have API key).
Yahoo Finance v10/quoteSummary is now 401 Unauthorized from server IPs.
Finnhub has a generous free tier (60 calls/min) and earnings data is clean.

What it does:
    Pulls all earnings events for the next 30 days in one API call,
    then filters to our watchlist tickers and stores in earnings_calendar.

Used by:
    - alphahound signals earnings  -- show upcoming earnings
    - kalshi_watcher.py            -- match Kalshi contracts to earnings
    - trade_advisor.py             -- context enrichment (future)

Writes to: earnings_calendar table directly (not raw_posts).

Env var: FINNHUB_API_KEY
"""
from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta, timezone
from typing import ClassVar, Iterable

import httpx

from alphahound.engine.adapters.base import BaseAdapter
from alphahound.engine.adapters.models import Post
from alphahound.engine.storage import EntityResolver, get_conn

log = logging.getLogger(__name__)

FINNHUB_BASE = "https://finnhub.io/api/v1"
LOOKAHEAD_DAYS = 30

WATCHLIST = {
    "AAPL", "NVDA", "TSLA", "AMD", "AMZN", "MSFT", "META",
    "ARM",  "BE",   "SNDK", "PLTR", "GME",  "SMCI",
    "MSTR", "COIN", "INTC", "SOFI", "F",    "BAC",
    "NFLX", "HOOD", "GOOG", "AVGO", "NOW",  "QCOM",
    "UBER", "SNAP", "SHOP", "USO",
    "ORCL", "IBM",  "CMG",  "MA",   "ADBE", "UNH",
    "PYPL", "TSM",  "CAT",  "CVX",  "MU",
}


class EarningsCalendarAdapter(BaseAdapter):
    """Pulls upcoming earnings dates from Finnhub."""

    adapter_id: ClassVar[str] = "stocks.earnings_calendar"
    source_class: ClassVar[str] = "price_data"
    tier: ClassVar[str] = "A"
    tos_basis: ClassVar[str] = "Finnhub free tier — personal research use"

    def __init__(self) -> None:
        self._api_key = os.environ.get("FINNHUB_API_KEY", "")
        if not self._api_key:
            raise RuntimeError("FINNHUB_API_KEY not set in .env")

    def pull(self, since: datetime, cursor: str | None = None) -> Iterable[Post]:
        """Pull earnings calendar from Finnhub, store in earnings_calendar."""
        observed_at = datetime.now(timezone.utc)
        today  = date.today()
        to_date = today + timedelta(days=LOOKAHEAD_DAYS)

        try:
            events = self._fetch_earnings(today, to_date)
        except Exception as exc:
            log.error("Earnings calendar fetch failed: %s", exc)
            return iter([])

        resolver = EntityResolver()
        stored = 0

        for event in events:
            ticker = (event.get("symbol") or "").upper().strip()
            if ticker not in WATCHLIST:
                continue

            date_str = event.get("date") or ""
            try:
                earnings_date = date.fromisoformat(date_str)
            except ValueError:
                continue

            eps_estimate = event.get("epsEstimate")
            fiscal_quarter = event.get("quarter")
            fiscal_year = event.get("year")
            period = f"Q{fiscal_quarter} {fiscal_year}" if fiscal_quarter and fiscal_year else None

            try:
                entity_id = resolver.resolve(
                    module_id="stocks", symbol=ticker, kind="ticker"
                )
                _upsert_earnings(entity_id, earnings_date, period, eps_estimate, observed_at)
                stored += 1
                log.debug("Earnings: %s → %s", ticker, earnings_date)
            except Exception as exc:
                log.warning("Earnings upsert failed for %s: %s", ticker, exc)

        log.info("Earnings calendar: stored/updated %d events", stored)
        return iter([])

    def _fetch_earnings(self, from_date: date, to_date: date) -> list[dict]:
        with httpx.Client(base_url=FINNHUB_BASE, timeout=15.0) as client:
            resp = client.get(
                "/calendar/earnings",
                params={
                    "from": from_date.isoformat(),
                    "to":   to_date.isoformat(),
                    "token": self._api_key,
                },
            )
            resp.raise_for_status()
            data = resp.json()
        return data.get("earningsCalendar", [])


def get_upcoming_earnings(days_ahead: int = 14) -> dict[str, date]:
    """Return {ticker: earnings_date} for tickers with earnings in the next N days.

    Used by trade_advisor and kalshi_watcher.
    """
    today  = date.today()
    cutoff = today + timedelta(days=days_ahead)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT e.canonical_symbol, ec.earnings_date
                FROM earnings_calendar ec
                JOIN entities e ON e.entity_id = ec.entity_id
                WHERE ec.earnings_date BETWEEN %s AND %s
                  AND ec.beat IS NULL
                ORDER BY ec.earnings_date ASC;
                """,
                (today, cutoff),
            )
            return {row[0]: row[1] for row in cur.fetchall()}


def _upsert_earnings(
    entity_id: str,
    earnings_date: date,
    fiscal_quarter: str | None,
    estimate_eps: float | None,
    observed_at: datetime,
) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO earnings_calendar
                    (entity_id, earnings_date, fiscal_quarter, estimate_eps, updated_at)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (entity_id, earnings_date) DO UPDATE
                    SET fiscal_quarter = EXCLUDED.fiscal_quarter,
                        estimate_eps   = EXCLUDED.estimate_eps,
                        updated_at     = EXCLUDED.updated_at;
                """,
                (entity_id, earnings_date, fiscal_quarter, estimate_eps, observed_at),
            )
        conn.commit()
