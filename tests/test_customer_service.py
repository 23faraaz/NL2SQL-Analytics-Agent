"""
Tests for app/services/customer_service.py.

Validation-logic tests (limit/customer_id checks, parameterization) run
unconditionally with no dependencies. Query-behaviour tests (ordering,
filtering, tier assignment, empty handling) exercise real SQL against a
real PostgreSQL database, because those are genuinely database behaviours
-- a mocked db.execute_query would only prove this module calls a mock
correctly, not that the ORDER BY, WHERE, or GROUP BY clauses are right.

These integration tests need a reachable PostgreSQL server (DB_HOST /
DB_PORT / DB_TEST_NAME / DB_USER / DB_PASSWORD, matching app/db.py's
convention) and are skipped cleanly, not failed, if one is not available.
Every one of them is marked @pytest.mark.integration (registered in
pytest.ini) specifically so a skipped run cannot be mistaken for a
passing integration validation: a bare `pytest` run that shows
"skipped" is not proof this module's SQL behaviour was ever exercised.
Run `pytest -m integration` to confirm these actually ran (not
skipped), or `pytest -m "not integration"` to run only the
dependency-free validation-logic tests.
"""

import os
import sys
from pathlib import Path

import psycopg2
import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SQL_DIR = PROJECT_ROOT / "sql"

TEST_DB_NAME = os.getenv("DB_TEST_NAME", "customer_service_test")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")


def _admin_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname="postgres",
        user=DB_USER,
        password=DB_PASSWORD,
        connect_timeout=3,
    )


def _postgres_available() -> bool:
    try:
        conn = _admin_connection()
        conn.close()
        return True
    except psycopg2.OperationalError:
        return False


POSTGRES_AVAILABLE = _postgres_available()

# Applied only to the commerce_test_db fixture below, not module-wide --
# the pure validation-logic tests (limit/customer_id checks) need no
# database and always run, regardless of Postgres availability.
SKIP_REASON = (
    "No reachable PostgreSQL server for customer_service integration "
    "tests (checked DB_HOST/DB_PORT env vars, defaulting to "
    "localhost:5432)"
)


# Fixture customers, one per tier, with directly-set orders.total_amount
# so the expected commerce.customer_lifetime_metrics.net_lifetime_revenue
# (and therefore customer_value_tier) is known exactly, matching the
# view's thresholds in sql/002_views.sql (VIP>=1000, HIGH_VALUE>=500,
# REGULAR>=150, LOW_VALUE>0, NO_PURCHASE=0). Customer E has no orders at
# all -- NO_PURCHASE and excluded from top-N (which requires
# total_orders > 0).
FIXTURE_CUSTOMERS = [
    # (customer_id, name, order_total_amount_or_None)
    (1, "Alice VIP", 1200.00),
    (2, "Bob HighValue", 600.00),
    (3, "Carol Regular", 200.00),
    (4, "Dave LowValue", 50.00),
    (5, "Eve NoPurchase", None),
]

EXPECTED_TIER_BY_CUSTOMER_ID = {
    1: "VIP",
    2: "HIGH_VALUE",
    3: "REGULAR",
    4: "LOW_VALUE",
    5: "NO_PURCHASE",
}


@pytest.fixture(scope="module")
def commerce_test_db():
    if not POSTGRES_AVAILABLE:
        pytest.skip(SKIP_REASON)

    admin_conn = _admin_connection()
    admin_conn.autocommit = True

    with admin_conn.cursor() as cursor:
        cursor.execute(f'DROP DATABASE IF EXISTS "{TEST_DB_NAME}";')
        cursor.execute(f'CREATE DATABASE "{TEST_DB_NAME}";')

    admin_conn.close()

    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=TEST_DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )
    conn.autocommit = True

    with conn.cursor() as cursor:
        for schema_file in ["001_schema.sql", "002_views.sql"]:
            cursor.execute((SQL_DIR / schema_file).read_text())

        for customer_id, name, total_amount in FIXTURE_CUSTOMERS:
            first_name, last_name = name.split(" ", 1)

            cursor.execute(
                """
                INSERT INTO commerce.customers
                    (customer_id, first_name, last_name, email,
                     acquisition_channel)
                VALUES (%s, %s, %s, %s, 'DIRECT')
                """,
                (
                    customer_id,
                    first_name,
                    last_name,
                    f"{first_name.lower()}@example.com",
                ),
            )

            if total_amount is not None:
                cursor.execute(
                    """
                    INSERT INTO commerce.orders
                        (customer_id, order_number, order_date, status,
                         sales_channel, subtotal, total_amount)
                    VALUES
                        (%s, %s, now(), 'DELIVERED', 'WEBSITE', %s, %s)
                    """,
                    (
                        customer_id,
                        f"ORD-TEST-{customer_id}",
                        total_amount,
                        total_amount,
                    ),
                )

        # Restart the customer_id sequence past our manually-assigned
        # IDs so it never collides with them.
        cursor.execute("SELECT setval('commerce.customers_customer_id_seq', 1000);")

    conn.close()

    # Module-scoped: pytest's function-scoped `monkeypatch` fixture can't
    # be used here, so pytest.MonkeyPatch() is instantiated directly --
    # its .undo() restores every env var below to its pre-fixture value
    # (or deletes it if it was unset) once this module's tests finish.
    # Without this, DB_NAME would stay pointed at TEST_DB_NAME even after
    # it's dropped below, breaking any DB-touching test that runs later
    # in the same pytest session.
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("DB_HOST", DB_HOST)
    monkeypatch.setenv("DB_PORT", str(DB_PORT))
    monkeypatch.setenv("DB_NAME", TEST_DB_NAME)
    monkeypatch.setenv("DB_USER", DB_USER)
    monkeypatch.setenv("DB_PASSWORD", DB_PASSWORD)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    yield

    monkeypatch.undo()

    admin_conn = _admin_connection()
    admin_conn.autocommit = True
    with admin_conn.cursor() as cursor:
        cursor.execute(f'DROP DATABASE IF EXISTS "{TEST_DB_NAME}";')
    admin_conn.close()


