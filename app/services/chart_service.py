from dataclasses import dataclass
from typing import Literal

import pandas as pd


ChartType = Literal["metric", "line", "bar", "scatter", "table"]


@dataclass
class ChartRecommendation:
    chart_type: ChartType
    x_column: str | None = None
    y_column: str | None = None
    title: str | None = None


def recommend_chart(df: pd.DataFrame) -> ChartRecommendation:
    """
    Selects a visualisation deterministically from the result structure.

    The LLM does not generate chart code.
    """
    if df.empty:
        return ChartRecommendation(chart_type="table")

    prepared_df = prepare_dataframe(df)

    numeric_columns = list(
        prepared_df.select_dtypes(include=["number"]).columns
    )

    datetime_columns = [
        column
        for column in prepared_df.columns
        if pd.api.types.is_datetime64_any_dtype(prepared_df[column])
    ]

    categorical_columns = [
        column
        for column in prepared_df.columns
        if column not in numeric_columns
        and column not in datetime_columns
    ]

    # One row with one numerical answer: KPI card.
    if len(prepared_df) == 1 and len(numeric_columns) == 1:
        metric_column = numeric_columns[0]

        return ChartRecommendation(
            chart_type="metric",
            y_column=metric_column,
            title=format_label(metric_column),
        )

    # Time plus number: trend chart.
    if datetime_columns and numeric_columns:
        return ChartRecommendation(
            chart_type="line",
            x_column=datetime_columns[0],
            y_column=select_best_numeric_column(numeric_columns),
            title="Trend over time",
        )

    # Category plus number: ranked bar chart.
    if categorical_columns and numeric_columns and len(prepared_df) <= 30:
        return ChartRecommendation(
            chart_type="bar",
            x_column=categorical_columns[0],
            y_column=select_best_numeric_column(numeric_columns),
            title="Comparison",
        )

    # Two numerical variables: scatter plot.
    if len(numeric_columns) >= 2 and len(prepared_df) > 1:
        return ChartRecommendation(
            chart_type="scatter",
            x_column=numeric_columns[0],
            y_column=numeric_columns[1],
            title="Relationship",
        )

    return ChartRecommendation(chart_type="table")


def prepare_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Attempts to recognise dates returned by PostgreSQL as strings or objects.
    """
    prepared_df = df.copy()

    for column in prepared_df.columns:
        lowered = column.lower()

        looks_like_date = any(
            token in lowered
            for token in ("date", "month", "year", "time", "created_at")
        )

        if looks_like_date:
            converted = pd.to_datetime(
                prepared_df[column],
                errors="coerce",
            )

            if converted.notna().any():
                prepared_df[column] = converted

    return prepared_df


def select_best_numeric_column(columns: list[str]) -> str:
    """
    Prefers business metrics over identifiers and technical counts.
    """
    priority_terms = [
        "revenue",
        "sales",
        "total_amount",
        "lifetime_value",
        "average_order_value",
        "profit",
        "orders",
        "customers",
        "quantity",
        "count",
    ]

    for term in priority_terms:
        for column in columns:
            if term in column.lower():
                return column

    non_identifier_columns = [
        column
        for column in columns
        if not column.lower().endswith("_id")
        and column.lower() != "id"
    ]

    return non_identifier_columns[0] if non_identifier_columns else columns[0]


def format_label(column: str) -> str:
    return column.replace("_", " ").strip().title()