"""Alpha Vantage adapter — earnings transcripts (primary) + news sentiment (manual only).

RATE LIMIT NOTE: Alpha Vantage free tier = 25 calls/day total.
At 20 tickers × 2 endpoints = 40 calls, a full run exhausts the daily quota instantly.

Usage strategy:
  - Default mode: transcripts-only (18 tickers = 18 calls/run). Run manually ~once/week.
    Transcripts don't change every 15 minutes — quarterly data.
  - News mode: disabled from scheduled ingest. Use only if AV plan is upgraded.
  - Add --transcripts-only flag to CLI if needed for manual runs.

  alphahound ingest --source alpha_vantage             # transcripts only (18 calls)
  alphahound ingest --source alpha_vantage --av-news   # news + transcripts (40 calls, burns quota)

Earnings transcripts are the first data in the analyst_curated source class.
Split into 512-token chunks so FinBERT can score each segment independently.

Env var: ALPHA_VANTAGE_API_KEY
"""
from __future__ import annotations

import hashlib
import logging
import os
import time
from datetime import datetime, timezone
from typing import ClassVar, Iterable

import httpx

from alphahound.engine.adapters.base import BaseAdapter
from alphahound.engine.adapters.models import Post

log = logging.getLogger(__name__)

AV_BASE = "https://www.alphavantage.co/query"
RATE_LIMIT_SLEEP = 2.0   # conservative — free tier is 25 calls/day, not per minute

# FinBERT max input is 512 tokens. At ~4 chars/token, 400 tokens ≈ 1,600 chars.
# We chunk at 1,500 chars to stay comfortably under with punctuation overhead.
TRANSCRIPT_CHUNK_SIZE = 1500

# Most recent earnings quarter to pull.
# Update manually each quarter.
TRANSCRIPT_YEAR    = 2025
TRANSCRIPT_QUARTER = 4     # Q4 2025

# Transcripts only for tickers with meaningful earnings calls.
# Excludes meme stocks (GME, AMC) — their calls have no analyst content.
TRANSCRIPT_WATCHLIST = [
    "AAPL", "NVDA", "TSLA", "AMD", "AMZN", "MSFT", "META",
    "ARM", "BE", "SNDK", "PLTR", "SMCI",
    "MSTR", "COIN", "INTC", "SOFI", "F", "BAC",
]

NEWS_WATCHLIST = [
    "AAPL", "NVDA", "TSLA", "AMD", "AMZN", "MSFT", "META",
    "ARM", "BE", "SNDK", "PLTR", "GME", "AMC", "SMCI",
    "MSTR", "COIN", "INTC", "SOFI", "F", "BAC",
]


