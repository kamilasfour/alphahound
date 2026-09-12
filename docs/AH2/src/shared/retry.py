"""Small, dependency-free retry helper shared across AH2 infrastructure
code that talks to external systems (HTTP APIs, the database).

Not a general-purpose resilience framework — just enough to satisfy
"retries/timeouts for external calls" without pulling in a new
dependency for three lines of logic.
"""
from __future__ import annotations

import logging
import time
from typing import Callable, TypeVar

T = TypeVar("T")

log = logging.getLogger(__name__)


def retry_with_backoff(
    func: Callable[[], T],
    *,
    attempts: int = 3,
    initial_delay_seconds: float = 1.0,
    backoff_factor: float = 2.0,
    retry_on: tuple[type[BaseException], ...] = (Exception,),
    description: str = "operation",
) -> T:
    """Call `func()`, retrying on failure with exponential backoff.

    Re-raises the last exception if every attempt fails. Only intended
    for idempotent or safely-repeatable operations (a GET request, an
    INSERT guarded by ON CONFLICT) — never wrap something with a
    non-idempotent side effect that could double-fire on a false-negative
    timeout.
    """
    delay = initial_delay_seconds
    last_exc: BaseException | None = None

    for attempt in range(1, attempts + 1):
        try:
            return func()
        except retry_on as exc:
            last_exc = exc
            if attempt == attempts:
                log.warning(
                    "%s failed on final attempt %d/%d: %s", description, attempt, attempts, exc
                )
                raise
            log.warning(
                "%s failed on attempt %d/%d (retrying in %.1fs): %s",
                description, attempt, attempts, delay, exc,
            )
            time.sleep(delay)
            delay *= backoff_factor

    # Unreachable, but keeps type checkers happy.
    assert last_exc is not None
    raise last_exc
