"""Request correlation IDs.

Every request gets a correlation ID. If the caller sends a safe ``X-Correlation-ID`` header we
reuse it, otherwise we generate one. The ID is stored in a context variable so log records and
error responses can include it without passing it through every function.
"""

import re
import uuid
from contextvars import ContextVar, Token

CORRELATION_HEADER = "X-Correlation-ID"

# Only accept IDs that are safe to log and echo back (no injection into logs or headers).
_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")

_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def new_correlation_id() -> str:
    return uuid.uuid4().hex


def normalize_correlation_id(incoming: str | None) -> str:
    if incoming and _SAFE_ID.match(incoming):
        return incoming
    return new_correlation_id()


def get_correlation_id() -> str | None:
    return _correlation_id.get()


def set_correlation_id(value: str) -> Token:
    return _correlation_id.set(value)


def reset_correlation_id(token: Token) -> None:
    _correlation_id.reset(token)
