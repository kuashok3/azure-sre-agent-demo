# Configuration

All configuration comes from **environment variables** (and a `.env` file locally). Settings are
validated at startup (`app/common/settings.py`, `app/orders/config.py`), so a bad value stops the
service with a clear error instead of failing later.

Legend: 🔒 = secret (never commit, never log). Azure column = planned values (M4).

## Shared (orders-api and payment-stub)

| Variable | Default | Local (.env) | Azure | Purpose |
|---|---|---|---|---|
| `ENVIRONMENT` | `local` | `local` | `azure` | `local`/`test`/`azure`. `azure` rejects placeholder tokens |
| `APP_VERSION` | `0.1.0-dev` | set by compose build arg | image tag | Shown in `/info`, telemetry `service.version` |
| `GIT_SHA`, `BUILD_TIME` | `unknown` | — | set by CI | Shown in `/info` |
| `DEPLOYMENT_REGION` | `local` | — | `eastus2` | Shown in `/info` |
| `LOG_LEVEL` | `INFO` | `INFO` | `INFO` | DEBUG/INFO/WARNING/ERROR (case-insensitive) |
| `OTEL_SERVICE_NAME` | `orders-api` / `payment-stub` | set by compose | same | Becomes `AppRoleName` in Application Insights |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` 🔒* | empty | empty | from App Insights | Empty = telemetry export off |
| `FAULTS_ENABLED` | `false` | `true` | `true` during training | Mounts `/admin/faults` |
| `FAULT_ADMIN_TOKEN` 🔒 | — | `change-me-local-fault-token` | Key Vault secret | ≥ 16 chars; required if faults enabled; `change-me…` rejected in Azure |
| `HOST` | `127.0.0.1` | — (image sets `0.0.0.0`) | `0.0.0.0` | Bind address |
| `PORT` | 8000 / 8001 | set by compose | 8000 / 8001 | Listen port |
| `OTEL_PYTHON_FASTAPI_EXCLUDED_URLS` | `health/live` (set by code) | — | — | Paths not recorded as requests |

\* The connection string is not a password, but treat it as sensitive: anyone holding it can send telemetry to your resource.

## orders-api only

| Variable | Default | Local | Azure | Purpose |
|---|---|---|---|---|
| `DB_HOST` | `localhost` | `localhost` (compose overrides to `postgres`) | `<server>.postgres.database.azure.com` | |
| `DB_PORT` | 5432 | 5434 (compose overrides to 5432) | 5432 | |
| `DB_NAME` / `DB_USER` | `orders` / `orders` | same | `orders` / managed-identity name | |
| `DB_PASSWORD` 🔒 | — | `local-dev-only-password` | **not set** | Required only when `DB_AUTH_MODE=password` |
| `DB_AUTH_MODE` | `password` | `password` | `entra` | `entra` = managed-identity token, no password |
| `DB_SSLMODE` | `prefer` | `disable` | `require` | |
| `DB_CONNECT_TIMEOUT_SECONDS` | 3 | — | 3 | TCP/auth connect timeout and pool wait |
| `DB_STATEMENT_TIMEOUT_MS` | 5000 | — | 5000 | Server-side query timeout |
| `DB_POOL_MIN_SIZE` / `DB_POOL_MAX_SIZE` | 1 / 5 | — | 1 / 5 | Connection pool |
| `AZURE_CLIENT_ID` | — | — | client ID of `id-orders-api` | Selects the user-assigned managed identity |
| `PAYMENT_BASE_URL` | `http://localhost:8001` | `http://localhost:8081` (compose overrides to `http://payment-stub:8001`) | `http://ca-payment-stub` | |
| `PAYMENT_TIMEOUT_SECONDS` | 2.0 | 2 | 2 | Read timeout for payment calls |
| `MIGRATIONS_DIR` | `<repo>/migrations` | — | `/app/migrations` | Used by `python -m app.orders.migrate` |

## payment-stub only

| Variable | Default | Purpose |
|---|---|---|
| `DECLINE_THRESHOLD_CENTS` | 1000000 | Payments above this amount are declined (402) |

## docker compose only (host side)

| Variable | Default | Purpose |
|---|---|---|
| `ORDERS_HOST_PORT` | 8080 | Host port for orders-api |
| `PAYMENT_HOST_PORT` | 8081 | Host port for payment-stub |
| `POSTGRES_HOST_PORT` | 5434 | Host port for PostgreSQL (keep `DB_PORT` in `.env` equal) |

## Scripts

| Variable | Default | Purpose |
|---|---|---|
| `ORDERS_BASE_URL` | `http://localhost:8080` | Target for `smoke_test.py`, `fault.py`, `load.py`, `validate_faults.py` |
| `FAULT_ADMIN_TOKEN` | read from `.env` | Token for `fault.py` / `validate_faults.py` |

## Validation rules (startup fails if broken)
- `FAULTS_ENABLED=true` needs `FAULT_ADMIN_TOKEN` of at least 16 characters.
- `ENVIRONMENT=azure` with a `change-me…` token fails.
- `DB_AUTH_MODE=password` needs `DB_PASSWORD`.
- `DB_POOL_MIN_SIZE` ≤ `DB_POOL_MAX_SIZE`.
