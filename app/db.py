"""
Database layer: connection handling, schema introspection, and query execution.

WHY SCHEMA IS INTROSPECTED, NOT HARDCODED:
The SQL-generation prompt needs an accurate picture of the schema (table
names, column names, types, foreign keys). Hardcoding that as a string
constant means it silently goes stale the moment someone alters the
schema. Reading it live from information_schema means the prompt is
always correct without anyone remembering to update two places at once.
"""

import logging
import os
from contextlib import contextmanager

import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    """Wraps psycopg2 errors so callers don't need to import psycopg2
    themselves just to catch exceptions."""
    pass


def _get_connection_params() -> dict:
    """
    Reads connection params from environment variables. No defaults on the
    password - if it's missing, fail loudly rather than silently trying an
    empty password.
    """
    required = ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"]
    missing = [var for var in required if not os.environ.get(var)]
    if missing:
        raise DatabaseError(
            f"Missing required environment variables: {', '.join(missing)}"
        )

    return {
        "host": os.environ["DB_HOST"],
        "port": os.environ["DB_PORT"],
        "dbname": os.environ["DB_NAME"],
        "user": os.environ["DB_USER"],
        "password": os.environ["DB_PASSWORD"],
        "connect_timeout": 5,
    }


@contextmanager
def get_connection():
    """
    Context manager for a single database connection. Ensures the
    connection is always closed, even if the query raises.
    """
    conn = None
    try:
        params = _get_connection_params()
        conn = psycopg2.connect(**params)
        yield conn
    except psycopg2.OperationalError as e:
        logger.error("Database connection failed: %s", e)
        raise DatabaseError(f"Could not connect to the database: {e}") from e
    finally:
        if conn is not None:
            conn.close()


def get_schema_description() -> str:
    """
    Introspects the database schema and returns a plain-text description
    suitable for injecting into the SQL-generation prompt: table names,
    columns with types, and foreign key relationships.
    """
    query = """
        SELECT
            t.table_name,
            c.column_name,
            c.data_type,
            c.is_nullable
        FROM information_schema.tables t
        JOIN information_schema.columns c
            ON t.table_name = c.table_name
        WHERE t.table_schema = 'public'
            AND t.table_type = 'BASE TABLE'
        ORDER BY t.table_name, c.ordinal_position;
    """

    fk_query = """
        SELECT
            tc.table_name AS source_table,
            kcu.column_name AS source_column,
            ccu.table_name AS target_table,
            ccu.column_name AS target_column
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.constraint_column_usage ccu
            ON tc.constraint_name = ccu.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY';
    """

    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query)
            columns = cur.fetchall()

            cur.execute(fk_query)
            foreign_keys = cur.fetchall()

    # Group columns by table
    tables: dict[str, list[str]] = {}
    for row in columns:
        nullable = "NULL" if row["is_nullable"] == "YES" else "NOT NULL"
        tables.setdefault(row["table_name"], []).append(
            f"  - {row['column_name']} ({row['data_type']}, {nullable})"
        )

    lines = []
    for table_name, cols in tables.items():
        lines.append(f"TABLE {table_name}:")
        lines.extend(cols)
        lines.append("")

    if foreign_keys:
        lines.append("FOREIGN KEYS:")
        for fk in foreign_keys:
            lines.append(
                f"  - {fk['source_table']}.{fk['source_column']} -> "
                f"{fk['target_table']}.{fk['target_column']}"
            )

    schema_text = "\n".join(lines)
    logger.info("Schema introspected: %d tables", len(tables))
    return schema_text


def execute_query(sql: str) -> tuple[list[str], list[tuple]]:
    """
    Executes a validated SELECT query. Returns (column_names, rows).
    Caller is responsible for having already run this through
    sql_validator.validate_select_only() - this function does not
    re-validate, it trusts its input.

    A statement timeout is set so a pathological query (accidental cross
    join, huge aggregation) can't hang the app indefinitely.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute("SET statement_timeout = '10s';")
                cur.execute(sql)
                columns = [desc[0] for desc in cur.description] if cur.description else []
                rows = cur.fetchall()
                logger.info("Query executed successfully, %d rows returned", len(rows))
                return columns, rows
            except psycopg2.Error as e:
                logger.error("Query execution failed: %s", e)
                raise DatabaseError(f"Query execution failed: {e}") from e