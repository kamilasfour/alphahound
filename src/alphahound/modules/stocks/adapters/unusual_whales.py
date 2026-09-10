"""Unusual Whales adapter — options flow alerts + per-ticker expiry breakdown.

Plan: API Basic ($125/mo) — api.unusualwhales.com

Correct endpoints (verified from live API responses):

1. GET /api/option-trades/flow-alerts
   Market-wide unusual options activity — sweeps, blocks, repeated hits.
   Returns contracts with: ticker, type (call/put), strike, expiry,
   total_premium, volume, open_interest, volume_oi_ratio, created_at.
   NOTE: No 'unusual_score' or 'sentiment' field in response.
   Sentiment is derived from: call=bullish, put=bearish.
   Conviction is derived from volume_oi_ratio and total_premium.

2. GET /api/stock/{ticker}/expiry-breakdown
   Per-ticker expiry breakdown: total volume + OI by expiry date.
   NOTE: No call/put split in this endpoint — just total volume/OI.
   We use volume/OI ratio as a proxy for active positioning intensity.

Writes to: options_flow table (NOT raw_posts).
The rule-based scorer reads options_flow directly and converts to polarity.

Rate limit: API Basic = 60 req/min.
At 1 flow-alerts + 37 expiry-breakdown = 38 calls/run. Safe.

Env var: UNUSUAL_WHALES_API_KEY
"""
from __future__ import annotations

import hashlib
import logging
import os
import time
from datetime import date, datetime, timezone
from typing import ClassVar, Iterable

import httpx

from alphahound.engine.adapters.base import BaseAdapter
from alphahound.engine.adapters.models import Post
from alphahound.engine.storage import EntityResolver, get_conn

from alphahound.modules.stocks.watchlist.watchlist import OPTIONS_WATCHLIST

log = logging.getLogger(__name__)

UW_BASE          = "https://api.unusualwhales.com"
RATE_LIMIT_SLEEP = 1.1
MIN_PREMIUM = 1_000.0       # lower threshold — catch more signals
MAX_ALERTS_PER_RUN = 2000  # pull everything available


