"""AH2 PostgreSQL connection helper.

Reads AH2_DATABASE_URL from the environment. In the deployed Function
App, this app setting is a Key Vault reference
(@Microsoft.KeyVault(SecretUri=...)) pointing at a secret in
`ah2-dev-kv` — Azure resolves it into a real environment variable value
automatically at runtime, so this module never touches Key Vault
directly and never sees a literal secret checked into any file.

No secret, connection string, or password is ever hard-coded here.
"""
from __future__ import annotations

import logging
import os

import psycopg2

from shared.retry import retry_with_backoff

log = logging.getLogger(__name__)

CONNECT_TIMEOUT_SECONDS = 10
CONNECT_RETRY_ATTEMPTS = 3


class DatabaseConfigurationError(RuntimeError):
    """Raised when AH2_DATABASE_URL is not configured."""


def get_connection() -> "psycopg2.extensions.connection":
    """Return a new AH2 (alphahound2) database connection, retrying
    transient connection failures with backoff."""
    database_url = os.environ.get("AH2_DATABASE_URL")
    if not database_url:
        raise DatabaseConfigurationError(
            "AH2_DATABASE_URL is not set. In the deployed Function App this "
            "should be a Key Vault reference; locally, set it via .env "
            "(see docs/AH2/docs/MIGRATIONS.md)."
        )

    def _connect():
        return psycopg2.connect(database_url, connect_timeout=CONNECT_TIMEOUT_SECONDS)

    return retry_with_backoff(
        _connect,
        attempts=CONNECT_RETRY_ATTEMPTS,
        retry_on=(psycopg2.OperationalError,),
        description="AH2 database connection",
    )
