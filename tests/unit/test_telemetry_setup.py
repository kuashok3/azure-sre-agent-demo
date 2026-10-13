"""setup_telemetry must configure sampling explicitly.

Found 2026-10-13: without an explicit sampler, the Azure Monitor distro defaults to a rate-limited
sampler (~5 traces/s) and dropped about half of the requests during fault drills, while their logs
were kept. SLO queries on AppRequests were then wrong.
"""

import pytest

import app.common.telemetry as telemetry


@pytest.fixture
def captured(monkeypatch):
    import azure.monitor.opentelemetry as distro

    calls = {}
    monkeypatch.setattr(distro, "configure_azure_monitor", lambda **kw: calls.update(kw))
    monkeypatch.setattr(telemetry, "_configured", False)
    yield calls
    telemetry._configured = False


def test_sampling_ratio_is_passed_explicitly(captured):
    assert telemetry.setup_telemetry("InstrumentationKey=x", "orders-api", "1.0", "test", 1.0)
    assert captured["sampling_ratio"] == 1.0


def test_sampling_ratio_is_configurable(captured):
    telemetry.setup_telemetry("InstrumentationKey=x", "orders-api", "1.0", "test", 0.25)
    assert captured["sampling_ratio"] == 0.25


def test_no_connection_string_means_no_export(captured):
    assert telemetry.setup_telemetry(None, "orders-api", "1.0", "test", 1.0) is False
    assert captured == {}
