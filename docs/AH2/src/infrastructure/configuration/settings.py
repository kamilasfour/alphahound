"""AH2 foundation configuration.

All configuration is read from environment variables / Azure Function App
settings, matching the "no secrets in code" rule (CLAUDE.md rule 10). The
Service Bus connection itself is identity-based
(ServiceBusConnection__fullyQualifiedNamespace, configured as an app
setting on ah2-dev-func) and is resolved by the Azure Functions Service Bus
extension directly from binding declarations in function_app.py — this
module does not construct or hold any connection string or credential.
"""
from __future__ import annotations

import os

AH2_SOURCE_NAME = os.environ.get("AH2_SOURCE_NAME", "ah2-dev-func")
AH2_TEST_QUEUE_NAME = os.environ.get("AH2_TEST_QUEUE_NAME", "ah2-dev-test-queue")