class AlphaVantageAdapter(BaseAdapter):
    """Pulls earnings transcripts (and optionally news) from Alpha Vantage.

    Default: transcripts only (18 calls/run — fits within 25/day free quota
    when run manually ~once per week).

    Set include_news=True only for manual one-off runs or if on a paid plan.
    """

    adapter_id: ClassVar[str] = "stocks.alpha_vantage"
    source_class: ClassVar[str] = "analyst_curated"
    tier: ClassVar[str] = "B"
    tos_basis: ClassVar[str] = (
        "Alpha Vantage free tier — https://www.alphavantage.co/terms_of_service/ "
        "(personal research use, Stage 1 only)"
    )

    def __init__(
        self,
        transcript_tickers: list[str] | None = None,
        news_tickers: list[str] | None = None,
        include_news: bool = False,
    ) -> None:
        self.transcript_tickers = transcript_tickers or TRANSCRIPT_WATCHLIST
        self.news_tickers       = news_tickers or NEWS_WATCHLIST
        self.include_news       = include_news
        self._api_key = os.environ.get("ALPHA_VANTAGE_API_KEY", "")
        if not self._api_key:
            raise RuntimeError("ALPHA_VANTAGE_API_KEY is not set in environment / .env")

    # ----- BaseAdapter contract -----

    def pull(self, since: datetime, cursor: str | None = None) -> Iterable[Post]:
        observed_at = datetime.now(timezone.utc)

        with httpx.Client(timeout=30.0) as client:
            # News sentiment — disabled by default to protect daily quota.
            if self.include_news:
                log.warning(
                    "AV news mode enabled — will use %d of 25 daily calls for news.",
                    len(self.news_tickers),
                )
                for ticker in self.news_tickers:
                    yield from self._pull_news_sentiment(client, ticker, observed_at)
                    time.sleep(RATE_LIMIT_SLEEP)

            # Earnings transcripts — primary value, run once per week manually.
            log.info(
                "AV pulling earnings transcripts for %d tickers (Q%d %d).",
                len(self.transcript_tickers), TRANSCRIPT_QUARTER, TRANSCRIPT_YEAR,
            )
            for ticker in self.transcript_tickers:
                yield from self._pull_earnings_transcript(client, ticker, observed_at)
                time.sleep(RATE_LIMIT_SLEEP)

    # ----- news sentiment -----

    def _pull_news_sentiment(
        self,
        client: httpx.Client,
        ticker: str,
        observed_at: datetime,
    ) -> list[Post]:
        """GET NEWS_SENTIMENT — one Post per article."""
        try:
            resp = client.get(
                AV_BASE,
                params={
                    "function": "NEWS_SENTIMENT",
                    "tickers": ticker,
                    "limit": 20,
                    "apikey": self._api_key,
                },
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as exc:
            log.warning("AV news sentiment failed for %s: %s", ticker, exc)
            return []

        if "Information" in data:
            log.warning("AV rate limit hit (news): %s", data["Information"][:80])
            return []

        posts = [
            self._article_to_post(a, ticker, observed_at)
            for a in data.get("feed", [])[:20]
        ]
        posts = [p for p in posts if p is not None]
        log.info("AV news: %s → %d articles", ticker, len(posts))
        return posts

    def _article_to_post(
        self, article: dict, ticker: str, observed_at: datetime
    ) -> Post | None:
        title    = article.get("title", "").strip()
        summary  = article.get("summary", "").strip()
        url      = article.get("url", "")
        time_str = article.get("time_published", "")
        av_label = article.get("overall_sentiment_label", "")
        av_score = article.get("overall_sentiment_score", None)

        if not title:
            return None

        text = title
        if summary and summary != title:
            text = f"{title}. {summary}"
        if av_label:
            text = f"{text} [AV_sentiment={av_label}]"

        external_id = (
            "av:news:" + hashlib.sha256(url.encode()).hexdigest()[:16]
            if url
            else "av:news:" + hashlib.sha256(text.encode()).hexdigest()[:16]
        )
        published_at = _parse_av_timestamp(time_str) or observed_at

        return Post(
            adapter_id=self.adapter_id,
            source_class="news_wire",
            external_id=external_id,
            author_hash=None,
            text=text,
            entity_ids=[ticker],
            observed_at=observed_at,
            published_at=published_at,
            raw={
                "ticker": ticker,
                "title": title,
                "summary": summary,
                "url": url,
                "av_sentiment_label": av_label,
                "av_sentiment_score": av_score,
                "time_published": time_str,
            },
        )

    # ----- earnings transcripts -----

    def _pull_earnings_transcript(
        self,
        client: httpx.Client,
        ticker: str,
        observed_at: datetime,
    ) -> list[Post]:
        """GET EARNINGS_CALL_TRANSCRIPT — chunked into FinBERT-sized Posts."""
        try:
            resp = client.get(
                AV_BASE,
                params={
                    "function": "EARNINGS_CALL_TRANSCRIPT",
                    "symbol": ticker,
                    "year": TRANSCRIPT_YEAR,
                    "quarter": TRANSCRIPT_QUARTER,
                    "apikey": self._api_key,
                },
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as exc:
            log.warning("AV transcript failed for %s: %s", ticker, exc)
            return []

        if "Information" in data:
            log.warning("AV rate limit hit (transcript): %s", data["Information"][:80])
            return []

        transcript_text = data.get("transcript", "")
        if not transcript_text:
            log.debug("AV: no transcript for %s Q%d %d", ticker, TRANSCRIPT_QUARTER, TRANSCRIPT_YEAR)
            return []

        chunks = _chunk_text(transcript_text, TRANSCRIPT_CHUNK_SIZE)
        posts = []

        for i, chunk in enumerate(chunks):
            chunk_hash  = hashlib.sha256(chunk.encode()).hexdigest()[:12]
            external_id = f"av:transcript:{ticker}:{TRANSCRIPT_YEAR}Q{TRANSCRIPT_QUARTER}:{i}:{chunk_hash}"

            posts.append(Post(
                adapter_id=self.adapter_id,
                source_class="analyst_curated",
                external_id=external_id,
                author_hash=None,
                text=chunk,
                entity_ids=[ticker],
                observed_at=observed_at,
                published_at=observed_at,
                raw={
                    "ticker": ticker,
                    "year": TRANSCRIPT_YEAR,
                    "quarter": TRANSCRIPT_QUARTER,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                },
            ))

        log.info(
            "AV transcript: %s Q%d %d → %d chunks",
            ticker, TRANSCRIPT_QUARTER, TRANSCRIPT_YEAR, len(posts),
        )
        return posts


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_av_timestamp(ts: str) -> datetime | None:
    """Parse Alpha Vantage timestamp: '20260429T143000' -> datetime."""
    if not ts or len(ts) < 15:
        return None
    try:
        return datetime.strptime(ts[:15], "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _chunk_text(text: str, chunk_size: int) -> list[str]:
    """Split text into ≤chunk_size character chunks on sentence boundaries."""
    if len(text) <= chunk_size:
        return [text.strip()] if text.strip() else []

    chunks: list[str] = []
    while text:
        if len(text) <= chunk_size:
            if text.strip():
                chunks.append(text.strip())
            break
        split_at = text.rfind(". ", 0, chunk_size)
        if split_at == -1:
            split_at = chunk_size
        else:
            split_at += 1
        chunk = text[:split_at].strip()
        if chunk:
            chunks.append(chunk)
        text = text[split_at:].lstrip()

    return chunks
