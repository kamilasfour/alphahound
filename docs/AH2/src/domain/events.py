"""AH2 domain event envelope.

Defines the standard event envelope used for AH2 Service Bus messages, per
docs/AH2/docs/ARCHITECTURE.md section 7 (event vocabulary) and the STEP 4B
foundation test workflow requirements (docs/AH2/docs/IMPLEMENTATION_PLAYBOOK.md
STEP 5 previews this same envelope shape; STEP 5 itself is not authorized —
this module only implements the envelope needed for the STEP 4B foundation
test event, not the full future event vocabulary).

No trading logic, no PostgreSQL access, no AH1 dependency.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, ClassVar, Dict, Optional, Union

from shared.ids import new_id

SCHEMA_VERSION = "1.0"


class EventValidationError(ValueError):
    """Raised when raw event data is missing required fields or malformed."""


@dataclass(frozen=True)
class AH2Event:
    """The standard AH2 event envelope.

    Required fields, per the STEP 4B authorization:
    event_id, event_type, correlation_id, source, created_at,
    schema_version, payload.
    """

    event_id: str
    event_type: str
    correlation_id: str
    source: str
    created_at: str
    schema_version: str
    payload: Dict[str, Any] = field(default_factory=dict)

    REQUIRED_FIELDS: ClassVar[tuple] = (
        "event_id",
        "event_type",
        "correlation_id",
        "source",
        "created_at",
        "schema_version",
        "payload",
    )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AH2Event":
        if not isinstance(data, dict):
            raise EventValidationError(
                f"Event payload must be a JSON object, got {type(data).__name__}"
            )
        missing = [f for f in cls.REQUIRED_FIELDS if f not in data]
        if missing:
            raise EventValidationError(
                f"Event missing required field(s): {', '.join(missing)}"
            )
        if not isinstance(data["payload"], dict):
            raise EventValidationError("Event 'payload' field must be a JSON object")
        return cls(
            event_id=data["event_id"],
            event_type=data["event_type"],
            correlation_id=data["correlation_id"],
            source=data["source"],
            created_at=data["created_at"],
            schema_version=data["schema_version"],
            payload=data["payload"],
        )

    @classmethod
    def from_json(cls, raw: Union[str, bytes]) -> "AH2Event":
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError) as exc:
            raise EventValidationError(f"Event body is not valid JSON: {exc}") from exc
        return cls.from_dict(data)


def new_event(
    event_type: str,
    source: str,
    payload: Optional[Dict[str, Any]] = None,
    correlation_id: Optional[str] = None,
) -> AH2Event:
    """Construct a new AH2Event.

    Generates event_id and created_at. Generates a fresh correlation_id
    unless the caller supplies one explicitly (e.g. to continue an existing
    correlation chain from an upstream event) — for the STEP 4B timer
    workflow, no upstream correlation exists, so a fresh one is always
    generated at the publish point and must survive unchanged through
    Service Bus to the consumer.
    """
    return AH2Event(
        event_id=new_id(),
        event_type=event_type,
        correlation_id=correlation_id or new_id(),
        source=source,
        created_at=datetime.now(timezone.utc).isoformat(),
        schema_version=SCHEMA_VERSION,
        payload=payload or {},
    )
