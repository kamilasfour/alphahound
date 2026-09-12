"""Structured logging helpers for AH2 Azure Functions.

Every AH2 log call should route through log_event() and include a
correlation_id (plus other structured context) via the custom_dimensions
extra. The Azure Functions Python worker forwards logging.Logger calls to
Application Insights automatically once APPLICATIONINSIGHTS_CONNECTION_STRING
is configured (already set on ah2-dev-func), and surfaces the
custom_dimensions dict as queryable customDimensions.* fields on the trace,
without requiring a separate JSON log formatter or the App Insights SDK
directly.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def log_event(
    logger: logging.Logger,
    level: int,
    message: str,
    *,
    correlation_id: Optional[str] = None,
    event_id: Optional[str] = None,
    function_name: Optional[str] = None,
    outcome: Optional[str] = None,
    **extra_fields: Any,
) -> None:
    """Emit a structured log record with AH2 tracing fields.

    Fields left as None are omitted from custom_dimensions rather than
    logged as literal "None" strings, keeping Application Insights queries
    clean.
    """
    dimensions: Dict[str, Any] = {}
    if correlation_id is not None:
        dimensions["correlation_id"] = correlation_id
    if event_id is not None:
        dimensions["event_id"] = event_id
    if function_name is not None:
        dimensions["function_name"] = function_name
    if outcome is not None:
        dimensions["outcome"] = outcome
    dimensions.update(extra_fields)
    logger.log(level, message, extra={"custom_dimensions": dimensions})
