"""AH2 Function App — foundation workflow (STEP 4B) + Yahoo Finance
ingestion (STEP 7B).

Foundation workflow (STEP 4B):
  Timer -> publish AH2 test event -> Service Bus (ah2-dev-test-queue) ->
  Queue-triggered Function -> structured success log.

Yahoo Finance ingestion (STEP 7B):
  Timer -> Yahoo Finance RSS -> normalize -> alphahound2.raw_source_events
  -> alphahound2.evidence -> alphahound2.audit_events (append-only) ->
  DATA_RECEIVED -> Service Bus (same queue) -> the same queue consumer
  verifies receipt.

No trading logic. No probability logic. No AH1 changes.

Both timers' Service Bus bindings use the identity-based
"ServiceBusConnection" app setting group
(ServiceBusConnection__fullyQualifiedNamespace) — the Function App's
system-assigned managed identity holds Azure Service Bus Data Sender and
Azure Service Bus Data Receiver, scoped only to ah2-dev-test-queue (see
docs/AH2/docs/AH2_DEV_ENVIRONMENT.md STEP 4B). No connection string is
configured or used for Service Bus.

The Yahoo Finance timer also connects to PostgreSQL (alphahound2) via
AH2_DATABASE_URL, a Key Vault reference resolved automatically into a
real environment variable by the platform — see
docs/AH2/docs/AH2_DEV_ENVIRONMENT.md STEP 7B and
infrastructure/db/connection.py. No password is stored in this repo.
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
from application.yahoo_ingestion_service import run_yahoo_ingestion
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


@app.function_name(name="AH2YahooFinanceTimer")
@app.timer_trigger(schedule="0 */15 * * * *", arg_name="mytimer", run_on_startup=True)
@app.service_bus_queue_output(
    arg_name="outputMessages",
    queue_name=QUEUE_NAME_BINDING_EXPRESSION,
    connection=SERVICE_BUS_CONNECTION_SETTING,
    cardinality="many",
)
def ah2_yahoo_finance_timer(mytimer: func.TimerRequest, outputMessages: func.Out[str]) -> None:
    """STEP 7B: Timer -> Yahoo Finance -> normalize -> raw_source_events
    -> evidence -> audit_events -> DATA_RECEIVED -> Service Bus.

    Thin trigger handler: all business logic lives in
    application.yahoo_ingestion_service.run_yahoo_ingestion(), which
    also owns the idempotency boundary (duplicate articles never reach
    this point as an event to publish).
    """
    result = run_yahoo_ingestion()

    if result.events_to_publish:
        outputMessages.set([event.to_json() for event in result.events_to_publish])

    for event in result.events_to_publish:
        log_event(
            logger,
            logging.INFO,
            f"AH2 DATA_RECEIVED event published (correlation_id={event.correlation_id}, event_id={event.event_id})",
            correlation_id=event.correlation_id,
            event_id=event.event_id,
            function_name="AH2YahooFinanceTimer",
            outcome="published",
            event_type=event.event_type,
            ticker=event.payload.get("ticker"),
        )

    log_event(
        logger,
        logging.INFO,
        (
            f"AH2 Yahoo Finance ingestion run complete: "
            f"new={result.new_count} duplicate={result.duplicate_count} error={result.error_count}"
        ),
        function_name="AH2YahooFinanceTimer",
        outcome="run_complete",
        new_count=result.new_count,
        duplicate_count=result.duplicate_count,
        error_count=result.error_count,
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
        (
            f"AH2 {result.event.event_type} event received and verified "
            f"(correlation_id={result.event.correlation_id}, event_id={result.event.event_id})"
        ),
        correlation_id=result.event.correlation_id,
        event_id=result.event.event_id,
        function_name="AH2FoundationQueueConsumer",
        outcome="success",
        event_type=result.event.event_type,
        message_id=result.message_id,
        delivery_count=result.delivery_count,
    )
