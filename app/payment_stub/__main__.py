"""Start payment-stub: ``python -m app.payment_stub`` (default port 8001)."""

import os

import uvicorn


def main() -> None:
    uvicorn.run(
        "app.payment_stub.main:create_app",
        factory=True,
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8001")),
        log_config=None,
        access_log=False,
    )


if __name__ == "__main__":
    main()
