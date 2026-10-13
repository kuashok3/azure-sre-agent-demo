"""orders-api application factory.

Run with ``python -m app.orders`` (see __main__.py). Tests call ``create_app(...)`` with fakes.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.common.errors import register_error_handlers
from app.common.fault_admin import build_fault_admin_router
from app.common.faults import FaultRegistry
from app.common.http_middleware import install_request_middleware
from app.common.logging_setup import setup_logging
from app.common.telemetry import fastapi_telemetry_config, setup_telemetry
from app.orders.config import Settings
from app.orders.faults import FORWARDED_FAULTS, ORDERS_FAULTS
from app.orders.payment_client import PaymentClient
from app.orders.repository import ObservedRepository, OrderRepository
from app.orders.routes import api_router, health_router
from app.orders.service import OrderService

logger = logging.getLogger("app.orders")


def create_app(
    settings: Settings | None = None,
    repository: OrderRepository | None = None,
    payment_client: PaymentClient | None = None,
    faults: FaultRegistry | None = None,
) -> FastAPI:
    settings = settings or Settings()
    setup_logging(settings.otel_service_name, settings.log_level)
    # Telemetry must be configured before FastAPI() so the app is auto-instrumented.
    setup_telemetry(
        settings.telemetry_connection_string,
        settings.otel_service_name,
        settings.app_version,
        settings.environment,
        settings.telemetry_sampling_ratio,
    )

    faults = faults or FaultRegistry(ORDERS_FAULTS)
    if repository is None:
        from app.orders.db import build_pool
        from app.orders.repository import PostgresOrderRepository

        repository = PostgresOrderRepository(build_pool(settings))
    observed = ObservedRepository(repository, faults, settings.db_name, settings.db_host)
    payment = payment_client or PaymentClient(
        settings.payment_base_url, settings.payment_timeout_seconds
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        logger.info(
            "orders-api starting",
            extra={
                "event": "startup",
                "version": settings.app_version,
                "git_sha": settings.git_sha,
                "environment": settings.environment,
                "faults_enabled": settings.faults_enabled,
            },
        )
        observed.start()
        yield
        observed.stop()
        logger.info("orders-api stopped", extra={"event": "shutdown"})

    app = FastAPI(
        title="Contoso Orders API",
        version=settings.app_version,
        description="Order-processing demo service for learning Azure SRE Agent.",
        lifespan=lifespan,
        telemetry=fastapi_telemetry_config(),
    )
    app.state.settings = settings
    app.state.faults = faults
    app.state.repository = observed
    app.state.payment_client = payment
    app.state.order_service = OrderService(observed, payment)

    register_error_handlers(app)
    install_request_middleware(app)
    app.include_router(health_router)
    app.include_router(api_router)

    if settings.faults_enabled:
        token = settings.fault_token_value

        def forward(action: str, name: str | None, params: dict | None) -> None:
            payment.admin_fault(action, name, params, token)

        app.include_router(
            build_fault_admin_router(faults, token, forwarded=FORWARDED_FAULTS, forwarder=forward)
        )
    return app
