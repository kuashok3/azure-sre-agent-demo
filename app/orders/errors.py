"""Expected failures in orders-api and the HTTP status each one maps to."""

from app.common.errors import AppError


class OrderNotFoundError(AppError):
    status_code = 404
    error_code = "order_not_found"


class OrderStateConflictError(AppError):
    status_code = 409
    error_code = "order_state_conflict"


class DatabaseUnavailableError(AppError):
    status_code = 503
    error_code = "database_unavailable"


class PaymentDeclinedError(AppError):
    status_code = 402
    error_code = "payment_declined"


class PaymentUnavailableError(AppError):
    status_code = 503
    error_code = "payment_service_unavailable"


class PaymentTimeoutError(AppError):
    status_code = 504
    error_code = "payment_service_timeout"
