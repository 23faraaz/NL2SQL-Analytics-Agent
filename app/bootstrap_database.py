"""Create or reconcile the production application's read-only PostgreSQL role."""

from __future__ import annotations

import logging
import os

import psycopg2
from psycopg2 import sql

logger = logging.getLogger(__name__)


def required_environment(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Required environment variable {name} is not set")
    return value


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
