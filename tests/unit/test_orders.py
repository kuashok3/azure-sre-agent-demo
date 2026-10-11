import uuid

from tests.conftest import ORDER_BODY


def create(client) -> dict:
    response = client.post("/api/v1/orders", json=ORDER_BODY)
    assert response.status_code == 201, response.text
    return response.json()


def test_create_order_computes_total(client):
    order = create(client)
    assert order["status"] == "PENDING"
    assert order["total_cents"] == 2 * 1250 + 4999
    assert len(order["items"]) == 2


def test_create_order_validation_errors(client):
    assert client.post("/api/v1/orders", json={**ORDER_BODY, "items": []}).status_code == 422
    bad_qty = {**ORDER_BODY, "items": [{"sku": "A", "quantity": 0, "unit_price_cents": 1}]}
    assert client.post("/api/v1/orders", json=bad_qty).status_code == 422
    assert client.post("/api/v1/orders", json={**ORDER_BODY, "currency": "XXX"}).status_code == 422


def test_get_order(client):
    order = create(client)
    response = client.get(f"/api/v1/orders/{order['id']}")
    assert response.status_code == 200
    assert response.json()["id"] == order["id"]


def test_get_missing_order_returns_404_with_error_body(client):
    response = client.get(f"/api/v1/orders/{uuid.uuid4()}")
    assert response.status_code == 404
    body = response.json()
    assert body["error"] == "order_not_found"
    assert body["correlation_id"] == response.headers["X-Correlation-ID"]


def test_invalid_order_id_returns_422(client):
    assert client.get("/api/v1/orders/not-a-uuid").status_code == 422


def test_list_orders(client):
    create(client)
    create(client)
    body = client.get("/api/v1/orders?limit=10").json()
    assert body["count"] == 2
    assert body["orders"][0]["item_count"] == 2


def test_checkout_success_marks_paid(client, payment):
    order = create(client)
    response = client.post(f"/api/v1/orders/{order['id']}/checkout")
    assert response.status_code == 200
    assert response.json()["status"] == "PAID"
    assert response.json()["payment_reference"] == "pay_test_123"
    assert payment.charges == [(order["id"], order["total_cents"], "USD")]


def test_checkout_twice_conflicts(client):
    order = create(client)
    client.post(f"/api/v1/orders/{order['id']}/checkout")
    response = client.post(f"/api/v1/orders/{order['id']}/checkout")
    assert response.status_code == 409
    assert response.json()["error"] == "order_state_conflict"


def test_checkout_declined_returns_402_and_marks_failed(client, payment):
    payment.mode = "decline"
    order = create(client)
    response = client.post(f"/api/v1/orders/{order['id']}/checkout")
    assert response.status_code == 402
    assert client.get(f"/api/v1/orders/{order['id']}").json()["status"] == "PAYMENT_FAILED"


def test_checkout_payment_timeout_returns_504_and_stays_pending(client, payment):
    payment.mode = "timeout"
    order = create(client)
    response = client.post(f"/api/v1/orders/{order['id']}/checkout")
    assert response.status_code == 504
    assert response.json()["error"] == "payment_service_timeout"
    assert client.get(f"/api/v1/orders/{order['id']}").json()["status"] == "PENDING"


def test_checkout_payment_unavailable_returns_503(client, payment):
    payment.mode = "unavailable"
    order = create(client)
    response = client.post(f"/api/v1/orders/{order['id']}/checkout")
    assert response.status_code == 503
    assert response.json()["error"] == "payment_service_unavailable"


def test_database_down_returns_503(client, repo):
    repo.available = False
    response = client.post("/api/v1/orders", json=ORDER_BODY)
    assert response.status_code == 503
    assert response.json()["error"] == "database_unavailable"


def test_stats(client, payment):
    paid = create(client)
    create(client)
    client.post(f"/api/v1/orders/{paid['id']}/checkout")
    body = client.get("/api/v1/stats").json()
    assert body["total_orders"] == 2
    assert body["orders_by_status"] == {"PAID": 1, "PENDING": 1}
    assert body["paid_revenue_cents"] == paid["total_cents"]
