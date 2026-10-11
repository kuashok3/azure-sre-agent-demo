"""Business logic: create, read and check out orders."""

import logging
from uuid import UUID

from app.orders import metrics
from app.orders.errors import (
    OrderNotFoundError,
    OrderStateConflictError,
    PaymentDeclinedError,
    PaymentTimeoutError,
    PaymentUnavailableError,
)
from app.orders.models import OrderCreate
from app.orders.payment_client import PaymentClient
from app.orders.repository import OrderRepository

logger = logging.getLogger("app.orders")


class OrderService:
    def __init__(self, repository: OrderRepository, payment: PaymentClient) -> None:
        self._repo = repository
        self._payment = payment

    def create(self, request: OrderCreate) -> dict:
        items = [item.model_dump() for item in request.items]
        order = self._repo.create_order(request.customer_id, request.currency, items)
        metrics.orders_created.add(1, {"currency": request.currency})
        metrics.order_value_cents.record(order["total_cents"], {"currency": request.currency})
        logger.info(
            "order created",
            extra={
                "event": "order_created",
                "order_id": str(order["id"]),
                "total_cents": order["total_cents"],
            },
        )
        return order

    def get(self, order_id: UUID) -> dict:
        order = self._repo.get_order(order_id)
        if order is None:
            raise OrderNotFoundError(f"Order {order_id} not found")
        return order

    def list(self, limit: int) -> list[dict]:
        return self._repo.list_orders(limit)

    def stats(self) -> dict:
        return self._repo.stats()

    def checkout(self, order_id: UUID) -> dict:
        order = self.get(order_id)
        if order["status"] == "PAID":
            raise OrderStateConflictError(f"Order {order_id} is already paid")

        try:
            payment = self._payment.charge(str(order_id), order["total_cents"], order["currency"])
        except PaymentDeclinedError:
            self._repo.set_payment_result(order_id, "PAYMENT_FAILED", None)
            metrics.checkout_results.add(1, {"result": "payment_declined"})
            logger.info(
                "payment declined",
                extra={"event": "checkout_declined", "order_id": str(order_id)},
            )
            raise
        except (PaymentTimeoutError, PaymentUnavailableError) as exc:
            # Order stays PENDING so the customer can retry once the dependency recovers.
            metrics.checkout_results.add(1, {"result": exc.error_code})
            raise

        updated = self._repo.set_payment_result(order_id, "PAID", payment["payment_id"])
        if updated is None:
            raise OrderStateConflictError(f"Order {order_id} was paid by a concurrent request")
        metrics.checkout_results.add(1, {"result": "paid"})
        logger.info(
            "order paid",
            extra={
                "event": "checkout_paid",
                "order_id": str(order_id),
                "payment_id": payment["payment_id"],
            },
        )
        return updated
