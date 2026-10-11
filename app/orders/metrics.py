"""Business metrics (OpenTelemetry). Exported to Application Insights customMetrics / AppMetrics.

Without a connection string the OpenTelemetry API is a no-op, so these are safe to call locally.
"""

from opentelemetry import metrics

_meter = metrics.get_meter("orders-api")

orders_created = _meter.create_counter(
    "orders_created", unit="1", description="Orders successfully created"
)
order_value_cents = _meter.create_histogram(
    "order_value_cents", unit="cents", description="Total value of created orders"
)
checkout_results = _meter.create_counter(
    "checkout_results",
    unit="1",
    description="Checkout attempts by result (paid, payment_declined, payment_service_timeout...)",
)
