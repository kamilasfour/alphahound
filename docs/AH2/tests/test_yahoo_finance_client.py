"""Tests for infrastructure.sources.yahoo_finance_client — RSS parsing,
normalization, deterministic source IDs, and malformed/partial response
handling. No real network access — uses httpx.MockTransport.
"""
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import httpx

from infrastructure.sources.yahoo_finance_client import _fetch_ticker, _item_to_article

SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Yahoo Finance</title>
    <item>
      <title>Apple shares rise on strong earnings</title>
      <description>&lt;p&gt;Apple Inc. reported strong quarterly earnings.&lt;/p&gt;</description>
      <guid>guid-12345</guid>
      <pubDate>Sat, 12 Sep 2026 10:00:00 GMT</pubDate>
      <link>https://finance.yahoo.com/news/apple-1</link>
    </item>
    <item>
      <title>Apple announces new product</title>
      <guid>guid-67890</guid>
      <pubDate>Sat, 12 Sep 2026 11:00:00 GMT</pubDate>
      <link>https://finance.yahoo.com/news/apple-2</link>
    </item>
  </channel>
</rss>"""


def _make_client(response_content: bytes, status_code: int = 200) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, content=response_content)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_fetch_ticker_parses_all_items():
    client = _make_client(SAMPLE_RSS.encode())
    observed_at = datetime.now(timezone.utc)
    articles = list(_fetch_ticker(client, "AAPL", observed_at))
    assert len(articles) == 2
    assert articles[0].ticker == "AAPL"
    assert articles[0].guid == "guid-12345"
    assert articles[0].title == "Apple shares rise on strong earnings"


def test_fetch_ticker_strips_html_from_description():
    client = _make_client(SAMPLE_RSS.encode())
    observed_at = datetime.now(timezone.utc)
    articles = list(_fetch_ticker(client, "AAPL", observed_at))
    assert "<p>" not in articles[0].description
    assert articles[0].description == "Apple Inc. reported strong quarterly earnings."


def test_fetch_ticker_combines_title_and_description_into_text():
    client = _make_client(SAMPLE_RSS.encode())
    observed_at = datetime.now(timezone.utc)
    articles = list(_fetch_ticker(client, "AAPL", observed_at))
    assert articles[0].text.startswith("Apple shares rise on strong earnings.")
    assert "reported strong quarterly earnings" in articles[0].text


def test_fetch_ticker_preserves_published_at_from_pubdate():
    client = _make_client(SAMPLE_RSS.encode())
    observed_at = datetime.now(timezone.utc)
    articles = list(_fetch_ticker(client, "AAPL", observed_at))
    assert (articles[0].published_at.year, articles[0].published_at.month, articles[0].published_at.day) == (
        2026, 9, 12,
    )
    assert articles[0].published_at.hour == 10


def test_fetch_ticker_handles_item_with_no_description():
    client = _make_client(SAMPLE_RSS.encode())
    observed_at = datetime.now(timezone.utc)
    articles = list(_fetch_ticker(client, "AAPL", observed_at))
    assert articles[1].description == ""
    assert articles[1].text == "Apple announces new product"


def test_source_record_id_is_deterministic_per_ticker_and_guid():
    client = _make_client(SAMPLE_RSS.encode())
    observed_at = datetime.now(timezone.utc)
    articles = list(_fetch_ticker(client, "AAPL", observed_at))
    assert articles[0].source_record_id == "AAPL:guid-12345"
    assert articles[1].source_record_id == "AAPL:guid-67890"


def test_fetch_ticker_returns_empty_for_404():
    client = _make_client(b"", status_code=404)
    observed_at = datetime.now(timezone.utc)
    articles = list(_fetch_ticker(client, "NOSUCHTICKER", observed_at))
    assert articles == []


def test_fetch_ticker_handles_malformed_xml_gracefully():
    client = _make_client(b"<rss><channel><item><title>Broken")
    observed_at = datetime.now(timezone.utc)
    articles = list(_fetch_ticker(client, "AAPL", observed_at))
    assert articles == []


def test_fetch_ticker_handles_missing_channel_gracefully():
    client = _make_client(b"<rss></rss>")
    observed_at = datetime.now(timezone.utc)
    articles = list(_fetch_ticker(client, "AAPL", observed_at))
    assert articles == []


def test_item_to_article_returns_none_when_title_missing():
    item = ET.fromstring("<item><guid>g1</guid></item>")
    observed_at = datetime.now(timezone.utc)
    assert _item_to_article(item, "AAPL", observed_at) is None


def test_item_to_article_returns_none_when_title_is_blank():
    item = ET.fromstring("<item><title>   </title><guid>g1</guid></item>")
    observed_at = datetime.now(timezone.utc)
    assert _item_to_article(item, "AAPL", observed_at) is None


def test_item_to_article_falls_back_to_deterministic_hash_guid_when_guid_missing():
    xml = "<item><title>Some headline with no guid</title></item>"
    observed_at = datetime.now(timezone.utc)
    article = _item_to_article(ET.fromstring(xml), "AAPL", observed_at)
    assert article is not None
    assert len(article.guid) == 16
    article2 = _item_to_article(ET.fromstring(xml), "AAPL", observed_at)
    assert article.guid == article2.guid  # deterministic, not random


def test_item_to_article_uses_observed_at_when_pubdate_missing():
    xml = "<item><title>No pub date here</title><guid>g2</guid></item>"
    observed_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    article = _item_to_article(ET.fromstring(xml), "AAPL", observed_at)
    assert article.published_at == observed_at


def test_item_to_article_uses_observed_at_when_pubdate_unparseable():
    xml = "<item><title>Bad date</title><guid>g3</guid><pubDate>not a date</pubDate></item>"
    observed_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    article = _item_to_article(ET.fromstring(xml), "AAPL", observed_at)
    assert article.published_at == observed_at


def test_item_to_article_uppercases_ticker():
    xml = "<item><title>Headline</title><guid>g4</guid></item>"
    observed_at = datetime.now(timezone.utc)
    article = _item_to_article(ET.fromstring(xml), "aapl", observed_at)
    assert article.ticker == "AAPL"
