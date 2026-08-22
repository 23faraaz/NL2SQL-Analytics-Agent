"""
Tests for app/services/product_service.py.

Validation-logic tests (limit checks) run unconditionally, mirroring
customer_service.py's pattern. Real query correctness (aggregation,
GROUP BY rollups) is a database behaviour, not unit-testable without a
live database -- see tests/test_customer_service.py's docstring for why
that's a deliberate integration-test-only concern, not replicated here
for this much smaller module.
"""

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import db  # noqa: E402
from services import product_service  # noqa: E402


@pytest.mark.parametrize("limit", [0, -1, -100])
def test_validate_limit_rejects_non_positive(limit):
    with pytest.raises(product_service.ProductServiceError):
        product_service._validate_limit(limit)


def test_validate_limit_rejects_exceeding_max():
    with pytest.raises(product_service.ProductServiceError):
        product_service._validate_limit(product_service.MAX_TOP_N_LIMIT + 1)


@pytest.mark.parametrize("limit", [10.5, None, "10", True])
def test_validate_limit_rejects_wrong_type(limit):
    with pytest.raises(product_service.ProductServiceError):
        product_service._validate_limit(limit)


def test_validate_limit_accepts_valid_value():
    assert product_service._validate_limit(10) == 10
    assert product_service._validate_limit(product_service.MAX_TOP_N_LIMIT) == (
        product_service.MAX_TOP_N_LIMIT
    )


def test_get_top_products_by_revenue_wraps_database_error(monkeypatch):
    def _raise(*args, **kwargs):
        raise db.DatabaseError("connection lost")

    monkeypatch.setattr(db, "execute_query", _raise)

    with pytest.raises(product_service.ProductServiceError):
        product_service.get_top_products_by_revenue(limit=10)


def test_get_top_products_by_revenue_passes_limit_as_parameter(monkeypatch):
    seen = {}

    def _fake_execute(sql, params=()):
        seen["sql"] = sql
        seen["params"] = params
        return (["product_id", "net_revenue"], [(1, 100.0)])

    monkeypatch.setattr(db, "execute_query", _fake_execute)

    product_service.get_top_products_by_revenue(limit=5)

    assert seen["params"] == (5,)
    assert "GROUP BY" in seen["sql"]


def test_get_revenue_by_category_wraps_database_error(monkeypatch):
    def _raise(*args, **kwargs):
        raise db.DatabaseError("connection lost")

    monkeypatch.setattr(db, "execute_query", _raise)

    with pytest.raises(product_service.ProductServiceError):
        product_service.get_revenue_by_category()


def test_get_revenue_by_category_returns_dataframe(monkeypatch):
    monkeypatch.setattr(
        db,
        "execute_query",
        lambda sql, params=(): (
            ["category_name", "net_revenue"],
            [("Electronics", 5000.0)],
        ),
    )

    result = product_service.get_revenue_by_category()

    assert list(result.columns) == ["category_name", "net_revenue"]
    assert len(result) == 1
