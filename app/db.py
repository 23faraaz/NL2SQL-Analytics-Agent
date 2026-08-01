from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from psycopg2.extensions import connection as PostgreSQLConnection

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"

load_dotenv(dotenv_path=ENV_FILE)

logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    """Raised when a database connection or query operation fails."""


def _get_connection_params() -> dict[str, Any]:
    """
    Build PostgreSQL connection parameters from environment variables.

    Supported variable names:

        DB_HOST
        DB_PORT
        DB_NAME
        DB_USER
        DB_PASSWORD

    POSTGRES_* variables are supported as fallbacks.
    """

    return {
        "host": os.getenv(
            "DB_HOST",
            os.getenv("POSTGRES_HOST", "localhost"),
        ),
        "port": int(
            os.getenv(
                "DB_PORT",
                os.getenv("POSTGRES_PORT", "5432"),
            )
        ),
        "dbname": os.getenv(
            "DB_NAME",
            os.getenv("POSTGRES_DB", "nl2sql_ecommerce"),
        ),
        "user": os.getenv(
            "DB_USER",
            os.getenv("POSTGRES_USER", "nl2sql_app"),
        ),
        "password": os.getenv(
            "DB_PASSWORD",
            os.getenv("POSTGRES_PASSWORD", ""),
        ),
        "connect_timeout": 10,
    }


def get_connection() -> PostgreSQLConnection:
    """
    Create and return a PostgreSQL database connection.

    DATABASE_URL is used when available. Otherwise, individual
    DB_* or POSTGRES_* environment variables are used.
    """

    database_url = os.getenv("DATABASE_URL")

    try:
        if database_url:
            logger.info(
                "Connecting to PostgreSQL using DATABASE_URL"
            )

            return psycopg2.connect(
                database_url,
                connect_timeout=10,
            )

        connection_params = _get_connection_params()

        logger.info(
            "Connecting to PostgreSQL database %s at %s:%s",
            connection_params["dbname"],
            connection_params["host"],
            connection_params["port"],
        )

        return psycopg2.connect(
            **connection_params
        )

    except psycopg2.Error as error:
        logger.error(
            "Database connection failed: %s",
            error,
        )

        raise DatabaseError(
            f"Could not connect to PostgreSQL: {error}"
        ) from error


def get_schema_description() -> str:
    """
    Introspect the warehouse schema and return a plain-text description
    suitable for the SQL-generation prompt.
    """

    columns_query = """
        SELECT
            c.table_schema,
            c.table_name,
            c.column_name,
            c.data_type,
            c.is_nullable
        FROM information_schema.columns AS c
        JOIN information_schema.tables AS t
            ON c.table_schema = t.table_schema
           AND c.table_name = t.table_name
        WHERE c.table_schema = 'warehouse'
          AND t.table_type = 'BASE TABLE'
        ORDER BY
            c.table_name,
            c.ordinal_position;
    """

    foreign_keys_query = """
        SELECT
            tc.table_schema AS source_schema,
            tc.table_name AS source_table,
            kcu.column_name AS source_column,
            ccu.table_schema AS target_schema,
            ccu.table_name AS target_table,
            ccu.column_name AS target_column
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
            ON tc.constraint_name = kcu.constraint_name
           AND tc.constraint_schema = kcu.constraint_schema
        JOIN information_schema.constraint_column_usage AS ccu
            ON tc.constraint_name = ccu.constraint_name
           AND tc.constraint_schema = ccu.constraint_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.table_schema = 'warehouse'
        ORDER BY
            tc.table_name,
            kcu.column_name;
    """

    try:
        with get_connection() as connection:
            with connection.cursor(
                cursor_factory=psycopg2.extras.RealDictCursor
            ) as cursor:
                cursor.execute(columns_query)
                columns = cursor.fetchall()

                cursor.execute(foreign_keys_query)
                foreign_keys = cursor.fetchall()

    except DatabaseError:
        raise

    except psycopg2.Error as error:
        logger.error(
            "Warehouse schema introspection failed: %s",
            error,
        )

        raise DatabaseError(
            "Could not introspect the warehouse schema: "
            f"{error}"
        ) from error

    if not columns:
        raise DatabaseError(
            "No base tables were found in the warehouse schema"
        )

    tables: dict[str, list[str]] = {}

    for row in columns:
        table_name = str(row["table_name"])
        column_name = str(row["column_name"])
        data_type = str(row["data_type"])

        nullable = (
            "NULL"
            if row["is_nullable"] == "YES"
            else "NOT NULL"
        )

        tables.setdefault(
            table_name,
            [],
        ).append(
            f"  - {column_name} "
            f"({data_type}, {nullable})"
        )

    lines = [
        "DATABASE: PostgreSQL",
        "SCHEMA: warehouse",
        "",
        "SQL GENERATION RULES:",
        "  - Generate exactly one read-only SELECT query.",
        "  - Common table expressions must end in a SELECT query.",
        "  - Use only the tables and columns listed below.",
        "  - Fully qualify every table as warehouse.<table_name>.",
        "  - Use PostgreSQL syntax.",
        "  - Use the listed foreign keys when joining tables.",
        "  - Do not invent tables, columns, or relationships.",
        "  - Do not use INSERT, UPDATE, DELETE, DROP, ALTER, "
        "TRUNCATE, CREATE, GRANT, REVOKE, COPY, or CALL.",
        "",
    ]

    for table_name, table_columns in tables.items():
        lines.append(
            f"TABLE warehouse.{table_name}:"
        )

        lines.extend(
            table_columns
        )

        lines.append("")

    if foreign_keys:
        lines.append(
            "FOREIGN KEYS:"
        )

        for foreign_key in foreign_keys:
            lines.append(
                f"  - {foreign_key['source_schema']}."
                f"{foreign_key['source_table']}."
                f"{foreign_key['source_column']} -> "
                f"{foreign_key['target_schema']}."
                f"{foreign_key['target_table']}."
                f"{foreign_key['target_column']}"
            )

    schema_text = "\n".join(
        lines
    ).strip()

    logger.info(
        "Warehouse schema introspected successfully: %d tables",
        len(tables),
    )

    return schema_text


