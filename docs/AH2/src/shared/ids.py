"""Shared ID-generation utility used across AH2 layers."""
from __future__ import annotations

import uuid


def new_id() -> str:
    """Return a new random UUID4 string, used for event_id and correlation_id."""
    return str(uuid.uuid4())
