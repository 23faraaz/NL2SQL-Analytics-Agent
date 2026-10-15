from pathlib import Path
from unittest.mock import MagicMock

import pytest

from scripts import load_commerce


def test_existing_production_dataset_is_checked_before_schema_execution(monkeypatch):
    connection = MagicMock()
    cursor = MagicMock()
    connection.cursor.return_value.__enter__.return_value = cursor
    cursor.fetchone.side_effect = [("public.nl2sql_dataset_imports",), (1,)]

    monkeypatch.setattr(
        load_commerce,
        "find_available_processed_files",
        lambda: list(load_commerce.COMMERCE_TABLES),
    )
    monkeypatch.setattr(load_commerce, "get_database_connection", lambda: connection)
    execute_schema = MagicMock()
    monkeypatch.setattr(load_commerce, "execute_schema", execute_schema)

    load_commerce.load_commerce(
        dataset_id="a" * 64,
        source_version="version-1",
        require_empty=True,
    )

    execute_schema.assert_not_called()
    connection.rollback.assert_called_once_with()
    connection.commit.assert_not_called()


def test_execute_schema_strips_utf8_byte_order_mark(monkeypatch, tmp_path):
    schema_file = tmp_path / "migration.sql"
    schema_file.write_text("\ufeffSELECT 1;", encoding="utf-8")
    connection = MagicMock()
    cursor = MagicMock()
    connection.cursor.return_value.__enter__.return_value = cursor
    monkeypatch.setattr(load_commerce, "SCHEMA_FILES", [schema_file])

    load_commerce.execute_schema(connection)

    cursor.execute.assert_called_once_with("SELECT 1;")


def test_repeated_local_load_skips_matching_database(monkeypatch):
    connection = MagicMock()
    tables = ["categories", "customers"]
    expected_counts = {"categories": 72, "customers": 99_441}

    monkeypatch.setattr(load_commerce, "find_available_processed_files", lambda: tables)
    monkeypatch.setattr(load_commerce, "get_database_connection", lambda: connection)
    monkeypatch.setattr(load_commerce, "execute_schema", MagicMock())
    monkeypatch.setattr(
        load_commerce,
        "count_csv_rows",
        lambda path: expected_counts[Path(path).stem],
    )
    monkeypatch.setattr(
        load_commerce,
        "get_table_row_count",
        lambda _connection, table_name: expected_counts[table_name],
    )
    load_csv = MagicMock()
    monkeypatch.setattr(load_commerce, "load_csv_into_table", load_csv)

    load_commerce.load_commerce(skip_if_already_loaded=True)

    load_csv.assert_not_called()
    connection.rollback.assert_called_once_with()
    connection.commit.assert_not_called()


def test_repeated_local_load_rejects_mismatched_database(monkeypatch):
    connection = MagicMock()
    tables = ["categories", "customers"]
    expected_counts = {"categories": 72, "customers": 99_441}
    actual_counts = {"categories": 72, "customers": 10}

    monkeypatch.setattr(load_commerce, "find_available_processed_files", lambda: tables)
    monkeypatch.setattr(load_commerce, "get_database_connection", lambda: connection)
    monkeypatch.setattr(load_commerce, "execute_schema", MagicMock())
    monkeypatch.setattr(
        load_commerce,
        "count_csv_rows",
        lambda path: expected_counts[Path(path).stem],
    )
    monkeypatch.setattr(
        load_commerce,
        "get_table_row_count",
        lambda _connection, table_name: actual_counts[table_name],
    )
    load_csv = MagicMock()
    monkeypatch.setattr(load_commerce, "load_csv_into_table", load_csv)

    with pytest.raises(ValueError, match="Mismatched tables: customers"):
        load_commerce.load_commerce(skip_if_already_loaded=True)

    load_csv.assert_not_called()
    connection.rollback.assert_called_once_with()
    connection.commit.assert_not_called()


def test_empty_local_database_loads_normally(monkeypatch):
    connection = MagicMock()
    tables = ["categories"]

    monkeypatch.setattr(load_commerce, "find_available_processed_files", lambda: tables)
    monkeypatch.setattr(load_commerce, "get_database_connection", lambda: connection)
    monkeypatch.setattr(load_commerce, "execute_schema", MagicMock())
    monkeypatch.setattr(load_commerce, "count_csv_rows", lambda _path: 72)
    monkeypatch.setattr(load_commerce, "get_table_row_count", lambda *_args: 0)
    monkeypatch.setattr(load_commerce, "verify_table_row_count", MagicMock())
    monkeypatch.setattr(load_commerce, "verify_foreign_key_integrity", MagicMock())
    load_csv = MagicMock(return_value=72)
    monkeypatch.setattr(load_commerce, "load_csv_into_table", load_csv)

    load_commerce.load_commerce(skip_if_already_loaded=True)

    load_csv.assert_called_once_with(connection, "categories")
    connection.commit.assert_called_once_with()
