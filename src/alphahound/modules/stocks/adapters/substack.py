"""Substack / analyst RSS adapter — finance newsletter ingestion.

Pulls articles from curated finance newsletters via public RSS feeds.
No auth required. Free for personal research use.

Feed registry is in the substack_feeds DB table.

Ticker extraction uses three methods:
    1. $TICKER notation
    2. ALL-CAPS watchlist symbols (filtered against FALSE_POSITIVE_WORDS)
    3. Company name matching (Apple -> AAPL, Nvidia -> NVDA etc)

Lookback: 168h (7 days) -- newsletters publish weekly, 48h misses most.
"""
from __future__ import annotations

import hashlib
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import ClassVar, Iterable

import httpx

from alphahound.engine.adapters.base import BaseAdapter
from alphahound.engine.adapters.models import Post
from alphahound.engine.storage import get_conn

log = logging.getLogger(__name__)

RATE_LIMIT_SLEEP = 1.5
MAX_ARTICLES_FEED = 50   # pull more articles per feed
MAX_TEXT_CHARS = 4000    # capture full article context
MIN_TEXT_CHARS = 50
LOOKBACK_HOURS = 168

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/xml, text/xml, */*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
}

# Company name -> ticker for outlets that write "Apple" not "$AAPL"
COMPANY_TO_TICKER: dict[str, str] = {
    "apple": "AAPL", "nvidia": "NVDA", "microsoft": "MSFT",
    "alphabet": "GOOGL", "google": "GOOG", "amazon": "AMZN",
    "meta": "META", "tesla": "TSLA", "broadcom": "AVGO",
    "qualcomm": "QCOM", "servicenow": "NOW", "netflix": "NFLX",
    "intel corporation": "INTC", "arm holdings": "ARM",
    "jpmorgan": "JPM", "jp morgan": "JPM", "bank of america": "BAC",
    "goldman sachs": "GS", "goldman": "GS", "morgan stanley": "MS",
    "visa": "V", "mastercard": "MA", "sofi": "SOFI",
    "eli lilly": "LLY", "lilly": "LLY", "unitedhealth": "UNH",
    "pfizer": "PFE", "merck": "MRK", "abbvie": "ABBV",
    "exxon": "XOM", "exxonmobil": "XOM", "chevron": "CVX",
    "walmart": "WMT", "costco": "COST", "target": "TGT",
    "microstrategy": "MSTR", "coinbase": "COIN", "robinhood": "HOOD",
    "s&p 500": "SPY", "s&p500": "SPY", "sp500": "SPY",
    "nasdaq 100": "QQQ", "nasdaq": "QQQ",
    "russell 2000": "IWM", "dow jones": "DIA",
    "treasuries": "TLT", "treasury bonds": "TLT",
    "gold": "GLD", "crude oil": "USO",
    "financial sector": "XLF", "financials": "XLF",
    "technology sector": "XLK", "tech sector": "XLK",
    "energy sector": "XLE", "semiconductors": "SMH",
    "biotech": "XBI", "biotechnology": "XBI",
    "palantir": "PLTR", "shopify": "SHOP",
    "uber": "UBER", "lyft": "LYFT", "roblox": "RBLX",
    "snap": "SNAP", "gamestop": "GME", "blackrock": "BLK",
}

# English words that look like tickers -- exclude from ALL-CAPS matching
# Note: $NOW is still valid (explicit notation), but bare NOW is not
FALSE_POSITIVE_WORDS = {
    "IT", "AT", "BE", "BY", "OR", "IF", "IN", "IS", "AS", "AN",
    "ON", "OF", "TO", "DO", "GO", "NO", "SO", "US", "UP", "AM",
    "PM", "ET", "EX", "RE", "OK", "AI", "TV", "CEO", "CFO", "IPO",
    "NOW", "WELL", "CORE", "PEAK", "BASE", "CASH", "BOND", "RISK",
    "RATE", "DATA", "FUND", "BANK", "BULL", "BEAR", "OPEN", "HIGH",
    "LONG", "SHORT", "CALL", "REAL", "GOLD", "INTEL",
}

WATCHLIST = {
    "AAPL", "NVDA", "TSLA", "AMD",  "AMZN", "MSFT", "META",
    "ARM",  "SNDK", "PLTR", "GME",  "AMC",  "SMCI", "MSTR",
    "COIN", "INTC", "SOFI", "BAC",  "NFLX", "HOOD", "GOOG",
    "GOOGL","AVGO", "NOW",  "QCOM", "QQQ",  "SPY",  "IWM",
    "DIA",  "VTI",  "XLK",  "UBER", "LYFT", "RBLX", "SNAP",
    "SHOP", "SQ",   "USO",  "ORCL", "IBM",  "CMG",  "MA",
    "ADBE", "CVNA", "UNH",  "PYPL", "TSM",  "CAT",  "CVX",
    "MU",   "JPM",  "GS",   "MS",   "V",    "LLY",  "PFE",
    "MRK",  "ABBV", "JNJ",  "COST", "WMT",  "TGT",  "XOM",
    "GLD",  "SLV",  "TLT",  "HYG",  "XLE",  "XLF",  "SMH",
    "XBI",  "GDX",  "EEM",  "EWJ",  "FXI",  "UVXY", "BTC",
    "ETH",  "F",    "BE",   "BLK",
}


class SubstackAdapter(BaseAdapter):
    adapter_id: ClassVar[str] = "stocks.substack"
    source_class: ClassVar[str] = "analyst_curated"
    tier: ClassVar[str] = "B"
    tos_basis: ClassVar[str] = "Public RSS feeds — free, personal research use"

    def pull(self, since: datetime, cursor: str | None = None) -> Iterable[Post]:
        observed_at = datetime.now(timezone.utc)
        lookback_since = observed_at - timedelta(hours=LOOKBACK_HOURS)
        feeds = _load_feeds()
        if not feeds:
            log.warning("Substack: no enabled feeds in substack_feeds table.")
            return

        log.info("Substack: pulling %d feeds (last %dh)", len(feeds), LOOKBACK_HOURS)
        successful = 0

        with httpx.Client(timeout=20.0, follow_redirects=True, headers=HEADERS) as client:
            for feed in feeds:
                try:
                    articles = _fetch_feed(client, feed, lookback_since)
                    count = 0
                    for article in articles[:MAX_ARTICLES_FEED]:
                        for post in _article_to_posts(article, feed, observed_at):
                            yield post
                            count += 1
                    if articles:
                        successful += 1
                    log.info("Substack: %s -> %d articles, %d posts",
                             feed["display_name"], len(articles), count)
                except Exception as exc:
                    log.warning("Substack: failed for %s: %s", feed["display_name"], exc)
                    if "403" in str(exc) or "404" in str(exc):
                        _disable_feed(feed["slug"])
                time.sleep(RATE_LIMIT_SLEEP)

        log.info("Substack: %d/%d feeds successful", successful, len(feeds))


def _load_feeds() -> list[dict]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT slug, display_name, rss_url, author, focus, tier "
                "FROM substack_feeds WHERE enabled = true ORDER BY slug;"
            )
            cols = [d.name for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]


def _disable_feed(slug: str) -> None:
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE substack_feeds SET enabled = false WHERE slug = %s;", (slug,))
            conn.commit()
        log.info("Substack: auto-disabled feed %s (403/404)", slug)
    except Exception as exc:
        log.warning("Substack: failed to disable %s: %s", slug, exc)


def _fetch_feed(client: httpx.Client, feed: dict, since: datetime) -> list[dict]:
    resp = client.get(feed["rss_url"])
    resp.raise_for_status()
    try:
        xml = resp.content.decode("utf-8")
    except UnicodeDecodeError:
        xml = resp.content.decode("latin-1")
    return _parse_rss(xml, feed["slug"], since)


def _parse_rss(xml: str, slug: str, since: datetime) -> list[dict]:
    import xml.etree.ElementTree as ET
    xml = xml.lstrip("\ufeff").strip()
    articles = []
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        log.warning("RSS parse error for %s: %s", slug, exc)
        return []

    ns = {
        "atom":    "http://www.w3.org/2005/Atom",
        "content": "http://purl.org/rss/1.0/modules/content/",
        "dc":      "http://purl.org/dc/elements/1.1/",
    }
    for item in root.findall(".//item"):
        a = _parse_item(item, ns, slug, since)
        if a:
            articles.append(a)
    for entry in root.findall(".//atom:entry", ns):
        a = _parse_entry(entry, ns, slug, since)
        if a:
            articles.append(a)
    return articles


def _parse_item(item, ns, slug, since):
    title    = _text(item, "title") or ""
    desc     = _text(item, "description") or ""
    content  = _text(item, "content:encoded", ns) or desc
    link     = _text(item, "link") or ""
    guid     = _text(item, "guid") or link
    pub_date = _text(item, "pubDate") or ""
    pub_at   = _parse_rss_date(pub_date)
    if pub_at and pub_at < since:
        return None
    return {"title": title.strip(), "text": _clean_html(content or desc),
            "link": link.strip(), "guid": guid.strip(),
            "published_at": pub_at or since, "slug": slug}


def _parse_entry(entry, ns, slug, since):
    title   = _text(entry, "atom:title", ns) or _text(entry, "title") or ""
    content = _text(entry, "atom:content", ns) or _text(entry, "atom:summary", ns) or ""
    link_el = entry.find("atom:link", ns) or entry.find("link")
    link    = link_el.get("href", "") if link_el is not None else ""
    guid    = _text(entry, "atom:id", ns) or _text(entry, "id") or link
    updated = _text(entry, "atom:updated", ns) or _text(entry, "atom:published", ns) or ""
    pub_at  = _parse_iso_date(updated)
    if pub_at and pub_at < since:
        return None
    return {"title": title.strip(), "text": _clean_html(content),
            "link": link.strip(), "guid": guid.strip(),
            "published_at": pub_at or since, "slug": slug}


def _article_to_posts(article, feed, observed_at) -> list[Post]:
    title = article["title"]
    body  = article["text"]
    full_text = title
    if body and len(body) > MIN_TEXT_CHARS:
        full_text = title + ". " + body
    full_text = full_text[:MAX_TEXT_CHARS]
    if len(full_text) < MIN_TEXT_CHARS:
        return []

    tickers = _extract_tickers(full_text)
    if not tickers:
        return []

    base_id = "substack:" + hashlib.sha256(
        (feed["slug"] + ":" + article["guid"]).encode()
    ).hexdigest()[:16]

    return [
        Post(
            adapter_id   = "stocks.substack",
            source_class = "analyst_curated",
            external_id  = base_id + ":" + ticker,
            author_hash  = None,
            text         = full_text,
            entity_ids   = [ticker],
            observed_at  = observed_at,
            published_at = article["published_at"],
            raw          = {
                "slug": feed["slug"], "display_name": feed["display_name"],
                "title": title, "link": article.get("link", ""),
                "ticker": ticker, "focus": feed.get("focus", ""),
            },
        )
        for ticker in tickers
    ]


def _extract_tickers(text: str) -> list[str]:
    found = set()

    # Method 1: explicit $TICKER -- always trusted
    dollar_tickers = re.findall(r'\$([A-Z]{1,5})\b', text)
    for sym in dollar_tickers:
        if sym in WATCHLIST:
            found.add(sym)

    # Method 2: ALL-CAPS symbols -- filter false positives
    allcaps = re.findall(r'\b([A-Z]{2,5})\b', text)
    for sym in allcaps:
        if sym in WATCHLIST and sym not in FALSE_POSITIVE_WORDS:
            found.add(sym)

    # Method 3: company name matching
    text_lower = text.lower()
    for name, ticker in COMPANY_TO_TICKER.items():
        if name in text_lower and ticker in WATCHLIST:
            found.add(ticker)

    return sorted(found)


def _text(el, tag, ns=None):
    child = el.find(tag, ns) if ns else el.find(tag)
    if child is None:
        return None
    return (child.text or "").strip() or None


def _clean_html(html: str) -> str:
    if not html:
        return ""
    text = re.sub(r'<[^>]+>', ' ', html)
    for old, new in [("&amp;","&"),("&lt;","<"),("&gt;",">"),
                     ("&quot;",'"'),("&#39;","'"),("&nbsp;"," ")]:
        text = text.replace(old, new)
    return re.sub(r'\s+', ' ', text).strip()


def _parse_rss_date(s: str) -> datetime | None:
    if not s:
        return None
    try:
        return parsedate_to_datetime(s).astimezone(timezone.utc)
    except Exception:
        return None


def _parse_iso_date(s: str) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None
