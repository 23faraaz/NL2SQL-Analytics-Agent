from __future__ import annotations

import csv
import json
import os
import sys
from pathlib import Path

import psycopg2
from psycopg2.extensions import connection as PostgreSQLConnection

from etl.config import PROCESSED_DATA_DIR
from etl.logging_config import get_logger

logger = get_logger(__name__)


PROJECT_ROOT = Path(__file__).resolve().parents[1]

SCHEMA_FILES = [
    PROJECT_ROOT / "sql" / "001_schema.sql",
    PROJECT_ROOT / "sql" / "002_views.sql",
    PROJECT_ROOT / "sql" / "003_indexes.sql",
    PROJECT_ROOT / "sql" / "migrations" / "004_dataset_imports.sql",
]

# FK-safe load order. product_variants and order_items are populated by
# S4b synthetic augmentation and will not exist as processed CSVs until
# that stage has run -- COMMERCE_TABLES lists every table this loader
# knows how to load; load_commerce() loads whichever of their processed
# CSVs are actually present, in this order, so it can be run identically
# after S4a alone (partial, expected) or after S4a+S4b (complete).
COMMERCE_TABLES = [
    "categories",
    "suppliers",
    "customers",
    "products",
    "product_variants",
    "orders",
    "order_items",
    "payments",
]


def get_database_connection() -> PostgreSQLConnection:
    """
    Create a PostgreSQL connection.

    DATABASE_URL is preferred. Otherwise DB_* environment variables are
    used (matching app/db.py's convention), with POSTGRES_* accepted as
    fallbacks for compatibility with the official postgres image's own
    variable names.
    """

    database_url = os.getenv("DATABASE_URL")

    try:
        if database_url:
            logger.info("Connecting to PostgreSQL using DATABASE_URL")

            return psycopg2.connect(database_url)

        logger.info(
            "Connecting to PostgreSQL using DB_*/POSTGRES_* environment variables"
        )

        return psycopg2.connect(
            host=os.getenv("DB_HOST", os.getenv("POSTGRES_HOST", "localhost")),
            port=int(os.getenv("DB_PORT", os.getenv("POSTGRES_PORT", "5432"))),
            dbname=os.getenv("DB_NAME", os.getenv("POSTGRES_DB", "nl2sql")),
            user=os.getenv("DB_USER", os.getenv("POSTGRES_USER", "postgres")),
            password=os.getenv(
                "DB_PASSWORD", os.getenv("POSTGRES_PASSWORD", "postgres")
            ),
        )

    except psycopg2.Error:
        logger.exception("Failed to connect to PostgreSQL")
        raise


def find_available_processed_files() -> list[str]:
    """
    Return the COMMERCE_TABLES names that have a processed CSV on disk,
    in load order. Tables without a processed CSV yet (e.g.
    product_variants / a fully augmented order_items before S4b has run)
    are skipped rather than treated as an error, so this loader is safe
    to run at either the S4a or the S4a+S4b checkpoint.
    """

    available = [
        table_name
        for table_name in COMMERCE_TABLES
        if (PROCESSED_DATA_DIR / f"{table_name}.csv").is_file()
    ]

    missing = [
        table_name for table_name in COMMERCE_TABLES if table_name not in available
    ]

    if missing:
        logger.warning(
            "No processed CSV found yet for: %s (expected before S4b "
            "synthetic augmentation has run)",
            ", ".join(missing),
        )

    if not available:
        raise FileNotFoundError(f"No processed CSV files found in {PROCESSED_DATA_DIR}")

    return available


def execute_schema(
    connection: PostgreSQLConnection,
) -> None:
    """
    Execute the canonical commerce schema: tables, views, then indexes,
    in that order.
    """

    for schema_file in SCHEMA_FILES:
        if not schema_file.is_file():
            raise FileNotFoundError(f"Required schema file is missing: {schema_file}")

        schema_sql = schema_file.read_text(encoding="utf-8")

        if not schema_sql.strip():
            raise ValueError(f"Schema file is empty: {schema_file}")

        logger.info(
            "Executing schema file: %s",
            schema_file.name,
        )

        with connection.cursor() as cursor:
            cursor.execute(schema_sql)

    logger.info("Commerce schema created successfully")


def count_csv_rows(
    csv_path: Path,
) -> int:
    """
    Count data rows in a CSV file, excluding its header.
    """

    with csv_path.open(
        mode="r",
        encoding="utf-8",
        newline="",
    ) as csv_file:
        reader = csv.reader(csv_file)

        try:
            next(reader)
        except StopIteration:
            return 0

        return sum(1 for _ in reader)