# ---------------------------------------------------------------------
# Validation-logic tests: no database required.
# ---------------------------------------------------------------------

from services import customer_service  # noqa: E402  (after sys.path setup)


@pytest.mark.parametrize("bad_limit", [0, -1, -100])
def test_validate_limit_rejects_non_positive(bad_limit):
    with pytest.raises(customer_service.CustomerServiceError):
        customer_service._validate_limit(bad_limit)


def test_validate_limit_rejects_exceeding_max():
    with pytest.raises(customer_service.CustomerServiceError):
        customer_service._validate_limit(customer_service.MAX_TOP_N_LIMIT + 1)


@pytest.mark.parametrize("bad_limit", ["10", 10.5, None, True])
def test_validate_limit_rejects_wrong_type(bad_limit):
    with pytest.raises(customer_service.CustomerServiceError):
        customer_service._validate_limit(bad_limit)


def test_validate_limit_accepts_valid_value():
    assert customer_service._validate_limit(10) == 10
    assert customer_service._validate_limit(1) == 1
    assert (
        customer_service._validate_limit(customer_service.MAX_TOP_N_LIMIT)
        == customer_service.MAX_TOP_N_LIMIT
    )


@pytest.mark.parametrize("bad_id", [0, -1, "5", 5.5, None, True])
def test_validate_customer_id_rejects_invalid(bad_id):
    with pytest.raises(customer_service.CustomerServiceError):
        customer_service._validate_customer_id(bad_id)


def test_validate_customer_id_accepts_valid_value():
    assert customer_service._validate_customer_id(42) == 42


# ---------------------------------------------------------------------
# Query-behaviour tests: require commerce_test_db.
# ---------------------------------------------------------------------


@pytest.mark.integration
def test_top_n_ordering(commerce_test_db):
    result = customer_service.get_top_customers_by_lifetime_value(limit=10)

    # Customer 5 (no orders) must not appear -- total_orders > 0 filter.
    assert set(result["customer_id"]) == {1, 2, 3, 4}

    # Descending by net_lifetime_revenue: Alice(1200) > Bob(600) >
    # Carol(200) > Dave(50).
    assert result["customer_id"].tolist() == [1, 2, 3, 4]
    assert result["net_lifetime_revenue"].tolist() == [
        1200.00,
        600.00,
        200.00,
        50.00,
    ]


@pytest.mark.integration
def test_top_n_respects_limit(commerce_test_db):
    result = customer_service.get_top_customers_by_lifetime_value(limit=2)

    assert len(result) == 2
    assert result["customer_id"].tolist() == [1, 2]


@pytest.mark.integration
def test_order_history_filters_to_requested_customer_only(commerce_test_db):
    result = customer_service.get_customer_order_history(customer_id=1)

    assert not result.empty
    assert result["order_number"].tolist() == ["ORD-TEST-1"]
    # No cross-contamination from other customers' orders.
    assert all(order_number.endswith("-1") for order_number in result["order_number"])


@pytest.mark.integration
def test_order_history_for_customer_with_no_orders_is_empty_not_error(
    commerce_test_db,
):
    result = customer_service.get_customer_order_history(customer_id=5)

    assert result.empty


@pytest.mark.integration
def test_order_history_unknown_customer_raises(commerce_test_db):
    with pytest.raises(customer_service.CustomerServiceError):
        customer_service.get_customer_order_history(customer_id=999999)


@pytest.mark.integration
def test_tier_assignment_matches_expected_thresholds(commerce_test_db):
    breakdown = customer_service.get_customer_value_tier_breakdown()

    counts_by_tier = dict(
        zip(breakdown["customer_value_tier"], breakdown["customer_count"])
    )

    # Each of the 5 fixture customers falls into a distinct tier.
    for tier in EXPECTED_TIER_BY_CUSTOMER_ID.values():
        assert counts_by_tier.get(tier) == 1

    # Tier counts sum to the total customer count.
    assert int(breakdown["customer_count"].sum()) == len(FIXTURE_CUSTOMERS)

    # No customer appears in more than one tier: total across tiers
    # equals total distinct customers seen across all tiers combined.
    assert breakdown["customer_value_tier"].nunique() == len(breakdown)


@pytest.mark.integration
def test_tier_breakdown_display_order(commerce_test_db):
    breakdown = customer_service.get_customer_value_tier_breakdown()

    present_tiers = breakdown["customer_value_tier"].tolist()
    expected_order = [
        tier for tier in customer_service.TIER_DISPLAY_ORDER if tier in present_tiers
    ]

    assert present_tiers == expected_order


@pytest.mark.integration
def test_sql_is_parameterized_not_interpolated(commerce_test_db, monkeypatch):
    """
    The limit value must travel as a bound parameter, never formatted
    into the SQL string -- this is what actually prevents injection via
    this code path (on top of the type-level validation above).
    """

    captured = {}
    original_execute_query = db_module().execute_query

    def spy_execute_query(sql, params=None):
        captured["sql"] = sql
        captured["params"] = params
        return original_execute_query(sql, params)

    monkeypatch.setattr(db_module(), "execute_query", spy_execute_query)

    customer_service.get_top_customers_by_lifetime_value(limit=3)

    assert "%s" in captured["sql"]
    assert "3" not in captured["sql"]
    assert captured["params"] == (3,)


def db_module():
    import db

    return db
