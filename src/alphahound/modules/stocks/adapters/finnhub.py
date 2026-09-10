"""Finnhub adapter — social sentiment + news headlines.

Fills the Reddit gap while official Reddit API access is pending.
Pulls two endpoints per ticker:

1. Social Sentiment  /stock/social-sentiment
   Returns Reddit + Twitter mention counts and sentiment scores per day.
   We synthesize one Post per ticker per day as a retail_social signal.

2. Company News  /company-news
   Returns news articles with headlines and summaries.
   Each article becomes one Post in the news_wire source class.

Rate limit: 60 calls/minute (free tier).
At 20 tickers × 2 endpoints = 40 calls per run. Safe.

Env var: FINNHUB_API_KEY
"""
from __future__ import annotations

import hashlib
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import ClassVar, Iterable

import httpx

from alphahound.engine.adapters.base import BaseAdapter
from alphahound.engine.adapters.models import Post

log = logging.getLogger(__name__)

FINNHUB_BASE = "https://finnhub.io/api/v1"
RATE_LIMIT_SLEEP = 1.1  # 60 calls/min = 1 call/sec; 1.1s gives headroom

# Full watchlist — all tickers get news coverage
from alphahound.modules.stocks.watchlist.watchlist import CORE_STOCKS, SECTOR_ETFS, BROAD_ETFS
WATCHLIST = CORE_STOCKS + SECTOR_ETFS + BROAD_ETFS

# How many days back to pull news — pull full week to catch everything
NEWS_LOOKBACK_DAYS = 3


