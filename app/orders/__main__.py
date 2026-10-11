"""Start orders-api: ``python -m app.orders``.

HOST defaults to 127.0.0.1 so a laptop run is not exposed to the network; the container image sets
HOST=0.0.0.0. log_config=None lets uvicorn's own logs flow through our JSON logging.
"""

import os

import uvicorn


def main() -> None:
    uvicorn.run(
        "app.orders.main:create_app",
        factory=True,
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8000")),
        log_config=None,
        access_log=False,
        proxy_headers=True,
        forwarded_allow_ips="*",
    )


if __name__ == "__main__":
    main()
