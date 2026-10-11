"""Integration tests against real PostgreSQL (docker compose, host port 5434).

Run:  docker compose up -d postgres migrate   then   pytest -m integration
Skipped automatically when the database is unreachable.
"""

import time

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.orders.config import Settings
from app.orders.db import build_conninfo, build_pool
from app.orders.main import create_app
from app.orders.repository import PostgresOrderRepository
from tests.conftest import ORDER_BODY, TEST_TOKEN
from tests.fakes import FakePaymentClient

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def settings() -> Settings:
    # Reads DB_* from the environment / .env (same values the app uses on the host).
    s = Settings(
        environment="test",
        faults_enabled=True,
        fault_admin_token=TEST_TOKEN,
        applicationinsights_connection_string="",
    )
    try:
        with psycopg.connect(
            build_conninfo(s), password=s.db_password.get_secret_value(), connect_timeout=2
        ) as conn:
            conn.execute("SELECT 1 FROM orders LIMIT 1")
    except psycopg.Error as exc:
        pytest.skip(f"PostgreSQL not reachable or not migrated: {type(exc).__name__}")
    return s


@pytest.fixture
def client(settings):
    repo = PostgresOrderRepository(build_pool(settings))
    app = create_app(settings, repository=repo, payment_client=FakePaymentClient())
    with TestClient(app) as c:
        yield c


def test_ready_with_real_database(client):
    for _ in range(20):  # pool opens asynchronously
        response = client.get("/health/ready")
        if response.status_code == 200:
            break
        time.sleep(0.25)
    assert response.json()["checks"]["database"]["status"] == "ok"


def test_order_lifecycle_persists(client):
    order = client.post("/api/v1/orders", json=ORDER_BODY).json()
    fetched = client.get(f"/api/v1/orders/{order['id']}").json()
    assert fetched["total_cents"] == 7499
    assert [i["sku"] for i in fetched["items"]] == ["WIDGET-1", "GADGET-2"]

    paid = client.post(f"/api/v1/orders/{order['id']}/checkout").json()
    assert paid["status"] == "PAID"
    assert client.post(f"/api/v1/orders/{order['id']}/checkout").status_code == 409
    assert client.get("/api/v1/stats").json()["orders_by_status"]["PAID"] >= 1


def test_db_latency_fault_against_real_database(client):
    headers = {"X-Fault-Token": TEST_TOKEN}
    client.put("/admin/faults/db_latency", json={"params": {"delay_ms": 300}}, headers=headers)
    try:
        started = time.perf_counter()
        assert client.get("/api/v1/orders?limit=1").status_code == 200
        assert time.perf_counter() - started >= 0.3
    finally:
        client.delete("/admin/faults", headers=headers)
