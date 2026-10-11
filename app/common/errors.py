"""Error model shared by both services.

Expected failures raise ``AppError`` subclasses with an HTTP status and a stable ``error`` code.
Every error response has the same JSON shape so clients and the SRE Agent can rely on it:

    {"error": "database_unavailable", "message": "...", "correlation_id": "..."}
"""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from opentelemetry import trace

from app.common.correlation import get_correlation_id

logger = logging.getLogger("app.errors")


class AppError(Exception):
    status_code: int = 500
    error_code: str = "internal_error"

    def __init__(
        self, message: str, *, status_code: int | None = None, error_code: str | None = None
    ) -> None:
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        if error_code is not None:
            self.error_code = error_code


class InjectedFaultError(Exception):
    """Raised by the http_5xx fault. Deliberately NOT an AppError: it behaves like a real bug."""


def error_body(error_code: str, message: str) -> dict[str, str | None]:
    return {"error": error_code, "message": message, "correlation_id": get_correlation_id()}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        if exc.status_code >= 500:
            # Server-side failure: attach to the request span so it shows in AppExceptions.
            trace.get_current_span().record_exception(exc)
            logger.error(
                exc.message,
                extra={
                    "event": "app_error",
                    "error_code": exc.error_code,
                    "http_status": exc.status_code,
                },
            )
        else:
            logger.info(
                exc.message,
                extra={
                    "event": "client_error",
                    "error_code": exc.error_code,
                    "http_status": exc.status_code,
                },
            )
        return JSONResponse(
            status_code=exc.status_code, content=error_body(exc.error_code, exc.message)
        )
