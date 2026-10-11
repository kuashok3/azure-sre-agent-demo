def test_root_describes_service(client):
    body = client.get("/").json()
    assert body["service"] == "orders-api"
    assert body["health"] == {"liveness": "/health/live", "readiness": "/health/ready"}


def test_liveness_is_always_ok(client, repo):
    repo.available = False  # liveness must not depend on the database
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


def test_readiness_ready_when_all_dependencies_ok(client):
    response = client.get("/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["checks"]["database"]["status"] == "ok"
    assert body["checks"]["payment_service"]["status"] == "ok"


def test_readiness_not_ready_when_database_down(client, repo):
    repo.available = False
    response = client.get("/health/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["checks"]["database"]["status"] == "error"


def test_readiness_degraded_when_payment_down(client, payment):
    payment.healthy = False
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "degraded"


def test_info_reports_version_and_environment(client):
    body = client.get("/info").json()
    assert body["service"] == "orders-api"
    assert body["environment"] == "test"
    assert body["telemetry_enabled"] is False
    assert body["faults_enabled"] is True


def test_correlation_id_generated_and_echoed(client):
    generated = client.get("/health/live").headers["X-Correlation-ID"]
    assert len(generated) == 32

    supplied = "my-trace-abc-123"
    response = client.get("/health/live", headers={"X-Correlation-ID": supplied})
    assert response.headers["X-Correlation-ID"] == supplied
    assert "X-Response-Time-Ms" in response.headers


def test_unsafe_correlation_id_is_replaced(client):
    response = client.get("/health/live", headers={"X-Correlation-ID": "bad id\nwith newline"})
    assert response.headers["X-Correlation-ID"] != "bad id\nwith newline"
