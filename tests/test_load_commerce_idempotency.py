from unittest.mock import MagicMock

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
