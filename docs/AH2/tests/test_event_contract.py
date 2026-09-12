"""Conformance tests guarding the AH2Event envelope against
docs/AH2/docs/EVENT_CONTRACT.md.

These do not test new behavior — they pin down that the existing
implementation (proven working end-to-end in STEP 4B) continues to match
the finalized contract from STEP 5. A failure here means either the code
drifted from the contract, or the contract needs to be revisited — not
that new functionality is missing.
"""
import re
import uuid
from datetime import datetime

from domain.events import AH2Event, SCHEMA_VERSION, new_event

CONTRACT_REQUIRED_FIELDS = (
    "event_id",
    "event_type",
    "correlation_id",
    "source",
    "created_at",
    "schema_version",
    "payload",
)


def test_envelope_fields_match_the_contract_exactly():
    # EVENT_CONTRACT.md §1: exactly these seven fields, no others.
    assert AH2Event.REQUIRED_FIELDS == CONTRACT_REQUIRED_FIELDS
    event = new_event(event_type="T", source="s")
    assert set(event.to_dict().keys()) == set(CONTRACT_REQUIRED_FIELDS)


def test_schema_version_matches_major_minor_string_format():
    # EVENT_CONTRACT.md §3: "<MAJOR>.<MINOR>" string format.
    assert re.fullmatch(r"\d+\.\d+", SCHEMA_VERSION)


def test_event_id_is_a_valid_uuid4():
    # EVENT_CONTRACT.md §7.
    event = new_event(event_type="T", source="s")
    parsed = uuid.UUID(event.event_id)
    assert parsed.version == 4


def test_correlation_id_is_a_valid_uuid4_when_freshly_generated():
    # EVENT_CONTRACT.md §7 / §8: fresh correlation_id for a chain-starting event.
    event = new_event(event_type="T", source="s")
    parsed = uuid.UUID(event.correlation_id)
    assert parsed.version == 4


def test_correlation_id_can_be_inherited_from_an_upstream_event():
    # EVENT_CONTRACT.md §8: downstream events must carry the upstream
    # correlation_id forward unchanged, not generate a new one.
    upstream = new_event(event_type="UPSTREAM_TYPE", source="s")
    downstream = new_event(
        event_type="DOWNSTREAM_TYPE", source="s2", correlation_id=upstream.correlation_id
    )
    assert downstream.correlation_id == upstream.correlation_id
    assert downstream.event_id != upstream.event_id


def test_created_at_is_timezone_aware_utc_iso8601():
    # EVENT_CONTRACT.md §6: always timezone-aware UTC, never naive.
    event = new_event(event_type="T", source="s")
    parsed = datetime.fromisoformat(event.created_at)
    assert parsed.tzinfo is not None
    assert parsed.utcoffset().total_seconds() == 0


def test_payload_defaults_to_empty_object_not_omitted():
    # EVENT_CONTRACT.md §1 / §10: payload is always a JSON object, even
    # when empty — never omitted or null.
    event = new_event(event_type="T", source="s")
    assert event.payload == {}
    assert isinstance(event.payload, dict)
