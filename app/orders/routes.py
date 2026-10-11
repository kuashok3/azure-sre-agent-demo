"""HTTP routes for orders-api.

Health endpoints:
  GET /health/live   - process is up (no dependency checks). Used for liveness probes.
  GET /health/ready  - can we serve traffic? Database is CRITICAL (503 if down);
                       payment-stub is NON-CRITICAL (200 "degraded" if down: orders can still be
                       created, only checkout fails).
Business endpoints are under /api/v1 and are the only ones affected by latency/http_5xx faults.
"""

import time
from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from app.common.errors import AppError, InjectedFaultError
from app.common.info import build_info
from app.orders.models import OrderCreate, OrderList, OrderOut, OrderStats
from app.orders.service import OrderService

health_router = APIRouter(tags=["health"])


@health_router.get("/")
def root(request: Request) -> dict:
    settings = request.app.state.settings
    return {
        "service": "orders-api",
        "description": "Contoso Orders demo service for learning Azure SRE Agent",
        "version": settings.app_version,
        "docs": "/docs",
        "health": {"liveness": "/health/live", "readiness": "/health/ready"},
        "api": "/api/v1/orders",
    }


@health_router.get("/health/live")
def liveness() -> dict:
    return {"status": "alive"}


def _check(fn: Callable[[], None]) -> dict:
    started = time.perf_counter()
    try:
        fn()
        result = {"status": "ok"}
    except AppError as exc:
        result = {"status": "error", "error": exc.message}
    except Exception as exc:  # report, never crash the health endpoint
        result = {"status": "error", "error": type(exc).__name__}
    result["latency_ms"] = round((time.perf_counter() - started) * 1000, 1)
    return result


@health_router.get("/health/ready")
def readiness(request: Request) -> JSONResponse:
    state = request.app.state
    checks = {
        "database": {"critical": True, **_check(state.repository.ping)},
        "payment_service": {"critical": False, **_check(state.payment_client.health)},
    }
    if checks["database"]["status"] != "ok":
        status, code = "not_ready", 503
    elif checks["payment_service"]["status"] != "ok":
        status, code = "degraded", 200
    else:
        status, code = "ready", 200
    return JSONResponse(status_code=code, content={"status": status, "checks": checks})


@health_router.get("/info")
def info(request: Request) -> dict:
    return build_info(request.app.state.settings)


def apply_request_faults(request: Request) -> None:
    faults = request.app.state.faults
    delay = faults.delay_seconds("latency")
    if delay:
        time.sleep(delay)
    if faults.triggered("http_5xx", "error_rate"):
        raise InjectedFaultError("Injected fault: http_5xx")


def get_service(request: Request) -> OrderService:
    return request.app.state.order_service


Service = Annotated[OrderService, Depends(get_service)]

api_router = APIRouter(
    prefix="/api/v1", tags=["orders"], dependencies=[Depends(apply_request_faults)]
)


@api_router.post("/orders", status_code=201, response_model=OrderOut)
def create_order(body: OrderCreate, service: Service) -> dict:
    return service.create(body)


@api_router.get("/orders", response_model=OrderList)
def list_orders(service: Service, limit: Annotated[int, Query(ge=1, le=100)] = 20) -> dict:
    orders = service.list(limit)
    return {"count": len(orders), "orders": orders}


@api_router.get("/orders/{order_id}", response_model=OrderOut)
def get_order(order_id: UUID, service: Service) -> dict:
    return service.get(order_id)


@api_router.post("/orders/{order_id}/checkout", response_model=OrderOut)
def checkout_order(order_id: UUID, service: Service) -> dict:
    return service.checkout(order_id)


@api_router.get("/stats", response_model=OrderStats)
def stats(service: Service) -> dict:
    return service.stats()