def execute_query(
    sql: str,
    params: tuple[Any, ...] | None = None,
) -> tuple[list[str], list[tuple[Any, ...]]]:
    """
    Execute a validated read-only SQL query.

    The SQL should already have been checked by sql_validator, unless it
    is trusted, developer-written, parameterized SQL (e.g. the
    Customer Analytics MVP's fixed service-layer queries), which never
    passes through the LLM and does not need that validator.

    params, when given, are bound with a parameterized cursor.execute()
    call (standard psycopg2 %s placeholders) rather than interpolated
    into the SQL string.

    Returns:
        A tuple containing:
        - a list of column names
        - a list of result rows
    """

    if not isinstance(sql, str):
        raise DatabaseError(
            "SQL query must be a string"
        )

    cleaned_sql = sql.strip()

    if not cleaned_sql:
        raise DatabaseError(
            "SQL query cannot be empty"
        )

    connection: PostgreSQLConnection | None = None

    try:
        connection = get_connection()

        # Enforce read-only behaviour at the PostgreSQL transaction level.
        connection.set_session(
            readonly=True,
            autocommit=False,
        )

        with connection.cursor() as cursor:
            # Limit query execution time.
            cursor.execute(
                "SET LOCAL statement_timeout = '10s';"
            )

            # Use the warehouse schema by default.
            cursor.execute(
                "SET LOCAL search_path TO warehouse, public;"
            )

            cursor.execute(
                cleaned_sql,
                params,
            )

            if cursor.description is None:
                raise DatabaseError(
                    "The SQL query did not return a result set"
                )

            columns = [
                description.name
                for description in cursor.description
            ]

            rows = cursor.fetchall()

            connection.commit()

            logger.info(
                "Query executed successfully: %d rows returned",
                len(rows),
            )

            return columns, rows

    except DatabaseError:
        if connection is not None:
            connection.rollback()

        raise

    except psycopg2.Error as error:
        if connection is not None:
            connection.rollback()

        logger.error(
            "Query execution failed: %s",
            error,
        )

        raise DatabaseError(
            f"Query execution failed: {error}"
        ) from error

    finally:
        if connection is not None:
            connection.close()

            logger.debug(
                "PostgreSQL connection closed"
            )

def get_database_metadata() -> dict:
    """
    Return high-level metadata about the warehouse.

    This is used by the LLM to interpret relative date phrases such as
    "last month" against the dataset's latest available business date.
    """

    sql = """
    SELECT
        MIN(ordered_at) AS earliest_order,
        MAX(ordered_at) AS latest_order,
        COUNT(*) AS total_orders
    FROM warehouse.orders;
    """

    columns, rows = execute_query(sql)

    if not rows:
        return {
            "status": "unavailable",
            "earliest_order": None,
            "latest_order": None,
            "total_orders": 0,
        }

    earliest_order, latest_order, total_orders = rows[0]

    return {
        "status": "available",
        "earliest_order": (
            earliest_order.isoformat()
            if earliest_order is not None
            else None
        ),
        "latest_order": (
            latest_order.isoformat()
            if latest_order is not None
            else None
        ),
        "total_orders": int(total_orders),
        "dataset_type": "historical",
        "relative_date_anchor": (
            latest_order.isoformat()
            if latest_order is not None
            else None
        ),
    }