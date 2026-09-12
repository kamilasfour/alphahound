"""Tests for infrastructure.observability.logging_setup."""
import logging
from unittest.mock import MagicMock

from infrastructure.observability.logging_setup import log_event


def test_log_event_includes_correlation_id_and_event_id_in_custom_dimensions():
    mock_logger = MagicMock(spec=logging.Logger)
    log_event(
        mock_logger,
        logging.INFO,
        "test message",
        correlation_id="corr-123",
        event_id="evt-456",
    )
    mock_logger.log.assert_called_once()
    args, kwargs = mock_logger.log.call_args
    assert args[0] == logging.INFO
    assert args[1] == "test message"
    dims = kwargs["extra"]["custom_dimensions"]
    assert dims["correlation_id"] == "corr-123"
    assert dims["event_id"] == "evt-456"


def test_log_event_omits_none_fields_from_custom_dimensions():
    mock_logger = MagicMock(spec=logging.Logger)
    log_event(mock_logger, logging.INFO, "test", correlation_id=None, event_id=None)
    dims = mock_logger.log.call_args.kwargs["extra"]["custom_dimensions"]
    assert "correlation_id" not in dims
    assert "event_id" not in dims


def test_log_event_passes_through_extra_fields():
    mock_logger = MagicMock(spec=logging.Logger)
    log_event(mock_logger, logging.ERROR, "failure", outcome="validation_failed", message_id="m1", delivery_count=3)
    dims = mock_logger.log.call_args.kwargs["extra"]["custom_dimensions"]
    assert dims["outcome"] == "validation_failed"
    assert dims["message_id"] == "m1"
    assert dims["delivery_count"] == 3
