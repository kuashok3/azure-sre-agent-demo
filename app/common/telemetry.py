"""Azure Monitor OpenTelemetry setup.

If APPLICATIONINSIGHTS_CONNECTION_STRING is set, the Azure Monitor OpenTelemetry Distro exports:
  * incoming FastAPI requests      -> AppRequests
  * outgoing `requests` HTTP calls -> AppDependencies (payment-stub calls)
  * our manual PostgreSQL spans    -> AppDependencies (type "postgresql")
  * Python log records             -> AppTraces / AppExceptions
  * OpenTelemetry metrics          -> AppMetrics (customMetrics)
Locally the connection string is empty and telemetry export is skipped; logs still go to stdout.
"""

import logging
import os

logger = logging.getLogger(__name__)

PROBE_PATH = "/health/live"

_configured = False


def setup_telemetry(
    connection_string: str | None, service_name: str, service_version: str, environment: str
) -> bool:
    """Configure export once per process. Must run before the FastAPI app object is created."""
    global _configured
    if _configured:
        return True
    if not connection_string:
        logger.info(
            "Application Insights not configured; telemetry export disabled",
            extra={"event": "telemetry_disabled"},
        )
        return False

    # Liveness probes run every few seconds; don't pay to store them as requests. Must be set
    # BEFORE importing the distro: the FastAPI instrumentation reads it once, at import time.
    os.environ.setdefault("OTEL_PYTHON_FASTAPI_EXCLUDED_URLS", PROBE_PATH.lstrip("/"))
    from azure.monitor.opentelemetry import configure_azure_monitor
    from opentelemetry.sdk.resources import Resource

    configure_azure_monitor(
        connection_string=connection_string,
        resource=Resource.create(
            {
                "service.name": service_name,  # becomes cloud_RoleName / AppRoleName
                "service.version": service_version,
                "deployment.environment": environment,
            }
        ),
    )
    _configured = True
    logger.info("Application Insights telemetry enabled", extra={"event": "telemetry_enabled"})
    return True


def is_telemetry_enabled() -> bool:
    return _configured


def _is_probe(scope) -> bool:
    return scope.get("path") == PROBE_PATH


def fastapi_telemetry_config() -> dict:
    """Settings for FastAPI's built-in OpenTelemetry support, passed as FastAPI(telemetry=...).

    FastAPI (0.143+) traces requests itself whenever a real tracer provider exists (as in Azure).
    * operation_spans=False: drop the internal fastapi.dependencies/endpoint/serialization spans,
      which would otherwise appear in AppDependencies as fake "dependencies" (3 rows per request).
    * exclude: skip liveness probes entirely.
    """
    return {"operation_spans": False, "exclude": _is_probe}
