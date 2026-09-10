"""Kalshi adapter — prediction market contract state per ticker.

Kalshi is a regulated prediction market exchange. Contracts are binary
YES/NO markets on specific outcomes. YES price (cents) = implied probability.

We pull open markets related to our watchlist tickers and convert
YES price to a polarity signal:
    polarity = (yes_price - 50) / 50   →   range [-1.0, +1.0]
    yes_price > 50  → bullish (market expects YES)
    yes_price < 50  → bearish (market expects NO)
    yes_price = 50  → neutral (coin flip)

API: https://api.elections.kalshi.com/trade-api/v2
Auth: NOT required for market data (public endpoints).

Approach:
    1. Fetch open markets filtered by series/category for our tickers.
    2. Use keyword search against known series tickers for each stock.
    3. Store each open contract as one row in kalshi_contracts.

Ticker → Kalshi series mapping:
    Kalshi uses series like "KXNVDA", "KXTSLA" etc for stock prices.
    We maintain a static mapping. Add new mappings as Kalshi adds series.

Writes to: kalshi_contracts table (NOT raw_posts).

Rate limit: Public endpoints have generous limits (no auth = no rate limit concern).
We'll add a small sleep to be respectful.

Env var: None required (public API). KALSHI_API_KEY reserved for future
trading endpoints.
"""
from __future__ import annotations

import hashlib
import logging
import time
from datetime import datetime, timezone
from typing import ClassVar, Iterable

import httpx

from alphahound.engine.adapters.base import BaseAdapter
from alphahound.engine.adapters.models import Post
from alphahound.engine.storage import EntityResolver, get_conn

log = logging.getLogger(__name__)

KALSHI_BASE  = "https://api.elections.kalshi.com/trade-api/v2"
RATE_LIMIT_SLEEP = 0.5  # gentle — no auth, but be respectful

# Static mapping: our ticker → Kalshi series ticker prefix.
# Kalshi names stock price series "KX{TICKER}" typically.
# We search by series_ticker to find all open markets for each stock.
# Add entries as Kalshi lists new series.
TICKER_TO_KALSHI_SERIES: dict[str, list[str]] = {
    "AAPL":  ["KXAAPL"],
    "NVDA":  ["KXNVDA"],
    "TSLA":  ["KXTSLA"],
    "AMD":   ["KXAMD"],
    "AMZN":  ["KXAMZN"],
    "MSFT":  ["KXMSFT"],
    "META":  ["KXMETA"],
    "GOOGL": ["KXGOOGL"],
    "GOOG":  ["KXGOOG", "KXGOOGL"],
    "PLTR":  ["KXPLTR"],
    "GME":   ["KXGME"],
    "MSTR":  ["KXMSTR"],
    "COIN":  ["KXCOIN"],
    "HOOD":  ["KXHOOD"],
    "NFLX":  ["KXNFLX"],
    "AVGO":  ["KXAVGO"],
    "QCOM":  ["KXQCOM"],
    "SMCI":  ["KXSMCI"],
    "ARM":   ["KXARM"],
    "SOFI":  ["KXSOFI"],
    # Macro / ETF proxies
    "SPY":   ["KXSPY", "KXSPX"],
    "QQQ":   ["KXQQQ", "KXNDX"],
}

# Also pull markets from these broad financial categories.
FINANCIAL_CATEGORIES = ["financials", "stocks", "crypto", "economy"]


