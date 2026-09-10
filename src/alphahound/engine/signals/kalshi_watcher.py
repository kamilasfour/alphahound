"""Kalshi watcher — scans for open stock-related prediction market contracts.

Runs at market open (9:30am ET) and throughout the trading day.
Finds Kalshi contracts relevant to our divergence alert tickers.
Pairs each contract with the current divergence signal to produce
a Kalshi bet recommendation alongside the equity trade recommendation.

How Kalshi stock contracts work:
    - Price level markets: "Will AAPL close above $270 today?"
    - Earnings markets: "Will AAPL beat Q2 2026 earnings estimates?"
    - These open during market hours and close at end of day / earnings date
    - yes_price (cents) = implied probability of YES outcome
    - We bet YES if our signal agrees, NO if it disagrees

Contract matching logic:
    For each active divergence alert ticker:
    1. Search Kalshi events by ticker name keyword
    2. Filter: active markets only, close_time within 7 days
    3. Score relevance: price level contracts vs earnings contracts
    4. Return top match per ticker with EV calculation

Expected value calculation:
    signal_direction = LONG or SHORT from trade_advisor
    if LONG:
        bet_side = YES (market goes up / beats earnings)
        yes_price in cents (e.g. 62 = $0.62 per contract)
        payout = $1.00 per contract if YES resolves
        EV = signal_prob * (1 - yes_price/100) - (1 - signal_prob) * (yes_price/100)
    if SHORT:
        bet_side = NO
        no_price = 100 - yes_price
        EV = signal_prob * (1 - no_price/100) - (1 - signal_prob) * (no_price/100)

Kelly sizing for prediction markets:
    b = (1 - entry_price) / entry_price   (payout odds)
    f* = (b*p - q) / b * HALF_KELLY
    Max contracts = floor(bankroll * f* / entry_price_dollars)
    Hard cap: $200 per Kalshi bet (prediction markets are higher variance)
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import httpx

from alphahound.engine.signals.trade_advisor import Direction, TradeRecommendation

log = logging.getLogger(__name__)

KALSHI_BASE      = "https://api.elections.kalshi.com/trade-api/v2"
RATE_LIMIT_SLEEP = 0.3
MAX_KALSHI_BET   = 200.0   # hard cap per Kalshi position
HALF_KELLY       = 0.5
SEARCH_WINDOW_DAYS = 7     # only look at contracts closing within 7 days


@dataclass
class KalshiOpportunity:
    ticker:          str
    contract_id:     str
    question:        str
    bet_side:        str          # "YES" or "NO"
    entry_price:     float        # cents (0-100)
    yes_price:       float        # current yes_price in cents
    ev:              float        # expected value per dollar staked
    kelly_contracts: int          # suggested number of contracts
    bet_usd:         float        # suggested dollar amount
    signal_prob:     float        # from trade_advisor
    direction:       Direction
    close_time:      datetime | None
    volume_24h:      int | None

    def display(self) -> str:
        side_str   = f"BUY {self.bet_side}"
        close_str  = self.close_time.strftime("%Y-%m-%d %H:%M UTC") if self.close_time else "unknown"
        vol_str    = f"{self.volume_24h:,}" if self.volume_24h else "n/a"
        return (
            f"  Kalshi: {self.ticker} → {side_str} @ {self.entry_price:.0f}¢\n"
            f"    Contract: {self.question[:70]}\n"
            f"    EV: {self.ev:+.3f}  |  Bet: ${self.bet_usd:.0f}  ({self.kelly_contracts} contracts)\n"
            f"    Closes: {close_str}  |  24h volume: {vol_str}"
        )


def scan_opportunities(
    recommendations: list[TradeRecommendation],
    bankroll: float = 5_000.0,
) -> list[KalshiOpportunity]:
    """Scan Kalshi for contracts matching current divergence alert tickers.

    Args:
        recommendations: list of TradeRecommendations from trade_advisor.advise_all()
        bankroll: total account size for sizing calculations

    Returns:
        list of KalshiOpportunity, sorted by EV descending
    """
    if not recommendations:
        return []

    opportunities: list[KalshiOpportunity] = []
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(days=SEARCH_WINDOW_DAYS)

    with httpx.Client(base_url=KALSHI_BASE, timeout=15.0) as client:
        for rec in recommendations:
            if rec.direction == Direction.NO_TRADE:
                continue
            try:
                contracts = _find_contracts(client, rec.ticker, cutoff)
                for contract in contracts:
                    opp = _evaluate_contract(contract, rec, bankroll)
                    if opp is not None and opp.ev > 0:
                        opportunities.append(opp)
                time.sleep(RATE_LIMIT_SLEEP)
            except Exception as exc:
                log.debug("Kalshi scan failed for %s: %s", rec.ticker, exc)

    opportunities.sort(key=lambda o: o.ev, reverse=True)
    log.info("Kalshi watcher: found %d opportunities", len(opportunities))
    return opportunities


def _find_contracts(
    client: httpx.Client,
    ticker: str,
    cutoff: datetime,
) -> list[dict]:
    """Search Kalshi for open markets related to this ticker."""
    found = []

    # Try direct series lookup (KX{TICKER} naming convention).
    series_ticker = f"KX{ticker}"
    try:
        resp = client.get(
            "/markets",
            params={"series_ticker": series_ticker, "status": "open", "limit": 10},
        )
        if resp.status_code == 200:
            data = resp.json()
            markets = data.get("markets", [])
            for m in markets:
                close_time = _parse_dt(m.get("close_time") or m.get("expiration_time"))
                if close_time and close_time <= cutoff:
                    found.append(m)
    except httpx.HTTPError:
        pass

    # Also try keyword search.
    try:
        resp = client.get(
            "/markets",
            params={"status": "open", "limit": 50},
        )
        if resp.status_code == 200:
            data = resp.json()
            for m in data.get("markets", []):
                title = (m.get("title") or "").upper()
                if ticker.upper() in title or f"${ticker.upper()}" in title:
                    close_time = _parse_dt(m.get("close_time") or m.get("expiration_time"))
                    if close_time and close_time <= cutoff:
                        # Avoid duplicates.
                        if not any(f["ticker"] == m["ticker"] for f in found):
                            found.append(m)
    except httpx.HTTPError:
        pass

    return found


def _evaluate_contract(
    market: dict,
    rec: TradeRecommendation,
    bankroll: float,
) -> KalshiOpportunity | None:
    """Calculate EV and sizing for one Kalshi contract vs our signal."""
    yes_price_raw = market.get("yes_bid_dollars") or market.get("last_price_dollars") or "0"
    try:
        yes_price_dollars = float(yes_price_raw)
    except (ValueError, TypeError):
        return None

    # Convert to cents (0-100).
    if yes_price_dollars <= 1.0:
        yes_price = yes_price_dollars * 100
    else:
        yes_price = yes_price_dollars  # already in cents

    if yes_price <= 0 or yes_price >= 100:
        return None

    no_price = 100 - yes_price

    # Determine which side to bet based on signal direction.
    if rec.direction == Direction.LONG:
        bet_side    = "YES"
        entry_price = yes_price
    else:
        bet_side    = "NO"
        entry_price = no_price

    if entry_price <= 0 or entry_price >= 100:
        return None

    # EV calculation.
    entry_frac = entry_price / 100.0
    payout_frac = 1.0 - entry_frac    # profit per dollar staked if correct
    p = rec.signal_prob
    q = 1.0 - p
    ev = p * payout_frac - q * entry_frac

    if ev <= 0:
        return None

    # Kelly sizing for prediction markets.
    b = payout_frac / entry_frac       # payout odds
    kelly_raw  = max(0.0, (b * p - q) / b)
    kelly_half = kelly_raw * HALF_KELLY
    bet_dollars = min(bankroll * kelly_half, MAX_KALSHI_BET)
    contracts   = max(1, int(bet_dollars / entry_frac))
    actual_bet  = round(contracts * entry_frac, 2)

    close_time  = _parse_dt(market.get("close_time") or market.get("expiration_time"))
    volume_24h  = _safe_int(market.get("volume_24h_fp") or market.get("volume_24h"))

    return KalshiOpportunity(
        ticker          = rec.ticker,
        contract_id     = market.get("ticker") or "",
        question        = market.get("title") or market.get("yes_sub_title") or "",
        bet_side        = bet_side,
        entry_price     = round(entry_price, 1),
        yes_price       = round(yes_price, 1),
        ev              = round(ev, 4),
        kelly_contracts = contracts,
        bet_usd         = actual_bet,
        signal_prob     = rec.signal_prob,
        direction       = rec.direction,
        close_time      = close_time,
        volume_24h      = volume_24h,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def _safe_int(val) -> int | None:
    if val is None:
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None
