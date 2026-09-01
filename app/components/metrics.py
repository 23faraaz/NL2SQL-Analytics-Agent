from decimal import Decimal

import streamlit as st


def render_result_summary(
    row_count: int,
    execution_ms: float,
    truncated: bool,
) -> None:
    columns = st.columns(3)

    columns[0].metric(
        "Rows returned",
        f"{row_count:,}",
    )

    columns[1].metric(
        "Execution time",
        f"{execution_ms:.0f} ms",
    )

    columns[2].metric(
        "Result status",
        "Truncated" if truncated else "Complete",
    )


def format_currency(value: int | float | Decimal) -> str:
    return f"£{float(value):,.2f}"
