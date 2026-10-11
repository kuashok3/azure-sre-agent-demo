"""Per-request middleware: correlation ID, duration measurement, access log, last-resort 500.

For every request we:
  1. reuse or create a correlation ID and echo it in the ``X-Correlation-ID`` response header;
  2. measure duration and return it in ``X-Response-Time-Ms``;
  3. write one structured "request completed" log line (except liveness probes);
  4. turn any unhandled exception into a JSON 500 that includes the correlation ID.
"""

import logging
import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from app.common.correlation import (
    CORRELATION_HEADER,
    normalize_correlation_id,
    reset_correlation_id,
    set_correlation_id,
)
from app.common.errors import error_body

logger = logging.getLogger("app.http")

_QUIET_PATHS = {"/health/live"}


def install_request_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_context(request: Request, call_next):
        correlation_id = normalize_correlation_id(request.headers.get(CORRELATION_HEADER))
        token = set_correlation_id(correlation_id)
        started = time.perf_counter()
        try:
            try:
                response = await call_next(request)
            except Exception as exc:  # last resort: unexpected bug or injected http_5xx fault
                span = trace.get_current_span()
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR, type(exc).__name__))
                logger.exception(
                    "Unhandled exception while processing request",
                    extra={"event": "unhandled_exception", "error_type": type(exc).__name__},
                )
                response = JSONResponse(
                    status_code=500,
                    content=error_body("internal_error", "An unexpected error occurred."),
                )
            duration_ms = round((time.perf_counter() - started) * 1000, 1)
            response.headers[CORRELATION_HEADER] = correlation_id
            response.headers["X-Response-Time-Ms"] = str(duration_ms)
            if request.url.path not in _QUIET_PATHS:
                logger.info(
                    "request completed",
                    extra={
                        "event": "http_request",
                        "http_method": request.method,
                        "http_path": request.url.path,
                        "http_status": response.status_code,
                        "duration_ms": duration_ms,
                    },
                )
            return response
        finally:
            reset_correlation_id(token)
