import pytest
from fastapi.testclient import TestClient

from app.common.faults import FaultRegistry
from app.orders.config import Settings
from app.orders.faults import ORDERS_FAULTS
from app.orders.main import create_app
from tests.fakes import FakePaymentClient, InMemoryRepository

TEST_TOKEN = "test-fault-token-0123456789"


def make_settings(**overrides) -> Settings:
    values = {
        "environment": "test",
        "db_password": "unused-in-unit-tests",
        "faults_enabled": True,
        "fault_admin_token": TEST_TOKEN,
        "applicationinsights_connection_string": "",
    }
    values.update(overrides)
    # _env_file=None: unit tests must not depend on a developer's .env file
    return Settings(_env_file=None, **values)


@pytest.fixture
def repo() -> InMemoryRepository:
    return InMemoryRepository()


@pytest.fixture
def payment() -> FakePaymentClient:
    return FakePaymentClient()


@pytest.fixture
def faults() -> FaultRegistry:
    return FaultRegistry(ORDERS_FAULTS)


@pytest.fixture
def client(repo, payment, faults):
    app = create_app(make_settings(), repository=repo, payment_client=payment, faults=faults)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def admin_headers() -> dict[str, str]:
    return {"X-Fault-Token": TEST_TOKEN}


ORDER_BODY = {
    "customer_id": "cust-001",
    "currency": "USD",
    "items": [
        {"sku": "WIDGET-1", "quantity": 2, "unit_price_cents": 1250},
        {"sku": "GADGET-2", "quantity": 1, "unit_price_cents": 4999},
    ],
}
