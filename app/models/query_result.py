from dataclasses import dataclass

import pandas as pd


@dataclass
class QueryResult:
    dataframe: pd.DataFrame
    sql: str
    row_count: int
    execution_ms: float
    truncated: bool = False
