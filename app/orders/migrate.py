"""Apply SQL migrations in migrations/*.sql, in file-name order, exactly once each.

Usage:  python -m app.orders.migrate
Uses the same DB_* settings as the app, so it works against local docker PostgreSQL (password)
and Azure PostgreSQL (Entra token via `az login` or managed identity).
"""

import logging
import os
import sys
import time
from pathlib import Path

import psycopg

from app.common.logging_setup import setup_logging
from app.orders.config import Settings
from app.orders.db import connection_parameters

logger = logging.getLogger("app.migrate")

DEFAULT_DIR = Path(__file__).resolve().parents[2] / "migrations"


def _connect(settings: Settings, attempts: int = 10, delay_seconds: float = 2.0):
    conninfo, kwargs, connection_class = connection_parameters(settings)
    for attempt in range(1, attempts + 1):
        try:
            return connection_class.connect(conninfo, **kwargs)
        except psycopg.OperationalError as exc:
            if attempt == attempts:
                raise
            logger.warning(
                "database not reachable yet, retrying",
                extra={"attempt": attempt, "error": type(exc).__name__},
            )
            time.sleep(delay_seconds)
    raise RuntimeError("unreachable")


def run(settings: Settings, migrations_dir: Path) -> list[str]:
    files = sorted(migrations_dir.glob("*.sql"))
    applied_now: list[str] = []
    with _connect(settings) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "version TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
        )
        conn.commit()
        done = {r["version"] for r in conn.execute("SELECT version FROM schema_migrations")}
        for path in files:
            if path.name in done:
                continue
            with conn.transaction():
                conn.execute(path.read_text(encoding="utf-8"))
                conn.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (path.name,))
            applied_now.append(path.name)
            logger.info("migration applied", extra={"event": "migration", "version": path.name})
    return applied_now


def main() -> int:
    settings = Settings()
    setup_logging("orders-migrate", settings.log_level)
    migrations_dir = Path(os.getenv("MIGRATIONS_DIR", str(DEFAULT_DIR)))
    applied = run(settings, migrations_dir)
    logger.info(
        "migrations complete",
        extra={"event": "migrations_complete", "applied": applied, "count": len(applied)},
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
