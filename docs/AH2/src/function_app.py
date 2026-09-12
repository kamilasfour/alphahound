"""AH2 Step 4B foundation workflow.

Timer Function -> publish AH2 test event -> Azure Service Bus
(ah2-dev-test-queue) -> Queue-triggered Function -> structured success log.

No trading logic. No PostgreSQL access. No AH1 changes.

Both bindings use the identity-based "ServiceBusConnection" app setting
group (ServiceBusConnection__fullyQualifiedNamespace) — the Function App's
system-assigned managed identity holds Azure Service Bus Data Sender and
Azure Service Bus Data Receiver, scoped only to ah2-dev-test-queue (see
docs/AH2/docs/AH2_DEV_ENVIRONMENT.md STEP 4B). No connection string is
configured or used.
"""
import logging
import os
import sys

# This deployment uses WEBSITE_RUN_FROM_PACKAGE with an external blob URL
# rather than the standard func/Kudu deploy path. In that mode the Python
# worker does not reliably put /home/site/wwwroot (this file's own
# directory) on sys.path, so sibling packages (application/, domain/,
# infrastructure/, shared/) fail to import with "No module named
# 'application'". Adding the script directory explicitly is the standard,
# minimal workaround.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import azure.functions as func

from application.queue_consumer_service import process_foundation_test_message
from application.timer_service import build_foundation_test_event
from domain.events import EventValidationError
from infrastructure.messaging.service_bus import (
    QUEUE_NAME_BINDING_EXPRESSION,
    SERVICE_BUS_CONNECTION_SETTING,
)
from infrastructure.observability.logging_setup import get_logger, log_event

app = func.FunctionApp()
logger = get_logger("ah2.foundation")


@app.function_name(name="AH2FoundationTimer")
@app.timer_trigger(schedule="0 */5 * * * *", arg_name="mytimer", run_on_startup=True)
@app.service_bus_queue_output(
    arg_name="outputMessage",
    queue_name=QUEUE_NAME_BINDING_EXPRESSION,
    connection=SERVICE_BUS_CONNECTION_SETTING,
)
def ah2_foundation_timer(mytimer: func.TimerRequest, outputMessage: func.Out[str]) -> None:
    event = build_foundation_test_event()
    outputMessage.set(event.to_json())
    log_event(
        logger,
        logging.INFO,
        f"AH2 foundation test event published (correlation_id={event.correlation_id}, event_id={event.event_id})",
        correlation_id=event.correlation_id,
        event_id=event.event_id,
        function_name="AH2FoundationTimer",
        outcome="published",
        event_type=event.event_type,
    )


@app.function_name(name="AH2FoundationQueueConsumer")
@app.service_bus_queue_trigger(
    arg_name="msg",
    queue_name=QUEUE_NAME_BINDING_EXPRESSION,
    connection=SERVICE_BUS_CONNECTION_SETTING,
)
def ah2_foundation_queue_consumer(msg: func.ServiceBusMessage) -> None:
    message_id = msg.message_id
    delivery_count = msg.delivery_count

    try:
        result = process_foundation_test_message(msg.get_body(), message_id, delivery_count)
    except EventValidationError as exc:
        log_event(
            logger,
            logging.ERROR,
            f"AH2 foundation message failed validation: {exc}",
            function_name="AH2FoundationQueueConsumer",
            outcome="validation_failed",
            message_id=message_id,
            delivery_count=delivery_count,
        )
        raise

    log_event(
        logger,
        logging.INFO,
        f"AH2 foundation test event processed successfully (correlation_id={result.event.correlation_id}, event_id={result.event.event_id})",
        correlation_id=result.event.correlation_id,
        event_id=result.event.event_id,
        function_name="AH2FoundationQueueConsumer",
        outcome="success",
        event_type=result.event.event_type,
        message_id=result.message_id,
        delivery_count=result.delivery_count,
    )
