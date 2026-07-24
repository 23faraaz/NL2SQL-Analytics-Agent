from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

import psycopg2
from psycopg2.extensions import connection as PostgreSQLConnection

from etl.logging_config import get_logger


logger = get_logger(__name__)


PROJECT_ROOT = Path(__file__).resolve().parents[1]

SCHEMA_FILE = (
    PROJECT_ROOT
    / "sql"
    / "warehouse"
    / "001_create_schema.sql"
)

PROCESSED_DATA_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
)

WAREHOUSE_TABLES = [
    "customers",
    "categories",
    "products",
    "suppliers",
    "orders",
    "order_items",
    "payments",
]


def get_database_connection() -> PostgreSQLConnection:
    """
    Create a PostgreSQL connection.

    DATABASE_URL is preferred. If it is unavailable, individual
    POSTGRES_* environment variables are used.
    """

    database_url = os.getenv("DATABASE_URL")

    try:
        if database_url:
            logger.info(
                "Connecting to PostgreSQL using DATABASE_URL"
            )

            return psycopg2.connect(database_url)

        logger.info(
            "Connecting to PostgreSQL using POSTGRES environment variables"
        )

        return psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            dbname=os.getenv(
                "POSTGRES_DB",
                "nl2sql",
            ),
            user=os.getenv(
                "POSTGRES_USER",
                "postgres",
            ),
            password=os.getenv(
                "POSTGRES_PASSWORD",
                "postgres",
            ),
        )

    except psycopg2.Error:
        logger.exception(
            "Failed to connect to PostgreSQL"
        )
        raise


def validate_required_files() -> None:
    """
    Verify that the schema SQL file and all processed CSV files exist.
    """

    missing_files: list[Path] = []

    if not SCHEMA_FILE.is_file():
        missing_files.append(SCHEMA_FILE)

    for table_name in WAREHOUSE_TABLES:
        csv_path = (
            PROCESSED_DATA_DIR
            / f"{table_name}.csv"
        )

        if not csv_path.is_file():
            missing_files.append(csv_path)

    if missing_files:
        formatted_files = "\n".join(
            f"  - {path}"
            for path in missing_files
        )

        raise FileNotFoundError(
            "Required warehouse files are missing:\n"
            f"{formatted_files}"
        )

    logger.info(
        "Validated schema file and %d processed CSV files",
        len(WAREHOUSE_TABLES),
    )


def execute_schema(
    connection: PostgreSQLConnection,
) -> None:
    """
    Execute the PostgreSQL warehouse schema.
    """

    logger.info(
        "Executing warehouse schema: %s",
        SCHEMA_FILE,
    )

    schema_sql = SCHEMA_FILE.read_text(
        encoding="utf-8"
    )

    if not schema_sql.strip():
        raise ValueError(
            f"Warehouse schema file is empty: {SCHEMA_FILE}"
        )

    with connection.cursor() as cursor:
        cursor.execute(schema_sql)

    logger.info(
        "Warehouse schema created successfully"
    )


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


def load_csv_into_table(
    connection: PostgreSQLConnection,
    table_name: str,
) -> int:
    """
    Load one processed CSV file into its warehouse table using COPY.
    """

    csv_path = (
        PROCESSED_DATA_DIR
        / f"{table_name}.csv"
    )

    expected_rows = count_csv_rows(
        csv_path
    )

    if expected_rows == 0:
        raise ValueError(
            f"Processed CSV contains no data rows: {csv_path}"
        )

    copy_statement = (
        f"COPY warehouse.{table_name} "
        "FROM STDIN "
        "WITH ("
        "FORMAT CSV, "
        "HEADER TRUE, "
        "NULL ''"
        ")"
    )

    logger.info(
        "Loading %s into warehouse.%s",
        csv_path.name,
        table_name,
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
        "Loaded warehouse.%s (%d rows expected)",
        table_name,
        expected_rows,
    )

    return expected_rows


