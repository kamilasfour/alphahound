"""Tests for application.queue_consumer_service (queue consumer business
logic + failure handling)."""
import pytest

from application.queue_consumer_service import process_foundation_test_message
from application.timer_service import build_foundation_test_event
from domain.events import EventValidationError


def test_process_foundation_test_message_round_trips_the_published_event():
    original = build_foundation_test_event()
    result = process_foundation_test_message(
        raw_body=original.to_json().encode("utf-8"),
        message_id="test-message-id",
        delivery_count=1,
    )
    assert result.event == original
    assert result.message_id == "test-message-id"
    assert result.delivery_count == 1


def test_process_foundation_test_message_preserves_correlation_id_end_to_end():
    original = build_foundation_test_event()
    result = process_foundation_test_message(
        raw_body=original.to_json().encode("utf-8"),
        message_id="m1",
        delivery_count=1,
    )
    assert result.event.correlation_id == original.correlation_id
    assert result.event.event_id == original.event_id


def test_process_foundation_test_message_raises_on_malformed_json_body():
    with pytest.raises(EventValidationError):
        process_foundation_test_message(
            raw_body=b"not json at all",
            message_id="bad-message",
            delivery_count=1,
        )


def test_process_foundation_test_message_raises_on_missing_required_fields():
    incomplete = b'{"event_id": "abc"}'
    with pytest.raises(EventValidationError):
        process_foundation_test_message(
            raw_body=incomplete,
            message_id="incomplete-message",
            delivery_count=2,
        )


def test_process_foundation_test_message_raises_on_empty_body():
    with pytest.raises(EventValidationError):
        process_foundation_test_message(
            raw_body=b"",
            message_id="empty-message",
            delivery_count=1,
        )
