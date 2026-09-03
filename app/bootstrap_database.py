"""Create or reconcile the production application's read-only PostgreSQL role."""

from __future__ import annotations

import logging
import os
from hashlib import sha256
from pathlib import Path

import psycopg2
from psycopg2 import sql

logger = logging.getLogger(__name__)
DEFAULT_MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "sql" / "migrations"


def required_environment(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Required environment variable {name} is not set")
    return value


def discover_migrations(directory: Path) -> list[Path]:
    migrations = sorted(directory.glob("[0-9][0-9][0-9]_*.sql"))
    if not migrations:
        raise RuntimeError(f"No production migrations found in {directory}")
    return migrations


def apply_migrations(connection, directory: Path) -> None:
    """Apply each immutable migration once and reject checksum drift."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_advisory_xact_lock(hashtext(%s))", ("nl2sql-migrations",)
        )
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS public.nl2sql_schema_migrations (
                version TEXT PRIMARY KEY,
                checksum TEXT NOT NULL,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """)
        cursor.execute("SELECT version, checksum FROM public.nl2sql_schema_migrations")
        applied = dict(cursor.fetchall())

        for migration in discover_migrations(directory):
            content = migration.read_bytes()
            checksum = sha256(content).hexdigest()
            previous_checksum = applied.get(migration.name)
            if previous_checksum is not None:
                if previous_checksum != checksum:
                    raise RuntimeError(
                        f"Applied migration checksum changed: {migration.name}"
                    )
                continue

            logger.info("Applying database migration %s", migration.name)
            cursor.execute(content.decode("utf-8-sig"))
            cursor.execute(
                """
                INSERT INTO public.nl2sql_schema_migrations (version, checksum)
                VALUES (%s, %s)
                """,
                (migration.name, checksum),
            )


def bootstrap_application_role(connection, username: str, password: str) -> None:
    """Idempotently create the login role and grant read-only commerce access."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (username,))
        role_exists = cursor.fetchone() is not None

        if role_exists:
            cursor.execute(
                sql.SQL("ALTER ROLE {} WITH LOGIN PASSWORD %s").format(
                    sql.Identifier(username)
                ),
                (password,),
            )
        else:
            cursor.execute(
                sql.SQL("CREATE ROLE {} WITH LOGIN PASSWORD %s").format(
                    sql.Identifier(username)
                ),
                (password,),
            )

        database_name = connection.info.dbname
        cursor.execute(
            sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                sql.Identifier(database_name), sql.Identifier(username)
            )
        )
        cursor.execute("CREATE SCHEMA IF NOT EXISTS commerce")
        cursor.execute(
            sql.SQL("GRANT USAGE ON SCHEMA commerce TO {}").format(
                sql.Identifier(username)
            )
        )
        cursor.execute(
            sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA commerce TO {}").format(
                sql.Identifier(username)
            )
        )
        cursor.execute(
            sql.SQL(
                "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA commerce TO {}"
            ).format(sql.Identifier(username))
        )
        cursor.execute(
            sql.SQL(
                "ALTER DEFAULT PRIVILEGES IN SCHEMA commerce "
                "GRANT SELECT ON TABLES TO {}"
            ).format(sql.Identifier(username))
        )
        cursor.execute(
            sql.SQL(
                "ALTER DEFAULT PRIVILEGES IN SCHEMA commerce "
                "GRANT USAGE, SELECT ON SEQUENCES TO {}"
            ).format(sql.Identifier(username))
        )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    connection = psycopg2.connect(
        host=required_environment("DB_HOST"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=required_environment("DB_NAME"),
        user=required_environment("DB_MASTER_USER"),
        password=required_environment("DB_MASTER_PASSWORD"),
        connect_timeout=15,
        sslmode="require",
    )
    try:
        migrations_dir = Path(os.getenv("MIGRATIONS_DIR", DEFAULT_MIGRATIONS_DIR))
        apply_migrations(connection, migrations_dir)
        bootstrap_application_role(
            connection,
            required_environment("DB_APP_USER"),
            required_environment("DB_APP_PASSWORD"),
        )
        connection.commit()
        logger.info("Database application role reconciled successfully")
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    main()
