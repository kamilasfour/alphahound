"""Queue-triggered workflow: deserialize and process the AH2 foundation test event.

Kept free of any azure.functions trigger/binding types so it is fully
unit-testable without the Functions runtime.
"""
from __future__ import annotations

from dataclasses import dataclass

from domain.events import AH2Event, EventValidationError


@dataclass(frozen=True)
class ConsumeResult:
    event: AH2Event
    message_id: str
    delivery_count: int


def process_foundation_test_message(
    raw_body: bytes, message_id: str, delivery_count: int
) -> ConsumeResult:
    """Parse and validate a Service Bus message body into an AH2Event.

    Raises EventValidationError on malformed/incomplete input. The caller
    (the Service Bus trigger handler in function_app.py) is expected to let
    this propagate uncaught — see infrastructure/messaging/service_bus.py
    for why that is the correct retry/dead-letter behavior here, not a
    bug to catch-and-continue around.
    """
    event = AH2Event.from_json(raw_body)
    return ConsumeResult(event=event, message_id=message_id, delivery_count=delivery_count)
