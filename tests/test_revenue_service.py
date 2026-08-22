"""
Tests for app/services/revenue_service.py.

revenue_service has no user-supplied parameters to validate (the whole
view is returned), so there is no validation logic to test the way
customer_service.py's limit/customer_id checks are tested. What's
tested here is the one real piece of logic this module has: wrapping
db.DatabaseError into RevenueServiceError so no raw database exception
reaches the UI. Real query correctness (ordering, aggregation) is a
database behaviour, not unit-testable without a live database -- see
tests/test_customer_service.py's docstring for why that's a deliberate
integration-test-only concern, not replicated here for this much
smaller module.
"""

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import db  # noqa: E402
from services import revenue_service  # noqa: E402


def test_get_monthly_sales_metrics_wraps_database_error(monkeypatch):
    def _raise(*args, **kwargs):
        raise db.DatabaseError("connection lost")

    monkeypatch.setattr(db, "execute_query", _raise)

    with pytest.raises(revenue_service.RevenueServiceError):
        revenue_service.get_monthly_sales_metrics()


def test_get_monthly_sales_metrics_returns_dataframe(monkeypatch):
    monkeypatch.setattr(
        db,
        "execute_query",
        lambda sql, params=(): (
            ["sales_month", "total_orders", "net_revenue"],
            [("2018-01-01", 100, 1234.56)],
        ),
    )

    result = revenue_service.get_monthly_sales_metrics()

    assert list(result.columns) == ["sales_month", "total_orders", "net_revenue"]
    assert len(result) == 1
