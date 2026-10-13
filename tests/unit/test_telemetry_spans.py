"""Which spans do the apps produce when a real tracer provider is active (as in Azure)?

Found on 2026-10-13 in Application Insights: liveness probes were recorded as requests, and
FastAPI's internal `fastapi.dependencies/endpoint/serialization` spans showed up in AppDependencies.
"""

import pytest
from fastapi.testclient import TestClient
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app.orders.main import create_app
from tests.conftest import make_settings
from tests.fakes import FakePaymentClient, InMemoryRepository

_EXPORTER = InMemorySpanExporter()


@pytest.fixture(scope="module", autouse=True)
def tracer_provider():
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(_EXPORTER))
    # The global provider can only be set once per process; later attempts are ignored.
    trace.set_tracer_provider(provider)
    if trace.get_tracer_provider() is not provider:
        pytest.skip("another global tracer provider is already installed")
    yield


@pytest.fixture
def spans():
    _EXPORTER.clear()
    app = create_app(
        make_settings(), repository=InMemoryRepository(), payment_client=FakePaymentClient()
    )
    with TestClient(app) as client:
        yield client, _EXPORTER


def names(exporter) -> list[str]:
    return [s.name for s in exporter.get_finished_spans()]


def test_no_internal_fastapi_operation_spans(spans):
    client, exporter = spans
    assert (
        client.post(
            "/api/v1/orders",
            json={
                "customer_id": "c",
                "items": [{"sku": "A", "quantity": 1, "unit_price_cents": 5}],
            },
        ).status_code
        == 201
    )
    assert not [n for n in names(exporter) if n.startswith("fastapi.")]


def test_business_requests_are_still_traced(spans):
    client, exporter = spans
    client.get("/api/v1/orders")
    assert any("/api/v1/orders" in n for n in names(exporter))
    assert "postgresql list_orders" in names(exporter)  # our dependency span survives


def test_liveness_probe_is_not_traced(spans):
    client, exporter = spans
    client.get("/health/live")
    assert not [n for n in names(exporter) if "/health/live" in n]