class UnusualWhalesAdapter(BaseAdapter):
    """Pulls options flow alerts and expiry breakdowns from Unusual Whales."""

    adapter_id: ClassVar[str] = "stocks.unusual_whales"
    source_class: ClassVar[str] = "options_flow"
    tier: ClassVar[str] = "A"
    tos_basis: ClassVar[str] = (
        "Unusual Whales API Basic plan — $125/mo, "
        "personal research use, https://unusualwhales.com/terms"
    )

    def __init__(self, tickers: list[str] | None = None) -> None:
        self.tickers  = tickers or OPTIONS_WATCHLIST
        self._api_key = os.environ.get("UNUSUAL_WHALES_API_KEY", "")
        if not self._api_key:
            raise RuntimeError("UNUSUAL_WHALES_API_KEY is not set in environment / .env")

    def pull(self, since: datetime, cursor: str | None = None) -> Iterable[Post]:
        observed_at   = datetime.now(timezone.utc)
        resolver      = EntityResolver()
        watchlist_set = set(self.tickers)

        with httpx.Client(
            base_url=UW_BASE,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Accept": "application/json",
            },
            timeout=20.0,
        ) as client:
            # 1. Market-wide flow alerts.
            total = self._ingest_flow_alerts(client, observed_at, resolver, watchlist_set)
            log.info("UW flow-alerts: %d contracts stored", total)
            time.sleep(RATE_LIMIT_SLEEP)

            # 2. Per-ticker expiry breakdown.
            expiry_stored = 0
            for ticker in self.tickers:
                try:
                    stored = self._ingest_expiry_breakdown(client, ticker, observed_at, resolver)
                    expiry_stored += stored
                except Exception as exc:
                    log.warning("UW expiry breakdown failed for %s: %s", ticker, exc)
                time.sleep(RATE_LIMIT_SLEEP)

            log.info("UW expiry breakdown: %d rows stored across %d tickers", expiry_stored, len(self.tickers))

        return iter([])

    # ----- flow alerts -----

    def _ingest_flow_alerts(
        self,
        client: httpx.Client,
        observed_at: datetime,
        resolver: EntityResolver,
        watchlist_set: set,
    ) -> int:
        try:
            resp = client.get("/api/option-trades/flow-alerts")
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as exc:
            log.warning("UW flow-alerts request failed: %s", exc)
            return 0

        alerts = data if isinstance(data, list) else data.get("data", [])
        if not alerts:
            return 0

        stored = 0
        for alert in alerts[:MAX_ALERTS_PER_RUN]:
            ticker = (alert.get("ticker") or "").upper().strip()
            if not ticker or ticker not in watchlist_set:
                continue
            try:
                entity_id = resolver.resolve(
                    module_id="stocks", symbol=ticker, kind="ticker"
                )
                if self._store_flow_alert(alert, ticker, entity_id, observed_at):
                    stored += 1
            except Exception as exc:
                log.warning("UW: failed to store alert for %s: %s", ticker, exc)

        return stored

    def _store_flow_alert(
        self,
        alert: dict,
        ticker: str,
        entity_id: str,
        observed_at: datetime,
    ) -> bool:
        # contract type — "call" or "put" directly in response
        contract_type = (alert.get("type") or "call").lower()
        if contract_type not in ("call", "put"):
            contract_type = "call"

        # sentiment derived from contract type
        sentiment = "bullish" if contract_type == "call" else "bearish"

        # premium filter — skip tiny trades
        premium = _safe_float(alert.get("total_premium"))
        if premium is None or premium < MIN_PREMIUM:
            return False

        strike    = _safe_float(alert.get("strike"))
        volume    = _safe_int(alert.get("volume"))
        oi        = _safe_int(alert.get("open_interest"))
        vol_oi    = _safe_float(alert.get("volume_oi_ratio"))

        expiry_str = alert.get("expiry") or ""
        expiry     = _parse_date(expiry_str)

        ts_str   = alert.get("created_at") or ""
        trade_at = _parse_datetime(ts_str) or observed_at

        # Use UW's own unique id for dedup
        uw_id = alert.get("id") or ""
        if uw_id:
            external_id = f"uw:alert:{uw_id}"
        else:
            id_src      = f"uw:{ticker}:{contract_type}:{strike}:{expiry_str}:{premium}"
            external_id = "uw:" + hashlib.sha256(id_src.encode()).hexdigest()[:16]

        # Use vol_oi_ratio as the unusual_score proxy (higher = more unusual)
        unusual_score = min(100.0, (vol_oi or 0) * 10)

        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO options_flow (
                            time, entity_id, adapter_id, external_id,
                            ticker, expiry, strike, contract_type,
                            sentiment, premium, volume, open_interest,
                            volume_oi_ratio, unusual_score, raw, observed_at
                        )
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (entity_id, time, external_id) DO NOTHING;
                        """,
                        (
                            trade_at, entity_id, self.adapter_id, external_id,
                            ticker, expiry, strike, contract_type,
                            sentiment, premium, volume, oi,
                            vol_oi, unusual_score,
                            __import__("psycopg").types.json.Json(alert),
                            observed_at,
                        ),
                    )
                conn.commit()
            return True
        except Exception as exc:
            log.warning("UW: DB insert failed for %s: %s", ticker, exc)
            return False

    # ----- expiry breakdown -----

    def _ingest_expiry_breakdown(
        self,
        client: httpx.Client,
        ticker: str,
        observed_at: datetime,
        resolver: EntityResolver,
    ) -> int:
        """GET /api/stock/{ticker}/expiry-breakdown.

        Response has: expires, volume, open_interest, chains.
        No call/put split — use aggregate vol/OI ratio as positioning signal.
        High vol/OI across near-term expiries = active positioning = signal.
        """
        resp = client.get(f"/api/stock/{ticker}/expiry-breakdown")
        if resp.status_code == 404:
            return 0
        resp.raise_for_status()
        data = resp.json()

        rows = data if isinstance(data, list) else data.get("data", [])
        if not rows:
            return 0

        # Focus on near-term expiries (next 30 days) where positioning is most meaningful.
        today = observed_at.date()
        near_term_rows = []
        for row in rows:
            exp_str = row.get("expires") or ""
            exp     = _parse_date(exp_str)
            if exp and (exp - today).days <= 30:
                near_term_rows.append(row)

        if not near_term_rows:
            return 0

        total_vol = sum(_safe_int(r.get("volume") or 0) or 0 for r in near_term_rows)
        total_oi  = sum(_safe_int(r.get("open_interest") or 0) or 0 for r in near_term_rows)

        if total_vol == 0 or total_oi == 0:
            return 0

        vol_oi_ratio = round(total_vol / total_oi, 4)

        # Only store if positioning is notable (vol > 20% of OI).
        if vol_oi_ratio < 0.2:
            return 0

        # Neutral sentiment — no call/put data available from this endpoint.
        # The divergence engine will weight this as a low-confidence signal.
        sentiment     = "neutral"
        unusual_score = min(100.0, vol_oi_ratio * 20)

        entity_id = resolver.resolve(
            module_id="stocks", symbol=ticker, kind="ticker"
        )
        external_id = "uw:expiry:" + hashlib.sha256(
            f"{ticker}:{today}:{vol_oi_ratio}".encode()
        ).hexdigest()[:16]

        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO options_flow (
                            time, entity_id, adapter_id, external_id,
                            ticker, expiry, strike, contract_type,
                            sentiment, premium, volume, open_interest,
                            volume_oi_ratio, unusual_score, raw, observed_at
                        )
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (entity_id, time, external_id) DO NOTHING;
                        """,
                        (
                            observed_at, entity_id, self.adapter_id, external_id,
                            ticker, None, None, "call",
                            sentiment, None, total_vol, total_oi,
                            vol_oi_ratio, unusual_score,
                            __import__("psycopg").types.json.Json({
                                "type": "expiry_breakdown_near_term",
                                "vol_oi_ratio": vol_oi_ratio,
                                "total_volume": total_vol,
                                "total_oi": total_oi,
                                "expiry_count": len(near_term_rows),
                            }),
                            observed_at,
                        ),
                    )
                conn.commit()
            log.debug("UW expiry: %s vol/OI=%.2f score=%.1f", ticker, vol_oi_ratio, unusual_score)
            return 1
        except Exception as exc:
            log.warning("UW expiry DB failed for %s: %s", ticker, exc)
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


def _parse_date(s: str) -> date | None:
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y%m%d"):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _parse_datetime(s: str) -> datetime | None:
    if not s:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S"):
        try:
            dt = datetime.strptime(s.strip(), fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    # Try fromisoformat as fallback for fractional seconds
    try:
        return datetime.fromisoformat(s.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
