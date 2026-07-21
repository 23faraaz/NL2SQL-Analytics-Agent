from decimal import Decimal

import altair as alt
import pandas as pd
import streamlit as st

from services.chart_service import (
    ChartRecommendation,
    format_label,
    prepare_dataframe,
)


CURRENCY_TERMS = {
    "revenue",
    "sales",
    "amount",
    "price",
    "value",
    "average_order_value",
    "lifetime_value",
    "profit",
}


def render_chart(
    df: pd.DataFrame,
    recommendation: ChartRecommendation,
) -> None:
    """Renders the recommended chart or KPI card."""

    if df.empty:
        return

    prepared_df = prepare_dataframe(df)

    if recommendation.chart_type == "metric":
        render_metric(
            prepared_df,
            recommendation.y_column,
        )
        return

    if recommendation.chart_type == "line":
        render_line_chart(prepared_df, recommendation)
        return

    if recommendation.chart_type == "bar":
        render_bar_chart(prepared_df, recommendation)
        return

    if recommendation.chart_type == "scatter":
        render_scatter_chart(prepared_df, recommendation)


def render_metric(df: pd.DataFrame, column: str | None) -> None:
    if column is None:
        return

    value = df.iloc[0][column]

    st.metric(
        label=format_label(column),
        value=format_value(column, value),
    )


def render_line_chart(
    df: pd.DataFrame,
    recommendation: ChartRecommendation,
) -> None:
    if not recommendation.x_column or not recommendation.y_column:
        return

    chart = (
        alt.Chart(df)
        .mark_line(point=True)
        .encode(
            x=alt.X(
                recommendation.x_column,
                title=format_label(recommendation.x_column),
            ),
            y=alt.Y(
                recommendation.y_column,
                title=format_label(recommendation.y_column),
            ),
            tooltip=[
                alt.Tooltip(column, title=format_label(column))
                for column in df.columns
            ],
        )
        .properties(
            title=recommendation.title,
            height=380,
        )
        .interactive()
    )

    st.altair_chart(chart, use_container_width=True)


def render_bar_chart(
    df: pd.DataFrame,
    recommendation: ChartRecommendation,
) -> None:
    if not recommendation.x_column or not recommendation.y_column:
        return

    # Horizontal bars make customer and product names easier to read.
    chart = (
        alt.Chart(df)
        .mark_bar(cornerRadiusEnd=4)
        .encode(
            x=alt.X(
                recommendation.y_column,
                title=format_label(recommendation.y_column),
            ),
            y=alt.Y(
                recommendation.x_column,
                sort="-x",
                title=format_label(recommendation.x_column),
            ),
            tooltip=[
                alt.Tooltip(column, title=format_label(column))
                for column in df.columns
            ],
        )
        .properties(
            title=recommendation.title,
            height=max(320, min(len(df) * 38, 650)),
        )
    )

    st.altair_chart(chart, use_container_width=True)


def render_scatter_chart(
    df: pd.DataFrame,
    recommendation: ChartRecommendation,
) -> None:
    if not recommendation.x_column or not recommendation.y_column:
        return

    chart = (
        alt.Chart(df)
        .mark_circle(size=100)
        .encode(
            x=alt.X(
                recommendation.x_column,
                title=format_label(recommendation.x_column),
            ),
            y=alt.Y(
                recommendation.y_column,
                title=format_label(recommendation.y_column),
            ),
            tooltip=[
                alt.Tooltip(column, title=format_label(column))
                for column in df.columns
            ],
        )
        .properties(
            title=recommendation.title,
            height=380,
        )
        .interactive()
    )

    st.altair_chart(chart, use_container_width=True)


def format_value(column: str, value) -> str:
    column_lower = column.lower()

    is_currency = any(
        term in column_lower
        for term in CURRENCY_TERMS
    )

    if isinstance(value, Decimal):
        value = float(value)

    if isinstance(value, float):
        prefix = "£" if is_currency else ""
        return f"{prefix}{value:,.2f}"

    if isinstance(value, int):
        prefix = "£" if is_currency else ""
        return f"{prefix}{value:,}"

    return str(value)