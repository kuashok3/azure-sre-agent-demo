"""payment-stub application.

POST /api/v1/payments approves payments up to DECLINE_THRESHOLD_CENTS and declines larger ones
(HTTP 402), which gives a deterministic "business failure" that is NOT an outage.
Faults: ``latency`` (slow responses) and ``errors`` (HTTP 503), usually toggled through
orders-api's payment_latency / payment_errors faults.
"""

import logging
import time
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.common.errors import AppError, register_error_handlers
from app.common.fault_admin import build_fault_admin_router
from app.common.faults import FaultRegistry, FaultSpec, delay_param, rate_param
from app.common.http_middleware import install_request_middleware
from app.common.info import build_info
from app.common.logging_setup import setup_logging
from app.common.settings import BaseServiceSettings
from app.common.telemetry import fastapi_telemetry_config, setup_telemetry

logger = logging.getLogger("app.payment_stub")


class StubSettings(BaseServiceSettings):
    otel_service_name: str = "payment-stub"
    decline_threshold_cents: int = Field(1_000_000, gt=0)


PAYMENT_FAULTS = {
    "latency": FaultSpec(
        "latency",
        "Delay payment responses",
        "payment-stub /api/*",
        {"delay_ms": delay_param(5000), "probability": rate_param(1.0, "Share of requests")},
    ),
    "errors": FaultSpec(
        "errors",
        "Return HTTP 503 for a share of payments",
        "payment-stub /api/*",
        {"error_rate": rate_param(1.0, "Share of requests that fail")},
    ),
}


class PaymentRequest(BaseModel):
    order_id: str = Field(min_length=1, max_length=64)
    amount_cents: int = Field(gt=0)
    currency: Literal["USD", "EUR", "INR"]


def create_app(
    settings: StubSettings | None = None, faults: FaultRegistry | None = None
) -> FastAPI:
    settings = settings or StubSettings()
    setup_logging(settings.otel_service_name, settings.log_level)
    setup_telemetry(
        settings.telemetry_connection_string,
        settings.otel_service_name,
        settings.app_version,
        settings.environment,
    )
    faults = faults or FaultRegistry(PAYMENT_FAULTS)

    app = FastAPI(
        title="Payment Stub", version=settings.app_version, telemetry=fastapi_telemetry_config()
    )
    app.state.settings = settings
    app.state.faults = faults
    register_error_handlers(app)
    install_request_middleware(app)

    def apply_faults() -> None:
        delay = faults.delay_seconds("latency")
        if delay:
            time.sleep(delay)
        if faults.triggered("errors", "error_rate"):
            raise AppError(
                "Payment processor unavailable (injected fault: errors)",
                status_code=503,
                error_code="processor_unavailable",
            )

    @app.get("/", tags=["health"])
    def root() -> dict:
        return {"service": "payment-stub", "version": settings.app_version}

    @app.get("/health/live", tags=["health"])
    def liveness() -> dict:
        return {"status": "alive"}

    @app.get("/health/ready", tags=["health"])
    def readiness() -> dict:
        return {"status": "ready"}

    @app.get("/info", tags=["health"])
    def info(request: Request) -> dict:
        return build_info(request.app.state.settings)

    api = APIRouter(prefix="/api/v1", tags=["payments"], dependencies=[Depends(apply_faults)])

    @api.post("/payments")
    def create_payment(body: PaymentRequest) -> JSONResponse:
        if body.amount_cents > settings.decline_threshold_cents:
            logger.info(
                "payment declined",
                extra={"event": "payment_declined", "order_id": body.order_id},
            )
            return JSONResponse(
                status_code=402, content={"status": "DECLINED", "reason": "amount_limit"}
            )
        payment_id = f"pay_{uuid.uuid4().hex[:20]}"
        logger.info(
            "payment approved",
            extra={
                "event": "payment_approved",
                "order_id": body.order_id,
                "payment_id": payment_id,
            },
        )
        return JSONResponse(
            status_code=200, content={"payment_id": payment_id, "status": "APPROVED"}
        )

    app.include_router(api)
    if settings.faults_enabled:
        app.include_router(build_fault_admin_router(faults, settings.fault_token_value))
    return app
