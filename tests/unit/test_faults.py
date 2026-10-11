import random
import time

import pytest
from fastapi.testclient import TestClient

from app.common.faults import FaultRegistry, FaultValidationError, UnknownFaultError
from app.orders.faults import ORDERS_FAULTS
from app.orders.main import create_app
from tests.conftest import ORDER_BODY, make_settings
from tests.fakes import FakePaymentClient, InMemoryRepository

# ---- registry -----------------------------------------------------------------------------


def test_registry_starts_empty_and_applies_defaults():
    registry = FaultRegistry(ORDERS_FAULTS)
    assert registry.active() == []
    entry = registry.enable("latency")
    assert entry["params"] == {"delay_ms": 1500, "probability": 1.0}


def test_registry_rejects_unknown_fault_and_bad_params():
    registry = FaultRegistry(ORDERS_FAULTS)
    with pytest.raises(UnknownFaultError):
        registry.enable("explode")
    with pytest.raises(FaultValidationError):
        registry.enable("latency", {"delay_ms": 999_999})
    with pytest.raises(FaultValidationError):
        registry.enable("latency", {"colour": 1})


def test_registry_probability_zero_never_triggers():
    registry = FaultRegistry(ORDERS_FAULTS, rng=random.Random(1))
    registry.enable("http_5xx", {"error_rate": 0.0})
    assert not any(registry.triggered("http_5xx", "error_rate") for _ in range(200))


def test_registry_reset():
    registry = FaultRegistry(ORDERS_FAULTS)
    registry.enable("latency")
    registry.enable("db_latency")
    assert registry.reset() == ["db_latency", "latency"]
    assert registry.active() == []


# ---- admin API security -------------------------------------------------------------------


def test_admin_api_absent_when_faults_disabled(repo, payment):
    app = create_app(make_settings(faults_enabled=False), repository=repo, payment_client=payment)
    with TestClient(app) as c:
        assert c.get("/admin/faults").status_code == 404


def test_admin_api_requires_token(client):
    assert client.get("/admin/faults").status_code == 401
    assert client.get("/admin/faults", headers={"X-Fault-Token": "wrong"}).status_code == 401


def test_list_faults(client, admin_headers):
    body = client.get("/admin/faults", headers=admin_headers).json()
    names = {f["name"] for f in body["available"]}
    assert names == set(ORDERS_FAULTS)
    assert body["active"] == []


def test_unknown_fault_404_and_bad_params_422(client, admin_headers):
    assert client.put("/admin/faults/explode", headers=admin_headers).status_code == 404
    response = client.put(
        "/admin/faults/latency", json={"params": {"delay_ms": -5}}, headers=admin_headers
    )
    assert response.status_code == 422


# ---- fault behaviour ----------------------------------------------------------------------


def test_latency_fault_slows_api_but_not_health(client, admin_headers):
    client.put("/admin/faults/latency", json={"params": {"delay_ms": 300}}, headers=admin_headers)
    started = time.perf_counter()
    assert client.get("/api/v1/orders").status_code == 200
    assert time.perf_counter() - started >= 0.3

    started = time.perf_counter()
    client.get("/health/live")
    assert time.perf_counter() - started < 0.3


def test_http_5xx_fault_returns_500_with_correlation_id(client, admin_headers):
    client.put("/admin/faults/http_5xx", json={"params": {"error_rate": 1}}, headers=admin_headers)
    response = client.get("/api/v1/orders")
    assert response.status_code == 500
    body = response.json()
    assert body["error"] == "internal_error"
    assert body["correlation_id"] == response.headers["X-Correlation-ID"]


def test_db_connection_failure_fault(client, admin_headers):
    client.put("/admin/faults/db_connection_failure", headers=admin_headers)
    assert client.post("/api/v1/orders", json=ORDER_BODY).status_code == 503
    assert client.get("/health/ready").status_code == 503


def test_db_latency_fault(client, admin_headers):
    client.put(
        "/admin/faults/db_latency", json={"params": {"delay_ms": 250}}, headers=admin_headers
    )
    started = time.perf_counter()
    assert client.get("/api/v1/stats").status_code == 200
    assert time.perf_counter() - started >= 0.25


def test_payment_faults_are_forwarded(client, payment, admin_headers):
    response = client.put(
        "/admin/faults/payment_latency", json={"params": {"delay_ms": 4000}}, headers=admin_headers
    )
    assert response.status_code == 200
    assert payment.admin_calls == [("enable", "latency", {"delay_ms": 4000})]
    client.delete("/admin/faults/payment_latency", headers=admin_headers)
    assert payment.admin_calls[-1] == ("disable", "latency", None)


def test_failed_forward_does_not_record_fault_locally(client, payment, admin_headers):
    payment.admin_should_fail = True
    response = client.put("/admin/faults/payment_errors", headers=admin_headers)
    assert response.status_code == 502
    assert client.get("/admin/faults", headers=admin_headers).json()["active"] == []


def test_reset_restores_normal_operation(client, admin_headers, payment):
    client.put("/admin/faults/http_5xx", json={"params": {"error_rate": 1}}, headers=admin_headers)
    client.put("/admin/faults/db_connection_failure", headers=admin_headers)
    response = client.delete("/admin/faults", headers=admin_headers)
    assert response.json()["reset"] == ["db_connection_failure", "http_5xx"]
    assert response.json()["forwarded_reset"] == "ok"
    assert payment.admin_calls[-1] == ("reset", None, None)
    assert client.get("/api/v1/orders").status_code == 200
    assert client.get("/health/ready").status_code == 200


def test_fault_state_is_per_app_instance():
    a = create_app(
        make_settings(), repository=InMemoryRepository(), payment_client=FakePaymentClient()
    )
    b = create_app(
        make_settings(), repository=InMemoryRepository(), payment_client=FakePaymentClient()
    )
    a.state.faults.enable("http_5xx", {"error_rate": 1})
    assert b.state.faults.active() == []
