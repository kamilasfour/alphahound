"""Timer-triggered workflow: build the AH2 foundation test event.

Kept free of any azure.functions trigger/binding types so it is fully
unit-testable without the Functions runtime. function_app.py's trigger
handler delegates here rather than embedding this logic directly (per
IMPLEMENTATION_PLAYBOOK.md architecture constraint: "Business logic must
not be embedded directly inside trigger handlers").
"""
from __future__ import annotations

from datetime import datetime, timezone

from domain.events import AH2Event, new_event
from infrastructure.configuration.settings import AH2_SOURCE_NAME

EVENT_TYPE = "AH2_FOUNDATION_TEST_EVENT"


def build_foundation_test_event() -> AH2Event:
    """Construct the STEP 4B foundation test event.

    A fresh correlation_id is generated here — this is the start of the
    correlation chain that must survive publish -> Service Bus -> consume
    unchanged.
    """
    return new_event(
        event_type=EVENT_TYPE,
        source=f"{AH2_SOURCE_NAME}:timer",
        payload={
            "message": "AH2 Step 4B foundation workflow test event",
            "fired_at": datetime.now(timezone.utc).isoformat(),
        },
    )
