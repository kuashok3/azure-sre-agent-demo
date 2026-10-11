"""PostgreSQL connections.

Two authentication modes:
  * ``password`` (local docker compose): classic user/password.
  * ``entra`` (Azure): the app's managed identity obtains a short-lived Microsoft Entra token and
    uses it as the password. No database password exists anywhere. A fresh token is requested for
    every new physical connection, so expiry is handled automatically.
"""

from psycopg import Connection
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.orders.config import Settings

ENTRA_POSTGRES_SCOPE = "https://ossrdbms-aad.database.windows.net/.default"


def build_conninfo(settings: Settings) -> str:
    return make_conninfo(
        host=settings.db_host,
        port=settings.db_port,
        dbname=settings.db_name,
        user=settings.db_user,
        sslmode=settings.db_sslmode,
        connect_timeout=settings.db_connect_timeout_seconds,
        application_name=settings.otel_service_name,
        options=f"-c statement_timeout={settings.db_statement_timeout_ms}",
    )


def _entra_connection_class(client_id: str | None) -> type[Connection]:
    from azure.identity import DefaultAzureCredential

    # In Azure: managed identity (client_id selects the user-assigned identity).
    # On a laptop (e.g. running migrations as an admin): falls back to `az login`.
    credential = (
        DefaultAzureCredential(managed_identity_client_id=client_id)
        if client_id
        else DefaultAzureCredential()
    )

    class EntraConnection(Connection):
        @classmethod
        def connect(cls, conninfo: str = "", **kwargs):
            kwargs["password"] = credential.get_token(ENTRA_POSTGRES_SCOPE).token
            return super().connect(conninfo, **kwargs)

    return EntraConnection


def connection_parameters(settings: Settings) -> tuple[str, dict, type[Connection]]:
    kwargs: dict = {"row_factory": dict_row}
    if settings.db_auth_mode == "password":
        kwargs["password"] = settings.db_password.get_secret_value()  # validated in Settings
        return build_conninfo(settings), kwargs, Connection
    return build_conninfo(settings), kwargs, _entra_connection_class(settings.azure_client_id)


def build_pool(settings: Settings) -> ConnectionPool:
    conninfo, kwargs, connection_class = connection_parameters(settings)
    return ConnectionPool(
        conninfo,
        kwargs=kwargs,
        connection_class=connection_class,
        min_size=settings.db_pool_min_size,
        max_size=settings.db_pool_max_size,
        timeout=settings.db_connect_timeout_seconds,  # max wait for a pooled connection
        open=False,  # opened in the app lifespan, without blocking startup if the DB is down
        name="orders-db",
    )
