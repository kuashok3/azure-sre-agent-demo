import pytest
import requests
import responses

from app.common.errors import AppError
from app.orders.errors import PaymentDeclinedError, PaymentTimeoutError, PaymentUnavailableError
from app.orders.payment_client import PaymentClient

BASE = "http://payments.test"
URL = f"{BASE}/api/v1/payments"


@pytest.fixture
def client() -> PaymentClient:
    return PaymentClient(BASE, timeout_seconds=2)


@responses.activate
def test_charge_success(client):
    responses.post(URL, json={"payment_id": "pay_1", "status": "APPROVED"})
    assert client.charge("o1", 100, "USD")["payment_id"] == "pay_1"


@responses.activate
def test_charge_declined(client):
    responses.post(URL, status=402, json={"status": "DECLINED"})
    with pytest.raises(PaymentDeclinedError):
        client.charge("o1", 100, "USD")


@responses.activate
def test_charge_server_error_is_unavailable(client):
    responses.post(URL, status=503)
    with pytest.raises(PaymentUnavailableError):
        client.charge("o1", 100, "USD")


@responses.activate
def test_charge_read_timeout(client):
    responses.post(URL, body=requests.ReadTimeout("slow"))
    with pytest.raises(PaymentTimeoutError):
        client.charge("o1", 100, "USD")


@responses.activate
def test_charge_connection_error(client):
    responses.post(URL, body=requests.ConnectionError("refused"))
    with pytest.raises(PaymentUnavailableError):
        client.charge("o1", 100, "USD")


@responses.activate
def test_admin_fault_forward_failure_is_502(client):
    responses.put(f"{BASE}/admin/faults/latency", status=401)
    with pytest.raises(AppError) as info:
        client.admin_fault("enable", "latency", {"delay_ms": 10}, "token")
    assert info.value.status_code == 502
