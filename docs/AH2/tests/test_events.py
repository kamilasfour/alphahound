"""Tests for domain.events: serialization/deserialization + correlation ID."""
import pytest

from domain.events import AH2Event, EventValidationError, SCHEMA_VERSION, new_event


def test_new_event_populates_all_required_fields():
    event = new_event(event_type="TEST_TYPE", source="unit-test", payload={"a": 1})
    assert event.event_type == "TEST_TYPE"
    assert event.source == "unit-test"
    assert event.payload == {"a": 1}
    assert event.schema_version == SCHEMA_VERSION
    assert event.event_id
    assert event.correlation_id
    assert event.created_at


def test_new_event_generates_unique_ids_across_calls():
    e1 = new_event(event_type="T", source="s")
    e2 = new_event(event_type="T", source="s")
    assert e1.event_id != e2.event_id
    assert e1.correlation_id != e2.correlation_id


def test_new_event_accepts_explicit_correlation_id():
    event = new_event(event_type="T", source="s", correlation_id="fixed-correlation-id")
    assert event.correlation_id == "fixed-correlation-id"


def test_new_event_defaults_payload_to_empty_dict():
    event = new_event(event_type="T", source="s")
    assert event.payload == {}


def test_to_json_round_trips_through_from_json():
    original = new_event(event_type="TEST_TYPE", source="unit-test", payload={"x": 1, "y": "two"})
    raw = original.to_json()
    restored = AH2Event.from_json(raw)
    assert restored == original


def test_correlation_id_survives_json_round_trip():
    original = new_event(event_type="TEST_TYPE", source="unit-test")
    restored = AH2Event.from_json(original.to_json())
    assert restored.correlation_id == original.correlation_id


def test_from_json_accepts_bytes_body_like_a_service_bus_message():
    original = new_event(event_type="TEST_TYPE", source="unit-test")
    restored = AH2Event.from_json(original.to_json().encode("utf-8"))
    assert restored == original


def test_from_json_rejects_invalid_json():
    with pytest.raises(EventValidationError):
        AH2Event.from_json("not valid json")


def test_from_json_rejects_non_object_json():
    with pytest.raises(EventValidationError):
        AH2Event.from_json("[1, 2, 3]")


def test_from_dict_rejects_missing_required_field():
    data = new_event(event_type="T", source="s").to_dict()
    del data["correlation_id"]
    with pytest.raises(EventValidationError):
        AH2Event.from_dict(data)


@pytest.mark.parametrize("missing_field", list(AH2Event.REQUIRED_FIELDS))
def test_from_dict_rejects_each_missing_required_field(missing_field):
    data = new_event(event_type="T", source="s", payload={"k": "v"}).to_dict()
    del data[missing_field]
    with pytest.raises(EventValidationError):
        AH2Event.from_dict(data)


def test_from_dict_rejects_non_dict_payload():
    data = new_event(event_type="T", source="s").to_dict()
    data["payload"] = "not-a-dict"
    with pytest.raises(EventValidationError):
        AH2Event.from_dict(data)


def test_from_dict_rejects_non_dict_input():
    with pytest.raises(EventValidationError):
        AH2Event.from_dict(["not", "a", "dict"])
