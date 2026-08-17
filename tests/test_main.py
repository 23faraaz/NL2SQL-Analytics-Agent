"""
Tests for the pure decision logic in app/main.py -- specifically
is_single_value_metric_result(), which gates whether execute_pipeline()
uses a deterministic explanation instead of calling explain_results().

app/main.py has Streamlit module-level calls (st.set_page_config, etc.)
that run at import time; Streamlit supports this "bare mode" (it logs a
warning and continues) so the module can be imported directly here, the
same way it is imported when Streamlit runs the script itself.
"""

import sys
from pathlib import Path

import pandas as pd

APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import main  # noqa: E402
from services.chart_service import ChartRecommendation, recommend_chart  # noqa: E402


def test_single_row_single_numeric_column_is_metric():
    df = pd.DataFrame({"total_revenue": [1234.56]})
    recommendation = recommend_chart(df)

    assert main.is_single_value_metric_result(df, recommendation) is True


def test_single_row_with_extra_non_numeric_column_is_not_metric():
    # "Which product has the highest revenue?" -- one row, but the
    # product name would be silently dropped by a numeric-only check.
    df = pd.DataFrame(
        {
            "product_name": ["Widget"],
            "total_revenue": [1234.56],
        }
    )
    recommendation = recommend_chart(df)

    # recommend_chart still classifies this as "metric" (it only checks
    # the numeric-column count), which is exactly the overly-broad
    # condition is_single_value_metric_result() must additionally guard
    # against.
    assert recommendation.chart_type == "metric"
    assert main.is_single_value_metric_result(df, recommendation) is False


def test_multi_row_result_is_not_metric():
    df = pd.DataFrame({"total_revenue": [100.0, 200.0, 300.0]})
    recommendation = recommend_chart(df)

    assert main.is_single_value_metric_result(df, recommendation) is False


def test_single_row_non_numeric_column_is_not_metric():
    df = pd.DataFrame({"customer_name": ["Ada Lovelace"]})
    recommendation = recommend_chart(df)

    assert recommendation.chart_type != "metric"
    assert main.is_single_value_metric_result(df, recommendation) is False


def test_empty_result_is_not_metric():
    df = pd.DataFrame({"total_revenue": []})
    recommendation = recommend_chart(df)

    assert main.is_single_value_metric_result(df, recommendation) is False


def test_two_numeric_columns_single_row_is_not_metric():
    df = pd.DataFrame({"total_revenue": [1234.56], "total_orders": [42]})
    recommendation = recommend_chart(df)

    assert main.is_single_value_metric_result(df, recommendation) is False


def test_directly_constructed_metric_recommendation_requires_matching_shape():
    # Guards against a mismatched recommendation/dataframe pair (for
    # example if a caller reuses a stale recommendation) still being
    # rejected rather than trusted blindly.
    df = pd.DataFrame(
        {
            "product_name": ["Widget"],
            "total_revenue": [1234.56],
        }
    )
    recommendation = ChartRecommendation(
        chart_type="metric",
        y_column="total_revenue",
        title="Total Revenue",
    )

    assert main.is_single_value_metric_result(df, recommendation) is False
