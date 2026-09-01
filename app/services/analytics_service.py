import time

import pandas as pd

import db
from models.query_result import QueryResult

DEFAULT_DISPLAY_LIMIT = 1_000


def execute_analytics_query(
    sql: str,
    display_limit: int = DEFAULT_DISPLAY_LIMIT,
) -> QueryResult:
    """
    Executes validated analytical SQL and converts the result into
    a pandas DataFrame suitable for charts and interactive tables.

    SQL safety validation must happen before this function is called.
    """
    started_at = time.perf_counter()

    columns, rows = db.execute_query(sql)

    execution_ms = (time.perf_counter() - started_at) * 1_000

    dataframe = pd.DataFrame(rows, columns=columns)

    truncated = len(dataframe) > display_limit

    if truncated:
        dataframe = dataframe.head(display_limit)

    return QueryResult(
        dataframe=dataframe,
        sql=sql,
        row_count=len(rows),
        execution_ms=execution_ms,
        truncated=truncated,
    )
