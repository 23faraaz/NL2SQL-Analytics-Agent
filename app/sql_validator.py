"""
SQL validator - the safety gate between "Claude generated some SQL" and
"we run that SQL against a real database".

WHY sqlparse INSTEAD OF REGEX:
A regex check like `if "DROP" in sql.upper()` is trivially bypassed - a
comment, a string literal containing the word, or unicode tricks can slip
past it. sqlparse actually tokenizes the SQL and lets us inspect the real
statement type, which is what lets us reliably:
  1. Reject anything that isn't a single SELECT statement
  2. Reject stacked statements (e.g. "SELECT 1; DROP TABLE users;")
  3. Reject SELECT ... INTO (which can still write data in some engines)

This is deliberately conservative - false rejections (blocking a valid
SELECT) are a UX annoyance, false acceptances (letting a DROP through) are
a data-loss incident. Bias toward rejecting anything ambiguous.
"""

import logging
import sqlparse
from sqlparse.sql import Statement
from sqlparse.tokens import DML, DDL, CTE

logger = logging.getLogger(__name__)

# Statement types we will NEVER execute, regardless of framing.
FORBIDDEN_KEYWORDS = {
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE",
    "CREATE", "GRANT", "REVOKE", "REPLACE", "MERGE", "CALL",
    "EXECUTE", "EXEC",
}


class SQLValidationError(Exception):
    """Raised when generated SQL fails validation. Never caught silently -
    the caller must surface this to the user, not swallow it."""
    pass


def validate_select_only(sql: str) -> str:
    """
    Validates that `sql` is exactly one read-only SELECT statement.
    Returns the cleaned SQL string if valid, raises SQLValidationError if not.
    """
    if not sql or not sql.strip():
        raise SQLValidationError("Generated SQL was empty.")

    cleaned = sql.strip().rstrip(";").strip()

    parsed = sqlparse.parse(cleaned)

    if len(parsed) == 0:
        raise SQLValidationError("Could not parse the generated SQL.")

    if len(parsed) > 1:
        # More than one statement parsed out - this is exactly the
        # "SELECT 1; DROP TABLE x;" attack shape. Reject outright.
        logger.warning("Rejected SQL: multiple statements detected")
        raise SQLValidationError(
            "Generated SQL contains multiple statements. Only a single "
            "SELECT statement is allowed."
        )

    statement: Statement = parsed[0]
    stmt_type = statement.get_type()

    # get_type() returns 'SELECT', 'INSERT', 'UNKNOWN', etc. A CTE
    # ("WITH x AS (...) SELECT ...") can report as UNKNOWN, so we also
    # check the first meaningful token as a fallback.
    first_token = statement.token_first(skip_cm=True)
    starts_with_select_or_with = first_token is not None and (
        first_token.ttype in (DML, CTE)
        and first_token.value.upper() in ("SELECT", "WITH")
    )

    if stmt_type != "SELECT" and not starts_with_select_or_with:
        logger.warning("Rejected SQL: statement type was '%s'", stmt_type)
        raise SQLValidationError(
            f"Only SELECT statements are permitted. Detected statement "
            f"type: {stmt_type}."
        )

    # Belt-and-braces keyword scan across every token, in case a forbidden
    # keyword shows up somewhere unexpected (e.g. inside a CTE alongside
    # a legitimate SELECT - "WITH x AS (DELETE ...) SELECT * FROM x" is
    # not valid SQL anyway, but we don't rely on that assumption).
    for token in statement.flatten():
        if token.ttype in (DDL, DML) and token.value.upper() in FORBIDDEN_KEYWORDS:
            logger.warning("Rejected SQL: forbidden keyword '%s' found", token.value)
            raise SQLValidationError(
                f"Generated SQL contains a forbidden keyword: {token.value.upper()}. "
                f"Only read-only SELECT queries are permitted."
            )

    logger.info("SQL passed validation")
    return cleaned