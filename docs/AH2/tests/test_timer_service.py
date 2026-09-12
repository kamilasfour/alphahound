"""Tests for application.timer_service (timer handler business logic)."""
from application.timer_service import EVENT_TYPE, build_foundation_test_event
from domain.events import SCHEMA_VERSION


def test_build_foundation_test_event_has_expected_type():
    event = build_foundation_test_event()
    assert event.event_type == EVENT_TYPE


def test_build_foundation_test_event_source_identifies_timer():
    event = build_foundation_test_event()
    assert event.source.endswith(":timer")


def test_build_foundation_test_event_payload_has_message_and_fired_at():
    event = build_foundation_test_event()
    assert "message" in event.payload
    assert "fired_at" in event.payload


def test_build_foundation_test_event_uses_current_schema_version():
    event = build_foundation_test_event()
    assert event.schema_version == SCHEMA_VERSION


def test_build_foundation_test_event_generates_fresh_ids_each_call():
    e1 = build_foundation_test_event()
    e2 = build_foundation_test_event()
    assert e1.event_id != e2.event_id
    assert e1.correlation_id != e2.correlation_id
