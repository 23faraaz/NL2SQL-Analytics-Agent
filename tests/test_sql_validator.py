"""
Tests for app/sql_validator.py -- the safety gate between LLM-generated
SQL and the database. No database or external service is required; this
module only tokenizes text.
"""

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from sql_validator import SQLValidationError, validate_select_only  # noqa: E402


# ---------------------------------------------------------------------
# Valid SQL that must pass.
# ---------------------------------------------------------------------

VALID_QUERIES = [
    "SELECT 1",
    "SELECT * FROM commerce.customers",
    "select * from commerce.customers",  # case-insensitive
    "SELECT customer_id, first_name FROM commerce.customers WHERE customer_id = 1",
    "SELECT c.customer_id FROM commerce.customers c JOIN commerce.orders o ON o.customer_id = c.customer_id",
    "SELECT COUNT(*) FROM commerce.orders GROUP BY status",
    "SELECT * FROM commerce.orders ORDER BY order_date DESC LIMIT 10",
    "WITH recent AS (SELECT * FROM commerce.orders) SELECT * FROM recent",
    "select 1;",  # trailing semicolon stripped, not rejected
    "  SELECT 1  ",  # surrounding whitespace
]


@pytest.mark.parametrize("sql", VALID_QUERIES)
def test_valid_select_queries_pass(sql):
    result = validate_select_only(sql)
    assert isinstance(result, str)
    assert result  # non-empty


def test_valid_query_returns_cleaned_sql_without_trailing_semicolon():
    result = validate_select_only("SELECT 1;")
    assert result == "SELECT 1"


def test_valid_query_strips_surrounding_whitespace():
    result = validate_select_only("   SELECT 1   ")
    assert result == "SELECT 1"


# ---------------------------------------------------------------------
# Empty / missing input.
# ---------------------------------------------------------------------


@pytest.mark.parametrize("sql", ["", "   ", ";", ";;;", None])
def test_empty_or_missing_sql_is_rejected(sql):
    with pytest.raises(SQLValidationError):
        validate_select_only(sql)


# ---------------------------------------------------------------------
# Forbidden statement types -- the core safety guarantee.
# ---------------------------------------------------------------------

FORBIDDEN_STATEMENTS = [
    "INSERT INTO commerce.customers (first_name) VALUES ('x')",
    "UPDATE commerce.customers SET first_name = 'x'",
    "DELETE FROM commerce.customers",
    "DROP TABLE commerce.customers",
    "ALTER TABLE commerce.customers ADD COLUMN x TEXT",
    "TRUNCATE commerce.customers",
    "CREATE TABLE evil (id INT)",
    "GRANT ALL ON commerce.customers TO public",
    "REVOKE ALL ON commerce.customers FROM public",
    "CALL some_procedure()",
    "EXECUTE some_statement",
    # case-insensitivity of the forbidden-keyword scan
    "drop table commerce.customers",
    "Delete From commerce.customers",
]


@pytest.mark.parametrize("sql", FORBIDDEN_STATEMENTS)
def test_forbidden_statement_types_are_rejected(sql):
    with pytest.raises(SQLValidationError):
        validate_select_only(sql)


# ---------------------------------------------------------------------
# Stacked / multiple statements -- the classic "SELECT 1; DROP TABLE x;"
# injection shape.
# ---------------------------------------------------------------------

STACKED_STATEMENTS = [
    "SELECT 1; DROP TABLE commerce.customers;",
    "SELECT * FROM commerce.customers; DELETE FROM commerce.orders;",
    "SELECT 1; SELECT 2;",  # even stacking two harmless SELECTs is rejected
]


@pytest.mark.parametrize("sql", STACKED_STATEMENTS)
def test_stacked_statements_are_rejected(sql):
    with pytest.raises(SQLValidationError):
        validate_select_only(sql)


# ---------------------------------------------------------------------
# A regex-based check would be fooled by comments or string literals
# containing forbidden words -- sqlparse's tokenization must not be.
# These prove both directions: false rejection does not happen for
# benign text, and the belt-and-braces keyword scan still fires when a
# forbidden keyword is a real token, not decoration.
# ---------------------------------------------------------------------


def test_comment_containing_forbidden_word_does_not_cause_false_rejection():
    sql = "SELECT 1 -- this is not a DROP statement"
    result = validate_select_only(sql)
    assert "SELECT 1" in result


def test_string_literal_containing_forbidden_word_does_not_cause_false_rejection():
    sql = "SELECT * FROM commerce.customers WHERE last_name = 'DROP'"
    result = validate_select_only(sql)
    assert "DROP" in result  # the literal survives -- it was never a keyword


def test_column_alias_containing_forbidden_word_does_not_cause_false_rejection():
    sql = "SELECT customer_id AS delete_candidate FROM commerce.customers"
    result = validate_select_only(sql)
    assert "delete_candidate" in result


# ---------------------------------------------------------------------
# SELECT ... INTO can still write data in some engines -- must be
# rejected even though it starts with SELECT.
# ---------------------------------------------------------------------


def test_select_into_is_rejected():
    with pytest.raises(SQLValidationError):
        validate_select_only(
            "SELECT * INTO new_table FROM commerce.customers"
        )


# ---------------------------------------------------------------------
# Unparseable input.
# ---------------------------------------------------------------------


def test_garbage_input_is_rejected():
    with pytest.raises(SQLValidationError):
        validate_select_only("this is not sql at all @#$%")


# ---------------------------------------------------------------------
# Error messages must be informative enough to show a user, and must
# never be silently swallowed by callers (module docstring's own
# invariant) -- verified here by confirming the exception always carries
# a non-empty, specific message.
# ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "sql",
    [
        "",
        "DROP TABLE x",
        "SELECT 1; DROP TABLE x;",
    ],
)
def test_validation_errors_carry_a_specific_message(sql):
    with pytest.raises(SQLValidationError) as exc_info:
        validate_select_only(sql)

    assert str(exc_info.value).strip()