def read_csv_header(
    csv_path: Path,
) -> list[str]:
    with csv_path.open(
        mode="r",
        encoding="utf-8",
        newline="",
    ) as csv_file:
        reader = csv.reader(csv_file)

        try:
            return next(reader)
        except StopIteration:
            return []


def load_csv_into_table(
    connection: PostgreSQLConnection,
    table_name: str,
) -> int:
    """
    Load one processed CSV file into its commerce table using COPY.

    The COPY column list is taken directly from the CSV's own header
    rather than assumed, so a table can be loaded with only the columns
    its processed CSV actually provides -- every column not present
    falls back to its schema DEFAULT (or NULL, for nullable columns
    with no default).
    """

    csv_path = PROCESSED_DATA_DIR / f"{table_name}.csv"

    expected_rows = count_csv_rows(csv_path)

    if expected_rows == 0:
        raise ValueError(f"Processed CSV contains no data rows: {csv_path}")

    columns = read_csv_header(csv_path)
    column_list = ", ".join(columns)

    copy_statement = (
        f"COPY commerce.{table_name} ({column_list}) "
        "FROM STDIN "
        "WITH ("
        "FORMAT CSV, "
        "HEADER TRUE, "
        "NULL ''"
        ")"
    )

    logger.info(
        "Loading %s into commerce.%s (%d columns)",
        csv_path.name,
        table_name,
        len(columns),
    )

    with csv_path.open(
        mode="r",
        encoding="utf-8",
        newline="",
    ) as csv_file:
        with connection.cursor() as cursor:
            cursor.copy_expert(
                copy_statement,
                csv_file,
            )

    logger.info(
        "Loaded commerce.%s (%d rows expected)",
        table_name,
        expected_rows,
    )

    return expected_rows


def get_table_row_count(
    connection: PostgreSQLConnection,
    table_name: str,
) -> int:
    """
    Return the number of rows currently stored in a commerce table.
    """

    query = f"SELECT COUNT(*) FROM commerce.{table_name}"

    with connection.cursor() as cursor:
        cursor.execute(query)
        result = cursor.fetchone()

    if result is None:
        raise RuntimeError(f"Could not read row count for commerce.{table_name}")

    return int(result[0])


def verify_table_row_count(
    connection: PostgreSQLConnection,
    table_name: str,
    expected_rows: int,
) -> None:
    """
    Confirm that the PostgreSQL table row count matches the CSV.
    """

    actual_rows = get_table_row_count(
        connection,
        table_name,
    )

    if actual_rows != expected_rows:
        raise ValueError(
            f"Row-count mismatch for commerce.{table_name}: "
            f"expected={expected_rows:,}, "
            f"actual={actual_rows:,}"
        )

    logger.info(
        "Verified commerce.%s row count (%d rows)",
        table_name,
        actual_rows,
    )


def verify_foreign_key_integrity(
    connection: PostgreSQLConnection,
    loaded_tables: list[str],
) -> None:
    """
    Verify the commerce relationships between tables that were actually
    loaded in this run.
    """

    all_relationship_queries = {
        ("orders", "customers"): (
            "orders.customer_id -> customers.customer_id",
            """
            SELECT COUNT(*)
            FROM commerce.orders AS child
            LEFT JOIN commerce.customers AS parent
                ON child.customer_id = parent.customer_id
            WHERE parent.customer_id IS NULL
            """,
        ),
        ("products", "categories"): (
            "products.category_id -> categories.category_id",
            """
            SELECT COUNT(*)
            FROM commerce.products AS child
            LEFT JOIN commerce.categories AS parent
                ON child.category_id = parent.category_id
            WHERE child.category_id IS NOT NULL
              AND parent.category_id IS NULL
            """,
        ),
        ("product_variants", "products"): (
            "product_variants.product_id -> products.product_id",
            """
            SELECT COUNT(*)
            FROM commerce.product_variants AS child
            LEFT JOIN commerce.products AS parent
                ON child.product_id = parent.product_id
            WHERE parent.product_id IS NULL
            """,
        ),
        ("order_items", "orders"): (
            "order_items.order_id -> orders.order_id",
            """
            SELECT COUNT(*)
            FROM commerce.order_items AS child
            LEFT JOIN commerce.orders AS parent
                ON child.order_id = parent.order_id
            WHERE parent.order_id IS NULL
            """,
        ),
        ("order_items", "product_variants"): (
            "order_items.variant_id -> product_variants.variant_id",
            """
            SELECT COUNT(*)
            FROM commerce.order_items AS child
            LEFT JOIN commerce.product_variants AS parent
                ON child.variant_id = parent.variant_id
            WHERE parent.variant_id IS NULL
            """,
        ),
        ("payments", "orders"): (
            "payments.order_id -> orders.order_id",
            """
            SELECT COUNT(*)
            FROM commerce.payments AS child
            LEFT JOIN commerce.orders AS parent
                ON child.order_id = parent.order_id
            WHERE parent.order_id IS NULL
            """,
        ),
    }

    loaded_set = set(loaded_tables)

    applicable_queries = {
        name: query
        for (child, parent), (name, query) in all_relationship_queries.items()
        if child in loaded_set and parent in loaded_set
    }

    logger.info(
        "Starting commerce relationship verification (%d applicable of "
        "%d known relationships, given %d tables loaded)",
        len(applicable_queries),
        len(all_relationship_queries),
        len(loaded_tables),
    )

    with connection.cursor() as cursor:
        for relationship, query in applicable_queries.items():
            cursor.execute(query)
            result = cursor.fetchone()

            orphan_count = int(result[0]) if result is not None else -1

            if orphan_count != 0:
                raise ValueError(
                    f"Commerce relationship failed: "
                    f"{relationship} contains "
                    f"{orphan_count:,} orphan rows"
                )

            logger.info(
                "Verified commerce relationship: %s",
                relationship,
            )

    logger.info("Commerce relationship verification completed successfully")


