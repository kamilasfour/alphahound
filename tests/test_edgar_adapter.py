"""Unit tests for the EDGAR adapter.

Strategy: monkeypatch httpx.Client to return a recorded Atom fixture
for one form type, and empty feeds for the others. No network, no DB.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from alphahound.modules.stocks.adapters.edgar import (
    EdgarAdapter,
    FORM_TYPES,
)

FIXTURE = Path(__file__).parent / "fixtures" / "edgar_13f_latest.xml"
EMPTY_FEED = (
    b'<?xml version="1.0" encoding="UTF-8"?>'
    b'<feed xmlns="http://www.w3.org/2005/Atom">'
    b'<title>Empty</title>'
    b'<updated>2026-04-19T14:30:00-04:00</updated>'
    b'</feed>'
)


@pytest.fixture
def fixture_bytes() -> bytes:
    return FIXTURE.read_bytes()


def test_adapter_metadata_conforms_to_contract():
    """Adapter must declare the four required class vars (PRD A5.2 / A9.4)."""
    assert EdgarAdapter.adapter_id == "stocks.edgar"
    assert EdgarAdapter.source_class == "institutional_flow"
    assert EdgarAdapter.tier == "B"
    assert "SEC.gov" in EdgarAdapter.tos_basis


def test_extract_filer_from_standard_title():
    name, cik = EdgarAdapter._extract_filer(
        "13F-HR - BERKSHIRE HATHAWAY INC (0001067983) (Filer)"
    )
    assert name == "BERKSHIRE HATHAWAY INC"
    assert cik == "0001067983"


def test_extract_filer_handles_lp_punctuation():
    name, cik = EdgarAdapter._extract_filer(
        "13F-HR - PERSHING SQUARE CAPITAL MANAGEMENT, L.P. (0001336528) (Filer)"
    )
    assert name == "PERSHING SQUARE CAPITAL MANAGEMENT, L.P."
    assert cik == "0001336528"


def test_extract_filer_returns_none_on_malformed_title():
    name, cik = EdgarAdapter._extract_filer("junk without parens")
    assert name is None
    assert cik is None


def test_canonicalize_filer_uses_cik():
    """Filer canonical symbol must be CIK-based so rebrands don't duplicate entities."""
    assert EdgarAdapter._canonicalize_filer("BERKSHIRE", "0001067983") == "CIK:0001067983"
    assert EdgarAdapter._canonicalize_filer("OTHER NAME", "0001067983") == "CIK:0001067983"


def test_pull_yields_post_per_entry(monkeypatch, fixture_bytes):
    """Fixture has 3 13F entries; adapter should yield 3 Posts from the 13F call and 0 from the others."""
    # Build a fake response that returns the fixture for the 13F-HR URL and empty
    # feeds for the other form types.
    def fake_get(self, url, *args, **kwargs):
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        if "type=13F-HR" in url:
            resp.content = fixture_bytes
        else:
            resp.content = EMPTY_FEED
        return resp

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        get = fake_get

    monkeypatch.setattr(
        "alphahound.modules.stocks.adapters.edgar.httpx.Client", FakeClient
    )
    # Short-circuit the rate-limit sleep so tests run instantly.
    monkeypatch.setattr(
        "alphahound.modules.stocks.adapters.edgar.time.sleep", lambda _: None
    )

    adapter = EdgarAdapter()
    posts = list(adapter.pull(since=datetime.now(timezone.utc)))
    assert len(posts) == 3


def test_post_shape_and_content(monkeypatch, fixture_bytes):
    """Check one emitted Post in detail."""

    def fake_get(self, url, *args, **kwargs):
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.content = fixture_bytes if "type=13F-HR" in url else EMPTY_FEED
        return resp

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        get = fake_get

    monkeypatch.setattr("alphahound.modules.stocks.adapters.edgar.httpx.Client", FakeClient)
    monkeypatch.setattr("alphahound.modules.stocks.adapters.edgar.time.sleep", lambda _: None)

    adapter = EdgarAdapter()
    posts = list(adapter.pull(since=datetime.now(timezone.utc)))

    berkshire = next(p for p in posts if "0001067983" in p.entity_ids[0])
    assert berkshire.adapter_id == "stocks.edgar"
    assert berkshire.source_class == "institutional_flow"
    assert berkshire.entity_ids == ["CIK:0001067983"]
    assert berkshire.external_id.startswith("edgar:0001067983-26-000045")
    assert "BERKSHIRE HATHAWAY INC" in berkshire.text
    assert "CIK 0001067983" in berkshire.text
    assert "13F-HR" in berkshire.text
    # Author hash is always None for EDGAR filings (filer identity is public).
    assert berkshire.author_hash is None
    # Raw payload preserved for audit.
    assert berkshire.raw["cik"] == "0001067983"
    assert berkshire.raw["filer_name"] == "BERKSHIRE HATHAWAY INC"


def test_http_error_skips_form_without_raising(monkeypatch, fixture_bytes):
    """A 500 error on one form type must NOT kill the whole pull."""
    import httpx

    def fake_get(self, url, *args, **kwargs):
        resp = MagicMock()
        if "type=13F-HR" in url:
            resp.content = fixture_bytes
            resp.raise_for_status.return_value = None
        else:
            # Simulate a failing call for all other form types.
            resp.raise_for_status.side_effect = httpx.HTTPError("boom")
        return resp

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        get = fake_get

    monkeypatch.setattr("alphahound.modules.stocks.adapters.edgar.httpx.Client", FakeClient)
    monkeypatch.setattr("alphahound.modules.stocks.adapters.edgar.time.sleep", lambda _: None)

    adapter = EdgarAdapter()
    posts = list(adapter.pull(since=datetime.now(timezone.utc)))
    # 13F succeeded -> 3 posts. Others errored out gracefully -> 0 posts.
    assert len(posts) == 3


def test_form_types_defined():
    """All four target form types must be configured."""
    assert "13F-HR" in FORM_TYPES
    assert "SC 13D" in FORM_TYPES
    assert "SC 13G" in FORM_TYPES
    assert "Form 4" in FORM_TYPES