def get_table_row_count(
    connection: PostgreSQLConnection,
    table_name: str,
) -> int:
    """
    Return the number of rows currently stored in a warehouse table.
    """

    query = (
        f"SELECT COUNT(*) "
        f"FROM warehouse.{table_name}"
    )

    with connection.cursor() as cursor:
        cursor.execute(query)
        result = cursor.fetchone()

    if result is None:
        raise RuntimeError(
            f"Could not read row count for warehouse.{table_name}"
        )

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
            f"Row-count mismatch for warehouse.{table_name}: "
            f"expected={expected_rows:,}, "
            f"actual={actual_rows:,}"
        )

    logger.info(
        "Verified warehouse.%s row count (%d rows)",
        table_name,
        actual_rows,
    )


def verify_foreign_key_integrity(
    connection: PostgreSQLConnection,
) -> None:
    """
    Verify the main warehouse relationships after loading.
    """

    relationship_queries = {
        "orders.customer_id -> customers.customer_id": """
            SELECT COUNT(*)
            FROM warehouse.orders AS child
            LEFT JOIN warehouse.customers AS parent
                ON child.customer_id = parent.customer_id
            WHERE parent.customer_id IS NULL
        """,
        "products.category_id -> categories.category_id": """
            SELECT COUNT(*)
            FROM warehouse.products AS child
            LEFT JOIN warehouse.categories AS parent
                ON child.category_id = parent.category_id
            WHERE child.category_id IS NOT NULL
              AND parent.category_id IS NULL
        """,
        "order_items.order_id -> orders.order_id": """
            SELECT COUNT(*)
            FROM warehouse.order_items AS child
            LEFT JOIN warehouse.orders AS parent
                ON child.order_id = parent.order_id
            WHERE parent.order_id IS NULL
        """,
        "order_items.product_id -> products.product_id": """
            SELECT COUNT(*)
            FROM warehouse.order_items AS child
            LEFT JOIN warehouse.products AS parent
                ON child.product_id = parent.product_id
            WHERE parent.product_id IS NULL
        """,
        "order_items.supplier_id -> suppliers.supplier_id": """
            SELECT COUNT(*)
            FROM warehouse.order_items AS child
            LEFT JOIN warehouse.suppliers AS parent
                ON child.supplier_id = parent.supplier_id
            WHERE parent.supplier_id IS NULL
        """,
        "payments.order_id -> orders.order_id": """
            SELECT COUNT(*)
            FROM warehouse.payments AS child
            LEFT JOIN warehouse.orders AS parent
                ON child.order_id = parent.order_id
            WHERE parent.order_id IS NULL
        """,
    }

    logger.info(
        "Starting warehouse relationship verification"
    )

    with connection.cursor() as cursor:
        for relationship, query in relationship_queries.items():
            cursor.execute(query)
            result = cursor.fetchone()

            orphan_count = (
                int(result[0])
                if result is not None
                else -1
            )

            if orphan_count != 0:
                raise ValueError(
                    f"Warehouse relationship failed: "
                    f"{relationship} contains "
                    f"{orphan_count:,} orphan rows"
                )

            logger.info(
                "Verified warehouse relationship: %s",
                relationship,
            )

    logger.info(
        "Warehouse relationship verification completed successfully"
    )


def load_warehouse() -> None:
    """
    Create and populate the PostgreSQL warehouse.
    """

    logger.info(
        "Starting PostgreSQL warehouse load"
    )

    validate_required_files()

    connection: PostgreSQLConnection | None = None

    try:
        connection = get_database_connection()
        connection.autocommit = False

        execute_schema(connection)

        expected_row_counts: dict[str, int] = {}

        for table_name in WAREHOUSE_TABLES:
            expected_row_counts[table_name] = (
                load_csv_into_table(
                    connection,
                    table_name,
                )
            )

        for table_name, expected_rows in (
            expected_row_counts.items()
        ):
            verify_table_row_count(
                connection,
                table_name,
                expected_rows,
            )

        verify_foreign_key_integrity(
            connection
        )

        connection.commit()

        logger.info(
            "PostgreSQL warehouse load completed successfully"
        )

    except Exception:
        if connection is not None:
            connection.rollback()

            logger.info(
                "Warehouse transaction rolled back"
            )

        logger.exception(
            "PostgreSQL warehouse load failed"
        )

        raise

    finally:
        if connection is not None:
            connection.close()

            logger.info(
                "PostgreSQL connection closed"
            )


def main() -> int:
    try:
        load_warehouse()
        return 0

    except Exception:
        return 1


if __name__ == "__main__":
    sys.exit(main())