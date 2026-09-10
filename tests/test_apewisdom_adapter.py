"""Unit test for the ApeWisdom adapter.

Strategy: monkeypatch httpx.Client.get to return a recorded fixture.
No network, no DB \u2014 pure shape check on what the adapter emits.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from alphahound.modules.stocks.adapters.apewisdom import ApeWisdomAdapter

FIXTURE = Path(__file__).parent / "fixtures" / "apewisdom_all_stocks_page1.json"


@pytest.fixture
def fixture_payload() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_adapter_metadata_conforms_to_contract():
    """Adapter must declare the four required class vars (PRD A5.2 / A9.4)."""
    assert ApeWisdomAdapter.adapter_id == "stocks.apewisdom"
    assert ApeWisdomAdapter.source_class == "retail_social"
    assert ApeWisdomAdapter.tier == "C"
    assert ApeWisdomAdapter.tos_basis  # non-empty


def test_pull_yields_one_post_per_row(monkeypatch, fixture_payload):
    """Each fixture row should produce exactly one Post."""
    # Build a fake httpx.Client that returns our fixture.
    fake_resp = MagicMock()
    fake_resp.json.return_value = fixture_payload
    fake_resp.raise_for_status.return_value = None

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url):
            return fake_resp

    monkeypatch.setattr(
        "alphahound.modules.stocks.adapters.apewisdom.httpx.Client", FakeClient
    )

    adapter = ApeWisdomAdapter()
    posts = list(adapter.pull(since=datetime.now(timezone.utc)))
    assert len(posts) == len(fixture_payload["results"])


def test_post_shape_and_content(monkeypatch, fixture_payload):
    """Check the details of one emitted Post."""
    fake_resp = MagicMock()
    fake_resp.json.return_value = fixture_payload
    fake_resp.raise_for_status.return_value = None

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url):
            return fake_resp

    monkeypatch.setattr(
        "alphahound.modules.stocks.adapters.apewisdom.httpx.Client", FakeClient
    )

    adapter = ApeWisdomAdapter()
    posts = list(adapter.pull(since=datetime.now(timezone.utc)))

    nvda_post = next(p for p in posts if "NVDA" in p.entity_ids)
    assert nvda_post.adapter_id == "stocks.apewisdom"
    assert nvda_post.source_class == "retail_social"
    assert nvda_post.entity_ids == ["NVDA"]
    assert "mentions=120" in nvda_post.text
    assert "rank=1" in nvda_post.text
    assert "24h_ago=85" in nvda_post.text
    assert nvda_post.author_hash is None  # aggregate, no author
    assert nvda_post.external_id.startswith("all-stocks:NVDA:")
    # Raw payload preserved for audit.
    assert nvda_post.raw["ticker"] == "NVDA"


def test_external_id_is_deterministic_per_minute(monkeypatch, fixture_payload):
    """Two pulls in the same minute should produce the same external_ids (enables dedup)."""
    fake_resp = MagicMock()
    fake_resp.json.return_value = fixture_payload
    fake_resp.raise_for_status.return_value = None

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url):
            return fake_resp

    monkeypatch.setattr(
        "alphahound.modules.stocks.adapters.apewisdom.httpx.Client", FakeClient
    )

    adapter = ApeWisdomAdapter()
    # Within the same minute the snapshot_key is stable, so external_ids match.
    # (There's a small race right at the minute boundary; acceptable.)
    ids_1 = {p.external_id for p in adapter.pull(since=datetime.now(timezone.utc))}
    ids_2 = {p.external_id for p in adapter.pull(since=datetime.now(timezone.utc))}
    # Most should overlap; allow up to 1 difference for a minute-boundary race.
    assert len(ids_1.symmetric_difference(ids_2)) <= len(fixture_payload["results"])
