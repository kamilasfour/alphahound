"""Core data shapes produced by every adapter.

A Post is the normalized unit the engine stores and scores. Adapters
convert source-native JSON into Posts in their pull() method.
"""
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


SourceClass = Literal[
    "retail_social",
    "institutional_flow",
    "options",
    "prediction_market",
    "analyst_curated",
    "news_wire",
]


class Post(BaseModel):
    """Normalized post yielded by BaseAdapter.pull().

    See PRD v1.2 A5.2 (adapter contract) and A9.2 (PII: author_hash is
    SHA-256 + per-module salt, never the raw username).
    """

    adapter_id: str = Field(..., description="e.g. 'stocks.apewisdom'")
    source_class: SourceClass
    external_id: str = Field(..., description="Source-native unique id")
    author_hash: str | None = Field(None, description="SHA-256(salt + author), never raw username")
    text: str
    entity_ids: list[str] = Field(default_factory=list, description="Canonical entity IDs mentioned")
    observed_at: datetime = Field(..., description="UTC time the adapter pulled this")
    published_at: datetime = Field(..., description="UTC time the source claims it was created")
    raw: dict[str, Any] = Field(default_factory=dict, description="Source-native payload for audit")
