"""One-time database setup in Azure, run by the PostgreSQL Entra admin after `az login`.

What it does (all idempotent, safe to re-run):
  1. Applies migrations as the admin, so the admin owns the tables.
  2. Creates a PostgreSQL role for the app's managed identity (`id-orders-api`), bound to the
     identity's OBJECT ID. Binding by name fails once several environments in the same tenant have
     an identity with that name ("name isn't unique in the tenant", seen 2026-10-15).
  3. Grants that role data access only (SELECT/INSERT/UPDATE/DELETE): no DDL, no admin rights.

Usage (needs the project venv, which has psycopg and azure-identity):
    $APP_MI_OID = az identity show -g $RG -n id-orders-api --query principalId -o tsv
    .\\.venv\\Scripts\\python.exe scripts\\azure_db_bootstrap.py `
        --server-fqdn <fqdn> --admin-upn <you@domain> --app-object-id $APP_MI_OID
"""

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import psycopg  # noqa: E402
from azure.identity import AzureCliCredential  # noqa: E402
from psycopg import sql  # noqa: E402

from app.orders import migrate  # noqa: E402
from app.orders.config import Settings  # noqa: E402
from app.orders.db import ENTRA_POSTGRES_SCOPE  # noqa: E402


def admin_settings(server_fqdn: str, admin_upn: str, database: str) -> Settings:
    """Settings for connecting as the Entra admin.

    Every value this script depends on is passed explicitly. Explicit values win over environment
    variables, so leftovers in the shell (e.g. local FAULTS_ENABLED / FAULT_ADMIN_TOKEN) can't
    interfere. Fault injection and telemetry are irrelevant here and switched off.
    """
    return Settings(
        _env_file=None,
        environment="azure",
        db_host=server_fqdn,
        db_port=5432,
        db_name=database,
        db_user=admin_upn,
        db_auth_mode="entra",
        db_sslmode="require",
        faults_enabled=False,
        fault_admin_token=None,
        applicationinsights_connection_string="",
    )


_GUID = re.compile(r"^[0-9a-fA-F]{8}-([0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}$")


def _guid(value: str) -> str:
    if not _GUID.match(value):
        raise argparse.ArgumentTypeError(
            f"{value!r} is not an object ID (GUID). Get it with: "
            "az identity show -g $RG -n id-orders-api --query principalId -o tsv"
        )
    return value.lower()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap Azure PostgreSQL for orders-api")
    parser.add_argument("--server-fqdn", required=True)
    parser.add_argument(
        "--admin-upn", required=True, help="Your Entra UPN (the server's Entra admin)"
    )
    parser.add_argument(
        "--app-object-id",
        required=True,
        type=_guid,
        help="Object (principal) ID of the app's managed identity",
    )
    parser.add_argument(
        "--app-role", default="id-orders-api", help="PostgreSQL role name to create"
    )
    parser.add_argument("--database", default="orders")
    return parser.parse_args(argv)


def create_principal_call(role: str, object_id: str) -> tuple[str, tuple]:
    """Create the Entra role bound to the identity's object ID, not its (possibly shared) name."""
    return (
        "SELECT * FROM pgaadauth_create_principal_with_oid(%s, %s, %s, %s, %s)",
        (role, object_id, "service", False, False),
    )


def main() -> int:
    args = parse_args()

    # 1. Migrations, as the admin (DB_AUTH_MODE=entra uses your `az login` token).
    settings = admin_settings(args.server_fqdn, args.admin_upn, args.database)
    applied = migrate.run(settings, migrate.DEFAULT_DIR)
    print(f"[1/3] migrations applied this run: {applied or 'none (already up to date)'}")

    token = AzureCliCredential().get_token(ENTRA_POSTGRES_SCOPE).token

    def connect(dbname: str) -> psycopg.Connection:
        return psycopg.connect(
            host=args.server_fqdn,
            port=5432,
            dbname=dbname,
            user=args.admin_upn,
            password=token,
            sslmode="require",
            autocommit=True,
        )

    # 2. Role for the managed identity (Entra principals are created from the `postgres` database).
    with connect("postgres") as conn:
        exists = conn.execute(
            "SELECT 1 FROM pg_roles WHERE rolname = %s", (args.app_role,)
        ).fetchone()
        if exists:
            print(f"[2/3] role {args.app_role!r} already exists")
        else:
            conn.execute(*create_principal_call(args.app_role, args.app_object_id))
            print(f"[2/3] created Entra role {args.app_role!r} for object ID {args.app_object_id}")

    # 3. Least-privilege grants: data access only.
    role = sql.Identifier(args.app_role)
    statements = [
        sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(args.database), role),
        sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(role),
        sql.SQL("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {}").format(
            role
        ),
        sql.SQL("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {}").format(role),
        sql.SQL(
            "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
            "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {}"
        ).format(role),
        sql.SQL(
            "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO {}"
        ).format(role),
    ]
    with connect(args.database) as conn:
        for statement in statements:
            conn.execute(statement)
    print(f"[3/3] granted data-only access on {args.database!r} to {args.app_role!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
