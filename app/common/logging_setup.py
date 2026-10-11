"""Structured JSON logging.

Each log line is one JSON object with timestamp, level, service, message, correlation_id and the
OpenTelemetry trace_id. Extra fields passed with ``logger.info(..., extra={...})`` are included.
When Application Insights is configured, the same records (and their extra fields) are exported
to the ``AppTraces`` table as customDimensions.
"""

import json
import logging
import sys
from datetime import UTC, datetime

from opentelemetry import trace

from app.common.correlation import get_correlation_id

_STANDARD_ATTRS = set(vars(logging.LogRecord("", 0, "", 0, "", (), None))) | {
    "message",
    "asctime",
    "taskName",
    "color_message",  # uvicorn's ANSI-coloured duplicate of the message
}

_factory_installed = False


def _install_record_factory() -> None:
    """Attach the current correlation ID to every log record (for all handlers, not just stdout)."""
    global _factory_installed
    if _factory_installed:
        return
    previous = logging.getLogRecordFactory()

    def factory(*args, **kwargs):
        record = previous(*args, **kwargs)
        correlation_id = get_correlation_id()
        if correlation_id:
            record.correlation_id = correlation_id
        return record

    logging.setLogRecordFactory(factory)
    _factory_installed = True


class JsonFormatter(logging.Formatter):
    def __init__(self, service_name: str) -> None:
        super().__init__()
        self._service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(
                timespec="milliseconds"
            ),
            "level": record.levelname,
            "service": self._service_name,
            "logger": record.name,
            "message": record.getMessage(),
        }
        span_context = trace.get_current_span().get_span_context()
        if span_context.is_valid:
            payload["trace_id"] = format(span_context.trace_id, "032x")
            payload["span_id"] = format(span_context.span_id, "016x")
        for key, value in vars(record).items():
            if key not in _STANDARD_ATTRS and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def setup_logging(service_name: str, level: str = "INFO") -> None:
    _install_record_factory()
    root = logging.getLogger()
    root.setLevel(level)
    for handler in list(root.handlers):
        if getattr(handler, "_sre_demo_stdout", False):
            root.removeHandler(handler)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter(service_name))
    handler._sre_demo_stdout = True  # type: ignore[attr-defined]
    root.addHandler(handler)

    # Keep SDK chatter out of logs (and out of Application Insights ingestion costs).
    for noisy in ("azure", "urllib3", "opentelemetry", "uvicorn.access"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