class KalshiAdapter(BaseAdapter):
    """Pulls prediction market contract state from Kalshi."""

    adapter_id: ClassVar[str] = "stocks.kalshi"
    source_class: ClassVar[str] = "prediction_market"
    tier: ClassVar[str] = "B"
    tos_basis: ClassVar[str] = (
        "Kalshi public API — free, personal research use, https://kalshi.com/terms"
    )

    def __init__(self) -> None:
        pass  # No API key needed for market data

    def pull(self, since: datetime, cursor: str | None = None) -> Iterable[Post]:
        """Pull open prediction market contracts relevant to our watchlist."""
        observed_at = datetime.now(timezone.utc)
        resolver    = EntityResolver()
        total_stored = 0

        with httpx.Client(
            base_url=KALSHI_BASE,
            timeout=20.0,
        ) as client:
            # 1. Pull markets for each known ticker series.
            for ticker, series_list in TICKER_TO_KALSHI_SERIES.items():
                for series in series_list:
                    try:
                        markets = self._fetch_markets_for_series(client, series)
                        for market in markets:
                            stored = self._store_contract(market, ticker, observed_at, resolver)
                            total_stored += stored
                    except Exception as exc:
                        log.warning("Kalshi: failed for %s series %s: %s", ticker, series, exc)
                    time.sleep(RATE_LIMIT_SLEEP)

            # 2. Pull open financial markets broadly and match to our tickers.
            try:
                broad_markets = self._fetch_financial_markets(client)
                matched = self._match_markets_to_tickers(
                    broad_markets, set(TICKER_TO_KALSHI_SERIES.keys()), observed_at, resolver
                )
                total_stored += matched
            except Exception as exc:
                log.warning("Kalshi: broad financial market fetch failed: %s", exc)

        log.info("Kalshi: %d contracts stored", total_stored)
        return iter([])

    # ----- fetchers -----

    def _fetch_markets_for_series(self, client: httpx.Client, series_ticker: str) -> list[dict]:
        """GET /markets?series_ticker={series}&status=open"""
        try:
            resp = client.get(
                "/markets",
                params={"series_ticker": series_ticker, "status": "open", "limit": 100},
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("markets", [])
        except httpx.HTTPError as exc:
            log.debug("Kalshi: series %s not found: %s", series_ticker, exc)
            return []

    def _fetch_financial_markets(self, client: httpx.Client) -> list[dict]:
        """GET /markets?status=open&category=financials — broad financial markets."""
        all_markets = []
        for category in FINANCIAL_CATEGORIES:
            try:
                resp = client.get(
                    "/markets",
                    params={"status": "open", "category": category, "limit": 200},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    all_markets.extend(data.get("markets", []))
                time.sleep(RATE_LIMIT_SLEEP)
            except httpx.HTTPError:
                pass
        return all_markets

    def _match_markets_to_tickers(
        self,
        markets: list[dict],
        ticker_set: set,
        observed_at: datetime,
        resolver: EntityResolver,
    ) -> int:
        """Match broad market results to our watchlist tickers by keyword search."""
        stored = 0
        for market in markets:
            title = (market.get("title") or "").upper()
            ticker_match = None
            for ticker in ticker_set:
                if ticker in title or f"${ticker}" in title:
                    ticker_match = ticker
                    break
            if ticker_match:
                try:
                    stored += self._store_contract(market, ticker_match, observed_at, resolver)
                except Exception as exc:
                    log.debug("Kalshi: match store failed: %s", exc)
        return stored

    # ----- storage -----

    def _store_contract(
        self,
        market: dict,
        ticker: str,
        observed_at: datetime,
        resolver: EntityResolver,
    ) -> int:
        """Parse one Kalshi market and insert into kalshi_contracts. Returns 1 if stored."""
        contract_id = market.get("ticker") or ""
        title       = market.get("title") or market.get("yes_sub_title") or ""
        status      = market.get("status") or ""

        # Skip non-open markets.
        if status not in ("open", "initialized", ""):
            return 0

        if not contract_id or not title:
            return 0

        # yes_price in cents (0-100) — the key signal field.
        yes_price = _safe_float(
            market.get("yes_bid_dollars") or
            market.get("last_price_dollars") or
            market.get("previous_price_dollars")
        )
        no_price = _safe_float(market.get("no_bid_dollars"))

        if yes_price is None:
            return 0

        # Convert dollar string to cents if needed (API returns "0.56" format).
        # yes_bid_dollars is in dollars (0-1 range), not cents (0-100).
        if yes_price <= 1.0:
            yes_price = yes_price * 100
        if no_price is not None and no_price <= 1.0:
            no_price = no_price * 100

        volume_24h  = _safe_int(market.get("volume_24h_fp"))
        open_interest = _safe_int(market.get("open_interest_fp"))

        # Parse close_time.
        close_time_str = market.get("close_time") or market.get("latest_expiration_time") or ""
        close_time = _parse_datetime(close_time_str)

        # Resolved status.
        result     = market.get("result") or None
        resolved   = result is not None and result in ("yes", "no")

        entity_id = resolver.resolve(
            module_id="stocks", symbol=ticker, kind="ticker"
        )

        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO kalshi_contracts (
                            time, entity_id, contract_id, title,
                            yes_price, no_price, volume_24h, open_interest,
                            close_time, resolved, resolution, raw, observed_at
                        )
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (entity_id, contract_id, time) DO NOTHING;
                        """,
                        (
                            observed_at, entity_id, contract_id, title,
                            yes_price, no_price, volume_24h, open_interest,
                            close_time, resolved, result,
                            __import__("psycopg").types.json.Json(market),
                            observed_at,
                        ),
                    )
                conn.commit()
            log.debug(
                "Kalshi: %s [%s] yes=%.0fc title=%s",
                ticker, contract_id, yes_price, title[:50],
            )
            return 1
        except Exception as exc:
            log.warning("Kalshi: DB insert failed for %s/%s: %s", ticker, contract_id, exc)
            return 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_float(val) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _safe_int(val) -> int | None:
    if val is None:
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


def _parse_datetime(s: str) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
