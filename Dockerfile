# One image, two services:
#   orders-api   -> default CMD (python -m app.orders)
#   payment-stub -> command override (python -m app.payment_stub)
#   migrations   -> command override (python -m app.orders.migrate)
FROM python:3.13-slim

ARG APP_VERSION=0.1.0-dev
ARG GIT_SHA=unknown
ARG BUILD_TIME=unknown

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HOST=0.0.0.0 \
    PORT=8000 \
    APP_VERSION=${APP_VERSION} \
    GIT_SHA=${GIT_SHA} \
    BUILD_TIME=${BUILD_TIME}

WORKDIR /app

# Run as an unprivileged user, never root.
RUN groupadd --system app && useradd --system --gid app --no-create-home app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app
COPY migrations ./migrations

USER app
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-m", "app.common.healthcheck"]

CMD ["python", "-m", "app.orders"]
