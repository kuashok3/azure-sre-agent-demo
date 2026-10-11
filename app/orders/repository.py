"""Data access for orders.

``PostgresOrderRepository`` contains only SQL. ``ObservedRepository`` wraps any repository and
adds the things SREs care about for every database call:
  * an OpenTelemetry CLIENT span -> one AppDependencies row (type "postgresql") per call;
  * the db_connection_failure / db_latency faults;
  * translation of connection errors into DatabaseUnavailableError (HTTP 503).
"""

import time
from collections.abc import Callable
from typing import Any, Protocol
from uuid import UUID

import psycopg
from opentelemetry import trace
from opentelemetry.trace import SpanKind
from psycopg_pool import ConnectionPool, PoolTimeout

from app.common.faults import FaultRegistry
from app.orders.errors import DatabaseUnavailableError

tracer = trace.get_tracer("app.orders.repository")


class OrderRepository(Protocol):
    def start(self) -> None: ...
    def stop(self) -> None: ...
    def ping(self) -> None: ...
    def create_order(self, customer_id: str, currency: str, items: list[dict]) -> dict: ...
    def get_order(self, order_id: UUID) -> dict | None: ...
    def list_orders(self, limit: int) -> list[dict]: ...
    def set_payment_result(
        self, order_id: UUID, status: str, payment_reference: str | None
    ) -> dict | None: ...
    def stats(self) -> dict: ...


class PostgresOrderRepository:
    def __init__(self, pool: ConnectionPool) -> None:
        self._pool = pool

    def start(self) -> None:
        self._pool.open(wait=False)

    def stop(self) -> None:
        self._pool.close()

    def ping(self) -> None:
        with self._pool.connection() as conn:
            conn.execute("SELECT 1")

    def create_order(self, customer_id: str, currency: str, items: list[dict]) -> dict:
        total = sum(i["quantity"] * i["unit_price_cents"] for i in items)
        with self._pool.connection() as conn, conn.transaction():
            order = conn.execute(
                "INSERT INTO orders (customer_id, currency, total_cents) "
                "VALUES (%s, %s, %s) RETURNING *",
                (customer_id, currency, total),
            ).fetchone()
            with conn.cursor() as cur:
                cur.executemany(
                    "INSERT INTO order_items (order_id, sku, quantity, unit_price_cents) "
                    "VALUES (%s, %s, %s, %s)",
                    [(order["id"], i["sku"], i["quantity"], i["unit_price_cents"]) for i in items],
                )
        order["items"] = [
            {"sku": i["sku"], "quantity": i["quantity"], "unit_price_cents": i["unit_price_cents"]}
            for i in items
        ]
        return order

    def _load_order(self, conn: psycopg.Connection, order_id: UUID) -> dict | None:
        order = conn.execute("SELECT * FROM orders WHERE id = %s", (order_id,)).fetchone()
        if order is None:
            return None
        order["items"] = conn.execute(
            "SELECT sku, quantity, unit_price_cents FROM order_items "
            "WHERE order_id = %s ORDER BY id",
            (order_id,),
        ).fetchall()
        return order

    def get_order(self, order_id: UUID) -> dict | None:
        with self._pool.connection() as conn:
            return self._load_order(conn, order_id)

    def list_orders(self, limit: int) -> list[dict]:
        with self._pool.connection() as conn:
            return conn.execute(
                "SELECT o.*, (SELECT count(*) FROM order_items i WHERE i.order_id = o.id) "
                "AS item_count FROM orders o ORDER BY o.created_at DESC LIMIT %s",
                (limit,),
            ).fetchall()

    def set_payment_result(
        self, order_id: UUID, status: str, payment_reference: str | None
    ) -> dict | None:
        """Update status unless the order is already PAID. Returns None if nothing was updated."""
        with self._pool.connection() as conn, conn.transaction():
            updated = conn.execute(
                "UPDATE orders SET status = %s, payment_reference = %s, updated_at = now() "
                "WHERE id = %s AND status <> 'PAID' RETURNING id",
                (status, payment_reference, order_id),
            ).fetchone()
            if updated is None:
                return None
            return self._load_order(conn, order_id)

    def stats(self) -> dict:
        with self._pool.connection() as conn:
            rows = conn.execute(
                "SELECT status, count(*) AS n, "
                "coalesce(sum(total_cents) FILTER (WHERE status = 'PAID'), 0) AS paid "
                "FROM orders GROUP BY status"
            ).fetchall()
        by_status = {r["status"]: r["n"] for r in rows}
        return {
            "total_orders": sum(by_status.values()),
            "orders_by_status": by_status,
            "paid_revenue_cents": int(sum(r["paid"] for r in rows)),
        }


class ObservedRepository:
    """Adds dependency telemetry, DB fault injection and error translation to a repository."""

    def __init__(
        self, inner: OrderRepository, faults: FaultRegistry, db_name: str, db_host: str
    ) -> None:
        self._inner = inner
        self._faults = faults
        self._attributes = {
            "db.system": "postgresql",
            "db.name": db_name,
            "server.address": db_host,
            "net.peer.name": db_host,
        }

    def start(self) -> None:
        self._inner.start()

    def stop(self) -> None:
        self._inner.stop()

    def _call(self, operation: str, fn: Callable[..., Any], *args: Any) -> Any:
        with tracer.start_as_current_span(
            f"postgresql {operation}",
            kind=SpanKind.CLIENT,
            attributes={**self._attributes, "db.operation": operation},
        ):
            if self._faults.triggered("db_connection_failure"):
                raise DatabaseUnavailableError(
                    "Could not connect to the database (injected fault: db_connection_failure)"
                )
            delay = self._faults.delay_seconds("db_latency")
            if delay:
                time.sleep(delay)
            try:
                return fn(*args)
            except (psycopg.OperationalError, PoolTimeout) as exc:
                raise DatabaseUnavailableError(
                    f"Database unavailable ({type(exc).__name__})"
                ) from exc

    def ping(self) -> None:
        self._call("ping", self._inner.ping)

    def create_order(self, customer_id: str, currency: str, items: list[dict]) -> dict:
        return self._call("create_order", self._inner.create_order, customer_id, currency, items)

    def get_order(self, order_id: UUID) -> dict | None:
        return self._call("get_order", self._inner.get_order, order_id)

    def list_orders(self, limit: int) -> list[dict]:
        return self._call("list_orders", self._inner.list_orders, limit)

    def set_payment_result(
        self, order_id: UUID, status: str, payment_reference: str | None
    ) -> dict | None:
        return self._call(
            "set_payment_result",
            self._inner.set_payment_result,
            order_id,
            status,
            payment_reference,
        )

    def stats(self) -> dict:
        return self._call("stats", self._inner.stats)
