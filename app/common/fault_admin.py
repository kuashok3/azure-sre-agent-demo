"""Token-protected admin API for failure injection: /admin/faults.

Mounted only when FAULTS_ENABLED=true (otherwise these URLs return 404). Every call requires the
``X-Fault-Token`` header, compared in constant time. Every change is logged at WARNING level with
``event=fault_enabled|fault_disabled|faults_reset`` so there is an audit trail in AppTraces.

Some faults are "forwarded": e.g. orders-api's ``payment_latency`` is applied inside payment-stub,
so the slowness is real network-visible dependency behaviour, not a simulation in the caller.
"""

import hmac
import logging
from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field

from app.common.errors import AppError
from app.common.faults import FaultRegistry, FaultValidationError, UnknownFaultError

logger = logging.getLogger("app.faults")

# forwarder(action, remote_fault_name, params) where action is "enable" | "disable" | "reset"
Forwarder = Callable[[str, str | None, dict | None], None]


class FaultChange(BaseModel):
    params: dict[str, float] = Field(default_factory=dict)


def build_fault_admin_router(
    registry: FaultRegistry,
    token: str,
    *,
    forwarded: dict[str, str] | None = None,
    forwarder: Forwarder | None = None,
) -> APIRouter:
    forwarded = forwarded or {}
    expected = token.encode()

    def require_token(x_fault_token: Annotated[str | None, Header()] = None) -> None:
        if x_fault_token is None or not hmac.compare_digest(x_fault_token.encode(), expected):
            raise AppError(
                "Missing or invalid X-Fault-Token header.",
                status_code=401,
                error_code="unauthorized",
            )

    router = APIRouter(
        prefix="/admin/faults",
        tags=["fault injection (demo only)"],
        dependencies=[Depends(require_token)],
    )

    def _unknown(name: str) -> AppError:
        return AppError(f"Unknown fault '{name}'", status_code=404, error_code="unknown_fault")

    @router.get("")
    def list_faults() -> dict:
        return {"available": registry.describe(), "active": registry.active()}

    @router.put("/{name}")
    def enable_fault(name: str, body: FaultChange | None = None) -> dict:
        try:
            params = registry.validate(name, body.params if body else {})
        except UnknownFaultError:
            raise _unknown(name) from None
        except FaultValidationError as exc:
            raise AppError(str(exc), status_code=422, error_code="invalid_fault_params") from exc
        if name in forwarded and forwarder is not None:
            forwarder("enable", forwarded[name], params)
        entry = registry.enable(name, params)
        logger.warning(
            "Fault injection enabled",
            extra={"event": "fault_enabled", "fault_name": name, "fault_params": params},
        )
        return entry

    @router.delete("/{name}")
    def disable_fault(name: str) -> dict:
        if not registry.is_known(name):
            raise _unknown(name)
        if name in forwarded and forwarder is not None:
            forwarder("disable", forwarded[name], None)
        was_active = registry.disable(name)
        logger.warning(
            "Fault injection disabled",
            extra={"event": "fault_disabled", "fault_name": name, "was_active": was_active},
        )
        return {"name": name, "was_active": was_active}

    @router.delete("")
    def reset_faults() -> dict:
        names = registry.reset()
        forwarded_reset = "not_applicable"
        if forwarder is not None:
            try:
                forwarder("reset", None, None)
                forwarded_reset = "ok"
            except AppError as exc:
                forwarded_reset = f"failed: {exc.message}"
        logger.warning(
            "All faults reset",
            extra={"event": "faults_reset", "reset": names, "forwarded_reset": forwarded_reset},
        )
        return {"reset": names, "forwarded_reset": forwarded_reset}

    return router
