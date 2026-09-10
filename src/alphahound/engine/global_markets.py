"""Global markets adapter — overnight Asian + European index levels.

Pulls price and % change for major global indices using Yahoo Finance.
No API key required. Runs once per pipeline cycle.

Indices tracked:
    Asia:   Nikkei 225, Hang Seng, Shanghai Composite, ASX 200, Kospi, Sensex
    Europe: DAX, FTSE 100, CAC 40, Eurostoxx 50, IBEX 35, AEX
    Futures: S&P 500 futures, Nasdaq futures, Dow futures, VIX

Why this matters for divergence:
    Global market direction is the single best pre-market context signal.
    If Asian markets drop 2% overnight and European markets open down 1.5%,
    that is a strong RISK_OFF signal that should:
    1. Shrink position sizes on LONG signals
    2. Strengthen SHORT signals (global confirmation)
    3. Block new LONG entries entirely if severity >= RISK_OFF

    This data feeds into the macro_context scorer which the executor
    already reads to size positions.

Source:
    Yahoo Finance quote endpoint (public, no auth).
    Tickers use Yahoo's global index format: ^N225, ^HSI, ^GDAXI etc.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Index universe
# ---------------------------------------------------------------------------
GLOBAL_INDICES: list[dict] = [
    # Asia
    {"ticker": "^N225",   "name": "Nikkei 225",          "region": "Asia",    "market": "Japan"},
    {"ticker": "^HSI",    "name": "Hang Seng",            "region": "Asia",    "market": "Hong Kong"},
    {"ticker": "000001.SS","name": "Shanghai Composite",  "region": "Asia",    "market": "China"},
    {"ticker": "^AXJO",   "name": "ASX 200",              "region": "Asia",    "market": "Australia"},
    {"ticker": "^KS11",   "name": "KOSPI",                "region": "Asia",    "market": "South Korea"},
    {"ticker": "^BSESN",  "name": "Sensex",               "region": "Asia",    "market": "India"},
    # Europe
    {"ticker": "^GDAXI",  "name": "DAX",                  "region": "Europe",  "market": "Germany"},
    {"ticker": "^FTSE",   "name": "FTSE 100",             "region": "Europe",  "market": "UK"},
    {"ticker": "^FCHI",   "name": "CAC 40",               "region": "Europe",  "market": "France"},
    {"ticker": "^STOXX50E","name": "Eurostoxx 50",        "region": "Europe",  "market": "Europe"},
    {"ticker": "^IBEX",   "name": "IBEX 35",              "region": "Europe",  "market": "Spain"},
    {"ticker": "^AEX",    "name": "AEX",                  "region": "Europe",  "market": "Netherlands"},
    # US Futures (pre-market signal)
    {"ticker": "ES=F",    "name": "S&P 500 Futures",      "region": "Futures", "market": "US"},
    {"ticker": "NQ=F",    "name": "Nasdaq 100 Futures",   "region": "Futures", "market": "US"},
    {"ticker": "YM=F",    "name": "Dow Futures",          "region": "Futures", "market": "US"},
    {"ticker": "RTY=F",   "name": "Russell 2000 Futures", "region": "Futures", "market": "US"},
    # Risk gauges
    {"ticker": "^VIX",    "name": "VIX",                  "region": "Risk",    "market": "US"},
    {"ticker": "^TNX",    "name": "10Y Treasury Yield",   "region": "Risk",    "market": "US"},
    {"ticker": "DX-Y.NYB","name": "Dollar Index (DXY)",   "region": "Risk",    "market": "US"},
    {"ticker": "GC=F",    "name": "Gold Futures",         "region": "Risk",    "market": "Global"},
    {"ticker": "CL=F",    "name": "Crude Oil (WTI)",      "region": "Risk",    "market": "Global"},
]

YAHOO_QUOTE_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
USER_AGENT = "AlphaHound/0.1 (global markets research)"


@dataclass
class GlobalIndexSnapshot:
    ticker:        str
    name:          str
    region:        str
    market:        str
    price:         float | None
    change_pct:    float | None   # % change from prev close
    prev_close:    float | None
    is_open:       bool
    timestamp:     datetime
    error:         str | None = None

    @property
    def direction(self) -> str:
        """UP / DOWN / FLAT based on change_pct."""
        if self.change_pct is None:
            return "UNKNOWN"
        if self.change_pct > 0.2:
            return "UP"
        elif self.change_pct < -0.2:
            return "DOWN"
        return "FLAT"

    @property
    def severity(self) -> str:
        """STRONG / MODERATE / MILD / FLAT based on magnitude."""
        if self.change_pct is None:
            return "UNKNOWN"
        abs_chg = abs(self.change_pct)
        if abs_chg >= 2.0:
            return "STRONG"
        elif abs_chg >= 1.0:
            return "MODERATE"
        elif abs_chg >= 0.3:
            return "MILD"
        return "FLAT"


@dataclass
class GlobalMarketSummary:
    snapshots:          list[GlobalIndexSnapshot]
    asia_verdict:       str   # RISK_ON / NEUTRAL / RISK_OFF
    europe_verdict:     str
    futures_verdict:    str
    overall_verdict:    str
    size_modifier:      float  # 0.5 = half size, 1.0 = full, 0.0 = no longs
    asia_avg_chg:       float
    europe_avg_chg:     float
    futures_avg_chg:    float
    narrative:          str
    generated_at:       datetime


def fetch_global_markets() -> GlobalMarketSummary:
    """Fetch all global indices and compute market verdict."""
    snapshots = []
    with httpx.Client(timeout=10.0, headers={"User-Agent": USER_AGENT}) as client:
        for idx in GLOBAL_INDICES:
            snap = _fetch_one(client, idx)
            snapshots.append(snap)
            time.sleep(0.15)  # gentle rate limiting

    return _compute_summary(snapshots)


def _fetch_one(client: httpx.Client, idx: dict) -> GlobalIndexSnapshot:
    ticker = idx["ticker"]
    now    = datetime.now(timezone.utc)
    try:
        url  = YAHOO_QUOTE_URL.format(ticker=ticker)
        resp = client.get(url, params={"interval": "1d", "range": "2d"})
        resp.raise_for_status()
        data = resp.json()

        result = data.get("chart", {}).get("result", [])
        if not result:
            return GlobalIndexSnapshot(
                ticker=ticker, name=idx["name"], region=idx["region"],
                market=idx["market"], price=None, change_pct=None,
                prev_close=None, is_open=False, timestamp=now,
                error="No data returned",
            )

        meta       = result[0].get("meta", {})
        price      = meta.get("regularMarketPrice")
        prev_close = meta.get("chartPreviousClose") or meta.get("previousClose")
        mkt_state  = meta.get("marketState", "CLOSED")
        is_open    = mkt_state in ("REGULAR", "PRE", "POST")

        change_pct = None
        if price is not None and prev_close and prev_close != 0:
            change_pct = round(((price - prev_close) / prev_close) * 100, 3)

        return GlobalIndexSnapshot(
            ticker=ticker, name=idx["name"], region=idx["region"],
            market=idx["market"],
            price=round(float(price), 2) if price else None,
            change_pct=change_pct,
            prev_close=round(float(prev_close), 2) if prev_close else None,
            is_open=is_open,
            timestamp=now,
        )
    except Exception as exc:
        log.warning("global_markets: failed to fetch %s: %s", ticker, exc)
        return GlobalIndexSnapshot(
            ticker=ticker, name=idx["name"], region=idx["region"],
            market=idx["market"], price=None, change_pct=None,
            prev_close=None, is_open=False, timestamp=now,
            error=str(exc),
        )


def _compute_summary(snapshots: list[GlobalIndexSnapshot]) -> GlobalMarketSummary:
    now = datetime.now(timezone.utc)

    def avg_chg(region: str) -> float:
        vals = [s.change_pct for s in snapshots
                if s.region == region and s.change_pct is not None]
        return round(sum(vals) / len(vals), 3) if vals else 0.0

    def verdict(avg: float) -> str:
        if avg <= -1.5:
            return "RISK_OFF"
        elif avg <= -0.5:
            return "CAUTIOUS"
        elif avg >= 1.5:
            return "RISK_ON"
        elif avg >= 0.3:
            return "POSITIVE"
        return "NEUTRAL"

    asia_avg    = avg_chg("Asia")
    europe_avg  = avg_chg("Europe")
    futures_avg = avg_chg("Futures")

    asia_v    = verdict(asia_avg)
    europe_v  = verdict(europe_avg)
    futures_v = verdict(futures_avg)

    # Overall: futures weighted most heavily (most direct US signal)
    combined = (asia_avg * 0.25) + (europe_avg * 0.35) + (futures_avg * 0.40)
    overall  = verdict(combined)

    # Size modifier for executor
    size_map = {
        "RISK_OFF":  0.0,   # Block all longs
        "CAUTIOUS":  0.5,   # Half size
        "NEUTRAL":   0.75,  # Slight reduction
        "POSITIVE":  1.0,   # Full size
        "RISK_ON":   1.0,   # Full size
    }
    size_modifier = size_map.get(overall, 0.75)

    # Narrative
    parts = []
    if asia_avg != 0:
        parts.append("Asia {}{:.1f}% ({})".format(
            "+" if asia_avg > 0 else "", asia_avg, asia_v))
    if europe_avg != 0:
        parts.append("Europe {}{:.1f}% ({})".format(
            "+" if europe_avg > 0 else "", europe_avg, europe_v))
    if futures_avg != 0:
        parts.append("US Futures {}{:.1f}% ({})".format(
            "+" if futures_avg > 0 else "", futures_avg, futures_v))

    narrative = " · ".join(parts) if parts else "No global data available"
    if overall == "RISK_OFF":
        narrative += " ⚠️ RISK_OFF: Long positions blocked"
    elif overall == "CAUTIOUS":
        narrative += " — position sizes halved"

    return GlobalMarketSummary(
        snapshots=snapshots,
        asia_verdict=asia_v, europe_verdict=europe_v,
        futures_verdict=futures_v, overall_verdict=overall,
        size_modifier=size_modifier,
        asia_avg_chg=asia_avg, europe_avg_chg=europe_avg,
        futures_avg_chg=futures_avg,
        narrative=narrative,
        generated_at=now,
    )


def print_summary(summary: GlobalMarketSummary) -> None:
    """Pretty print for CLI use."""
    print()
    print("=" * 65)
    print("  GLOBAL MARKETS SNAPSHOT  —  {}".format(
        summary.generated_at.strftime("%Y-%m-%d %H:%M UTC")))
    print("=" * 65)

    for region in ["Futures", "Asia", "Europe", "Risk"]:
        snaps = [s for s in summary.snapshots if s.region == region]
        if not snaps:
            continue
        print()
        print("  {}:".format(region.upper()))
        for s in snaps:
            if s.error or s.change_pct is None:
                print("    {:25s}  N/A".format(s.name))
                continue
            arrow  = "▲" if s.change_pct > 0 else ("▼" if s.change_pct < 0 else "—")
            status = "[OPEN]" if s.is_open else "[CLOSED]"
            print("    {:25s}  {:>10,.1f}  {} {:+.2f}%  {}  {}".format(
                s.name, s.price or 0, arrow, s.change_pct, s.severity, status))

    print()
    print("  VERDICTS:")
    print("    Asia:    {:10s}  avg {:+.2f}%".format(summary.asia_verdict, summary.asia_avg_chg))
    print("    Europe:  {:10s}  avg {:+.2f}%".format(summary.europe_verdict, summary.europe_avg_chg))
    print("    Futures: {:10s}  avg {:+.2f}%".format(summary.futures_verdict, summary.futures_avg_chg))
    print()
    print("  OVERALL:  {}  →  size modifier {:.0%}".format(
        summary.overall_verdict, summary.size_modifier))
    print()
    print("  {}".format(summary.narrative))
    print("=" * 65)
    print()
