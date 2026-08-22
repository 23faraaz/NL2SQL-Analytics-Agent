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


# ---------------------------------------------------------------------
# Unanswerable-question fallback
# ---------------------------------------------------------------------


def test_is_unanswerable_result_detects_sentinel():
    sql = "SELECT 'QUESTION_CANNOT_BE_ANSWERED_FROM_AVAILABLE_SCHEMA' AS error"

    assert main._is_unanswerable_result(sql) is True


def test_is_unanswerable_result_false_for_normal_sql():
    sql = "SELECT COUNT(*) FROM commerce.orders"

    assert main._is_unanswerable_result(sql) is False


def test_format_month_year_parses_iso_timestamp():
    assert main._format_month_year("2018-10-17T17:30:18+01:00") == "October 2018"


def test_format_month_year_returns_none_for_invalid_input():
    assert main._format_month_year("") is None
    assert main._format_month_year("not-a-date") is None


def test_build_unanswerable_explanation_includes_real_date_range(monkeypatch):
    monkeypatch.setattr(
        main.db,
        "get_database_metadata",
        lambda: {
            "earliest_order": "2016-09-04T21:15:19+01:00",
            "latest_order": "2018-10-17T17:30:18+01:00",
        },
    )

    explanation = main._build_unanswerable_explanation()

    assert "September 2016" in explanation
    assert "October 2018" in explanation


def test_build_unanswerable_explanation_falls_back_when_metadata_unavailable(
    monkeypatch,
):
    monkeypatch.setattr(
        main.db,
        "get_database_metadata",
        lambda: {"status": "unavailable"},
    )

    explanation = main._build_unanswerable_explanation()

    assert "cannot be answered" in explanation
    assert "September" not in explanation


def test_build_unanswerable_explanation_handles_database_error(monkeypatch):
    def _raise(*args, **kwargs):
        raise main.db.DatabaseError("connection lost")

    monkeypatch.setattr(main.db, "get_database_metadata", _raise)

    explanation = main._build_unanswerable_explanation()

    assert "cannot be answered" in explanation
