import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import bootstrap_database  # noqa: E402
from bootstrap_database import (  # noqa: E402
    apply_migrations,
    bootstrap_application_role,
    discover_migrations,
    required_environment,
)


def test_required_environment_rejects_missing_value(monkeypatch):
    monkeypatch.delenv("REQUIRED_TEST_VALUE", raising=False)

    with pytest.raises(RuntimeError, match="REQUIRED_TEST_VALUE"):
        required_environment("REQUIRED_TEST_VALUE")


def test_discover_migrations_orders_versioned_sql(tmp_path):
    (tmp_path / "002_second.sql").write_text("SELECT 2;")
    (tmp_path / "001_first.sql").write_text("SELECT 1;")
    (tmp_path / "notes.sql").write_text("SELECT 0;")

    assert [path.name for path in discover_migrations(tmp_path)] == [
        "001_first.sql",
        "002_second.sql",
    ]


def test_apply_migrations_rejects_checksum_drift(tmp_path):
    migration = tmp_path / "001_initial.sql"
    migration.write_text("SELECT 1;")
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value = [(migration.name, "wrong-checksum")]

    with pytest.raises(RuntimeError, match="checksum changed"):
        apply_migrations(connection, tmp_path)


def test_production_migrations_contain_no_drop_statements():
    migrations = Path(__file__).resolve().parents[1] / "sql" / "migrations"

    for migration in discover_migrations(migrations):
        assert "DROP " not in migration.read_text(encoding="utf-8").upper()


def test_bootstrap_creates_missing_role_and_grants_access():
    connection = MagicMock()
    connection.info.dbname = "nl2sql_ecommerce"
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = None

    bootstrap_application_role(connection, "nl2sql_app", "not-logged")

    statements = [str(call.args[0]) for call in cursor.execute.call_args_list]
    assert any("CREATE ROLE" in statement for statement in statements)
    assert any("GRANT SELECT ON ALL TABLES" in statement for statement in statements)
    assert not any("DROP" in statement for statement in statements)


def test_bootstrap_updates_existing_role_password():
    connection = MagicMock()
    connection.info.dbname = "nl2sql_ecommerce"
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = (1,)

    bootstrap_application_role(connection, "nl2sql_app", "replacement")

    statements = [str(call.args[0]) for call in cursor.execute.call_args_list]
    assert any("ALTER ROLE" in statement for statement in statements)
    assert not any("CREATE ROLE" in statement for statement in statements)


@patch("bootstrap_database.psycopg2.connect")
def test_main_rolls_back_and_closes_on_failure(connect, monkeypatch):
    for name, value in {
        "DB_HOST": "database.internal",
        "DB_NAME": "nl2sql_ecommerce",
        "DB_MASTER_USER": "master",
        "DB_MASTER_PASSWORD": "master-password",
        "DB_APP_USER": "nl2sql_app",
        "DB_APP_PASSWORD": "application-password",
    }.items():
        monkeypatch.setenv(name, value)

    connection = connect.return_value
    with patch.object(
        bootstrap_database,
        "bootstrap_application_role",
        side_effect=RuntimeError("failed"),
    ):
        with pytest.raises(RuntimeError, match="failed"):
            bootstrap_database.main()

    connection.rollback.assert_called_once_with()
    connection.close.assert_called_once_with()
