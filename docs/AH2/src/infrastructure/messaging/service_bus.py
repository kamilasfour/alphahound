"""AH2 Service Bus messaging conventions.

STEP 4B uses Azure Functions' declarative Service Bus bindings
(service_bus_queue_output / service_bus_queue_trigger in function_app.py)
rather than a hand-rolled azure-servicebus SDK client. The binding
extension (via the extension bundle declared in host.json) handles the
actual connection, using the identity-based "ServiceBusConnection" app
setting group (ServiceBusConnection__fullyQualifiedNamespace) — no
connection string, no secret, no azure-servicebus/azure-identity package
dependency.

This module centralizes the naming conventions shared between the
publisher and consumer sides so they cannot drift out of sync, and
documents the retry / dead-letter strategy in one place.

Retry-safe processing / dead-letter strategy
---------------------------------------------
`ah2-dev-test-queue` (see docs/AH2/docs/AH2_DEV_ENVIRONMENT.md STEP 4A) is
configured with maxDeliveryCount=10 and deadLetteringOnMessageExpiration=
True. The consumer (AH2FoundationQueueConsumer in function_app.py) does
not catch and swallow EventValidationError — it logs the failure with
whatever identifying information is available (message_id, delivery_count)
and re-raises. Azure Functions' Service Bus trigger treats an unhandled
exception as processing failure: the message is not completed, so the
Service Bus host redelivers it (up to maxDeliveryCount), after which it is
moved to the queue's dead-letter sub-queue automatically. No custom
dead-letter code is needed for this behavior — it comes from the queue
configuration plus "let real errors propagate," which is why the consumer
must not use a bare except/log/continue pattern for validation failures.
"""
from __future__ import annotations

#: App setting group name used by both the output binding (publisher) and
#: the trigger binding (consumer) in function_app.py. Resolved by the
#: Functions host to ServiceBusConnection__fullyQualifiedNamespace.
SERVICE_BUS_CONNECTION_SETTING = "ServiceBusConnection"

#: Binding expression resolved from the AH2_TEST_QUEUE_NAME app setting,
#: used by both bindings so the queue name is configured once, not
#: hard-coded twice.
QUEUE_NAME_BINDING_EXPRESSION = "%AH2_TEST_QUEUE_NAME%"
