"""HTTP client for payment-stub.

Uses ``requests`` because the Azure Monitor distro instruments it automatically: every call
becomes an AppDependencies row and carries the W3C ``traceparent`` header, so the payment-stub
request appears in the same end-to-end transaction in Application Insights.
"""

import requests

from app.common.correlation import CORRELATION_HEADER, get_correlation_id
from app.common.errors import AppError
from app.orders.errors import PaymentDeclinedError, PaymentTimeoutError, PaymentUnavailableError

CONNECT_TIMEOUT_SECONDS = 1.0


class PaymentClient:
    def __init__(
        self, base_url: str, timeout_seconds: float, session: requests.Session | None = None
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._session = session or requests.Session()

    def _headers(self) -> dict[str, str]:
        correlation_id = get_correlation_id()
        return {CORRELATION_HEADER: correlation_id} if correlation_id else {}

    def charge(self, order_id: str, amount_cents: int, currency: str) -> dict:
        try:
            response = self._session.post(
                f"{self._base_url}/api/v1/payments",
                json={"order_id": order_id, "amount_cents": amount_cents, "currency": currency},
                headers=self._headers(),
                timeout=(CONNECT_TIMEOUT_SECONDS, self._timeout),
            )
        except requests.ConnectTimeout as exc:
            raise PaymentUnavailableError("Payment service unreachable (connect timeout)") from exc
        except requests.Timeout as exc:
            raise PaymentTimeoutError(
                f"Payment service did not respond within {self._timeout:g}s"
            ) from exc
        except requests.ConnectionError as exc:
            raise PaymentUnavailableError("Payment service unreachable") from exc

        if response.status_code == 402:
            raise PaymentDeclinedError("Payment was declined by the payment service")
        if response.status_code != 200:
            raise PaymentUnavailableError(f"Payment service returned HTTP {response.status_code}")
        return response.json()

    def health(self) -> None:
        try:
            response = self._session.get(
                f"{self._base_url}/health/live", headers=self._headers(), timeout=1.0
            )
        except requests.RequestException as exc:
            raise PaymentUnavailableError(
                f"Payment service unreachable ({type(exc).__name__})"
            ) from exc
        if response.status_code != 200:
            raise PaymentUnavailableError(f"Payment service health returned {response.status_code}")

    def admin_fault(self, action: str, name: str | None, params: dict | None, token: str) -> None:
        """Forward a fault change to payment-stub's own /admin/faults API."""
        url = f"{self._base_url}/admin/faults" + (f"/{name}" if name else "")
        headers = {**self._headers(), "X-Fault-Token": token}
        try:
            if action == "enable":
                response = self._session.put(
                    url, json={"params": params or {}}, headers=headers, timeout=3
                )
            else:  # "disable" or "reset"
                response = self._session.delete(url, headers=headers, timeout=3)
        except requests.RequestException as exc:
            raise AppError(
                f"Could not reach payment-stub to {action} fault ({type(exc).__name__})",
                status_code=502,
                error_code="fault_forward_failed",
            ) from exc
        if response.status_code != 200:
            raise AppError(
                f"payment-stub rejected fault {action}: HTTP {response.status_code}",
                status_code=502,
                error_code="fault_forward_failed",
            )
