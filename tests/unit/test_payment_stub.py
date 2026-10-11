import pytest
from fastapi.testclient import TestClient

from app.payment_stub.main import StubSettings, create_app
from tests.conftest import TEST_TOKEN

HEADERS = {"X-Fault-Token": TEST_TOKEN}


@pytest.fixture
def stub():
    settings = StubSettings(
        _env_file=None,
        environment="test",
        faults_enabled=True,
        fault_admin_token=TEST_TOKEN,
        applicationinsights_connection_string="",
    )
    with TestClient(create_app(settings)) as client:
        yield client


def pay(client, amount: int):
    return client.post(
        "/api/v1/payments", json={"order_id": "o1", "amount_cents": amount, "currency": "USD"}
    )


def test_approves_normal_payment(stub):
    response = pay(stub, 5000)
    assert response.status_code == 200
    assert response.json()["status"] == "APPROVED"
    assert response.json()["payment_id"].startswith("pay_")


def test_declines_above_threshold(stub):
    assert pay(stub, 2_000_000).status_code == 402


def test_errors_fault_returns_503(stub):
    stub.put("/admin/faults/errors", json={"params": {"error_rate": 1}}, headers=HEADERS)
    response = pay(stub, 5000)
    assert response.status_code == 503
    assert response.json()["error"] == "processor_unavailable"
    stub.delete("/admin/faults", headers=HEADERS)
    assert pay(stub, 5000).status_code == 200


def test_health(stub):
    assert stub.get("/health/live").json() == {"status": "alive"}