def load_commerce(
    *,
    dataset_id: str | None = None,
    source_version: str | None = None,
    require_empty: bool = False,
) -> None:
    """
    Create the canonical commerce schema and populate it with whichever
    processed CSVs are currently available.
    """

    logger.info("Starting PostgreSQL commerce load")

    tables_to_load = find_available_processed_files()

    connection: PostgreSQLConnection | None = None

    try:
        connection = get_database_connection()
        connection.autocommit = False

        execute_schema(connection)

        if dataset_id is not None:
            if len(dataset_id) != 64 or any(
                character not in "0123456789abcdef" for character in dataset_id
            ):
                raise ValueError("dataset_id must be a lowercase SHA-256 value")
            if not source_version:
                raise ValueError("source_version is required for a production import")

            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_advisory_xact_lock(hashtext(%s))",
                    ("nl2sql-dataset-import",),
                )
                cursor.execute(
                    "SELECT 1 FROM public.nl2sql_dataset_imports WHERE dataset_id = %s",
                    (dataset_id,),
                )
                if cursor.fetchone() is not None:
                    connection.rollback()
                    logger.info(
                        "Dataset %s was already imported; no changes made", dataset_id
                    )
                    return

        if require_empty:
            if set(tables_to_load) != set(COMMERCE_TABLES):
                missing = sorted(set(COMMERCE_TABLES) - set(tables_to_load))
                raise ValueError(
                    "Production import requires every processed table; missing: "
                    + ", ".join(missing)
                )
            existing_counts = {
                table_name: get_table_row_count(connection, table_name)
                for table_name in COMMERCE_TABLES
            }
            nonempty = {
                table_name: count
                for table_name, count in existing_counts.items()
                if count > 0
            }
            if nonempty:
                raise ValueError(
                    "Production commerce tables are not empty; refusing replacement import"
                )

        expected_row_counts: dict[str, int] = {}

        for table_name in tables_to_load:
            expected_row_counts[table_name] = load_csv_into_table(
                connection,
                table_name,
            )

        for table_name, expected_rows in expected_row_counts.items():
            verify_table_row_count(
                connection,
                table_name,
                expected_rows,
            )

        verify_foreign_key_integrity(
            connection,
            tables_to_load,
        )

        if dataset_id is not None and source_version is not None:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO public.nl2sql_dataset_imports
                        (dataset_id, source_version, table_row_counts)
                    VALUES (%s, %s, %s::jsonb)
                    """,
                    (dataset_id, source_version, json.dumps(expected_row_counts)),
                )

        connection.commit()

        logger.info(
            "PostgreSQL commerce load completed successfully (%d of %d "
            "tables loaded: %s)",
            len(tables_to_load),
            len(COMMERCE_TABLES),
            ", ".join(tables_to_load),
        )

    except Exception:
        if connection is not None:
            connection.rollback()

            logger.info("Commerce transaction rolled back")

        logger.exception("PostgreSQL commerce load failed")

        raise

    finally:
        if connection is not None:
            connection.close()

            logger.info("PostgreSQL connection closed")


def main() -> int:
    try:
        load_commerce()
        return 0

    except Exception:
        return 1


if __name__ == "__main__":
    sys.exit(main())
