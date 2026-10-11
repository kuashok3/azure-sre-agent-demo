"""Test doubles: an in-memory repository and a scriptable payment client."""

import uuid
from datetime import UTC, datetime
from uuid import UUID

import psycopg

from app.orders.errors import PaymentDeclinedError, PaymentTimeoutError, PaymentUnavailableError


class InMemoryRepository:
    def __init__(self) -> None:
        self.orders: dict[UUID, dict] = {}
        self.available = True  # set False to simulate PostgreSQL being down
        self.started = False

    def _check(self) -> None:
        if not self.available:
            raise psycopg.OperationalError("connection refused (simulated)")

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.started = False

    def ping(self) -> None:
        self._check()

    def create_order(self, customer_id: str, currency: str, items: list[dict]) -> dict:
        self._check()
        now = datetime.now(UTC)
        order = {
            "id": uuid.uuid4(),
            "customer_id": customer_id,
            "status": "PENDING",
            "currency": currency,
            "total_cents": sum(i["quantity"] * i["unit_price_cents"] for i in items),
            "payment_reference": None,
            "created_at": now,
            "updated_at": now,
            "items": [dict(i) for i in items],
        }
        self.orders[order["id"]] = order
        return dict(order)

    def get_order(self, order_id: UUID) -> dict | None:
        self._check()
        order = self.orders.get(order_id)
        return dict(order) if order else None

    def list_orders(self, limit: int) -> list[dict]:
        self._check()
        rows = sorted(self.orders.values(), key=lambda o: o["created_at"], reverse=True)[:limit]
        return [{**o, "item_count": len(o["items"])} for o in rows]

    def set_payment_result(self, order_id: UUID, status: str, ref: str | None) -> dict | None:
        self._check()
        order = self.orders.get(order_id)
        if order is None or order["status"] == "PAID":
            return None
        order.update(status=status, payment_reference=ref, updated_at=datetime.now(UTC))
        return dict(order)

    def stats(self) -> dict:
        self._check()
        by_status: dict[str, int] = {}
        for o in self.orders.values():
            by_status[o["status"]] = by_status.get(o["status"], 0) + 1
        paid = sum(o["total_cents"] for o in self.orders.values() if o["status"] == "PAID")
        return {
            "total_orders": len(self.orders),
            "orders_by_status": by_status,
            "paid_revenue_cents": paid,
        }


class FakePaymentClient:
    """mode: approve | decline | timeout | unavailable"""

    def __init__(self) -> None:
        self.mode = "approve"
        self.healthy = True
        self.charges: list[tuple] = []
        self.admin_calls: list[tuple] = []
        self.admin_should_fail = False

    def charge(self, order_id: str, amount_cents: int, currency: str) -> dict:
        self.charges.append((order_id, amount_cents, currency))
        if self.mode == "decline":
            raise PaymentDeclinedError("declined")
        if self.mode == "timeout":
            raise PaymentTimeoutError("Payment service did not respond within 2s")
        if self.mode == "unavailable":
            raise PaymentUnavailableError("Payment service returned HTTP 503")
        return {"payment_id": "pay_test_123", "status": "APPROVED"}

    def health(self) -> None:
        if not self.healthy:
            raise PaymentUnavailableError("Payment service unreachable")

    def admin_fault(self, action: str, name: str | None, params: dict | None, token: str) -> None:
        from app.common.errors import AppError

        if self.admin_should_fail:
            raise AppError("forward failed", status_code=502, error_code="fault_forward_failed")
        self.admin_calls.append((action, name, params))