class FinnhubAdapter(BaseAdapter):
    """Pulls social sentiment scores and news headlines from Finnhub."""

    adapter_id: ClassVar[str] = "stocks.finnhub"
    source_class: ClassVar[str] = "retail_social"   # primary class; news posts override per-post
    tier: ClassVar[str] = "C"
    tos_basis: ClassVar[str] = (
        "Finnhub free tier — https://finnhub.io/terms "
        "(personal/non-commercial, attribution required)"
    )

    def __init__(self, tickers: list[str] | None = None) -> None:
        self.tickers = tickers or WATCHLIST
        self._api_key = os.environ.get("FINNHUB_API_KEY", "")
        if not self._api_key:
            raise RuntimeError("FINNHUB_API_KEY is not set in environment / .env")

    # ----- BaseAdapter contract -----

    def pull(self, since: datetime, cursor: str | None = None) -> Iterable[Post]:
        observed_at = datetime.now(timezone.utc)
        today = observed_at.date()
        yesterday = today - timedelta(days=NEWS_LOOKBACK_DAYS)

        with httpx.Client(
            base_url=FINNHUB_BASE,
            params={"token": self._api_key},
            timeout=15.0,
        ) as client:
            for ticker in self.tickers:
                # News only -- social sentiment is 403 on free tier, skip entirely
                news_posts = self._pull_news(client, ticker, observed_at, yesterday, today)
                yield from news_posts
                time.sleep(RATE_LIMIT_SLEEP)

    # ----- social sentiment -----

    def _pull_social_sentiment(
        self,
        client: httpx.Client,
        ticker: str,
        observed_at: datetime,
        today,
    ) -> Post | None:
        """GET /stock/social-sentiment — one synthetic Post per ticker per day."""
        from_date = (today - timedelta(days=2)).strftime("%Y-%m-%d")
        try:
            resp = client.get(
                "/stock/social-sentiment",
                params={"symbol": ticker, "from": from_date},
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as exc:
            log.warning("Finnhub social sentiment failed for %s: %s", ticker, exc)
            return None

        reddit = data.get("reddit", [])
        twitter = data.get("twitter", [])

        if not reddit and not twitter:
            log.debug("Finnhub: no social sentiment data for %s", ticker)
            return None

        # Aggregate the most recent day's data from each platform.
        reddit_mentions   = sum(r.get("mention", 0) for r in reddit)
        reddit_pos        = sum(r.get("positiveScore", 0) for r in reddit) / max(len(reddit), 1)
        reddit_neg        = sum(r.get("negativeScore", 0) for r in reddit) / max(len(reddit), 1)
        twitter_mentions  = sum(t.get("mention", 0) for t in twitter)
        twitter_pos       = sum(t.get("positiveScore", 0) for t in twitter) / max(len(twitter), 1)
        twitter_neg       = sum(t.get("negativeScore", 0) for t in twitter) / max(len(twitter), 1)

        # Synthetic deterministic text for FinBERT scoring.
        text = (
            f"{ticker} social sentiment: "
            f"reddit_mentions={reddit_mentions} reddit_positive={reddit_pos:.3f} reddit_negative={reddit_neg:.3f} "
            f"twitter_mentions={twitter_mentions} twitter_positive={twitter_pos:.3f} twitter_negative={twitter_neg:.3f} "
            f"source=Finnhub:social_sentiment date={today}"
        )

        # One snapshot per ticker per day — deduplicates on re-run.
        external_id = f"finnhub:social:{ticker}:{today}"

        return Post(
            adapter_id=self.adapter_id,
            source_class="retail_social",
            external_id=external_id,
            author_hash=None,
            text=text,
            entity_ids=[ticker],
            observed_at=observed_at,
            published_at=observed_at,
            raw={
                "ticker": ticker,
                "reddit": reddit,
                "twitter": twitter,
                "reddit_mentions": reddit_mentions,
                "twitter_mentions": twitter_mentions,
            },
        )

    # ----- news -----

    def _pull_news(
        self,
        client: httpx.Client,
        ticker: str,
        observed_at: datetime,
        from_date,
        to_date,
    ) -> list[Post]:
        """GET /company-news — one Post per article."""
        try:
            resp = client.get(
                "/company-news",
                params={
                    "symbol": ticker,
                    "from": from_date.strftime("%Y-%m-%d"),
                    "to": to_date.strftime("%Y-%m-%d"),
                },
            )
            resp.raise_for_status()
            articles = resp.json()
        except httpx.HTTPError as exc:
            log.warning("Finnhub news failed for %s: %s", ticker, exc)
            return []

        if not isinstance(articles, list):
            return []

        posts: list[Post] = []
        for article in articles[:100]:   # pull all articles, not just 20
            post = self._article_to_post(article, ticker, observed_at)
            if post is not None:
                posts.append(post)

        log.info("Finnhub: %s → %d news articles", ticker, len(posts))
        return posts

    def _article_to_post(self, article: dict, ticker: str, observed_at: datetime) -> Post | None:
        """Convert one Finnhub news article to a Post."""
        headline = article.get("headline", "").strip()
        summary  = article.get("summary", "").strip()
        source   = article.get("source", "")
        ts       = article.get("datetime")  # Unix timestamp

        if not headline:
            return None

        text = headline
        if summary and summary != headline:
            text = f"{headline}. {summary}"

        # Use article URL or fallback hash as stable external_id.
        url = article.get("url", "")
        if url:
            # Hash the URL so external_id stays short and DB-safe.
            external_id = "finnhub:news:" + hashlib.sha256(url.encode()).hexdigest()[:16]
        else:
            external_id = "finnhub:news:" + hashlib.sha256(text.encode()).hexdigest()[:16]

        # Parse publish timestamp.
        if ts:
            try:
                published_at = datetime.fromtimestamp(int(ts), tz=timezone.utc)
            except (ValueError, OSError):
                published_at = observed_at
        else:
            published_at = observed_at

        return Post(
            adapter_id=self.adapter_id,
            source_class="news_wire",   # news articles are news_wire, not retail_social
            external_id=external_id,
            author_hash=None,
            text=text,
            entity_ids=[ticker],
            observed_at=observed_at,
            published_at=published_at,
            raw={
                "ticker": ticker,
                "headline": headline,
                "summary": summary,
                "source": source,
                "url": url,
                "datetime": ts,
            },
        )
