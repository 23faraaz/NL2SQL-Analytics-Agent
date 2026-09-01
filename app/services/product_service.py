"""
Product Analytics.

Deterministic, service-layer SQL against commerce.product_performance --
never routed through the LLM, same pattern as customer_service.py and
revenue_service.py.

commerce.product_performance is variant-level (one row per SKU); every
query here aggregates up to product or category level with GROUP BY
rather than returning raw variant rows, so multi-variant products are
not double-counted.
"""

from __future__ import annotations

import logging

import pandas as pd

import db

logger = logging.getLogger(__name__)

MAX_TOP_N_LIMIT = 100


class ProductServiceError(Exception):
    """
    Raised for invalid input or an unrecoverable data problem in Product
    Analytics. Never a raw database exception -- callers (the UI) can
    display this message directly.
    """


def _validate_limit(limit: int) -> int:
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise ProductServiceError(
            f"limit must be an integer, got {type(limit).__name__}"
        )

    if limit < 1:
        raise ProductServiceError(f"limit must be at least 1, got {limit}")

    if limit > MAX_TOP_N_LIMIT:
        raise ProductServiceError(f"limit cannot exceed {MAX_TOP_N_LIMIT}, got {limit}")

    return limit


def _run_query(
    sql: str,
    params: tuple = (),
) -> pd.DataFrame:
    try:
        columns, rows = db.execute_query(sql, params)
    except db.DatabaseError as exc:
        logger.error("Product analytics query failed: %s", exc)
        raise ProductServiceError(
            "Product analytics data could not be retrieved."
        ) from exc

    return pd.DataFrame(rows, columns=columns)


def get_top_products_by_revenue(
    limit: int = 10,
) -> pd.DataFrame:
    """
    Top-N products (aggregated across all of a product's variants) by
    net revenue.
    """

    limit = _validate_limit(limit)

    sql = """
        SELECT
            product_id,
            product_name,
            brand,
            category_name,
            SUM(units_sold) AS units_sold,
            SUM(gross_revenue) AS gross_revenue,
            SUM(net_revenue) AS net_revenue,
            SUM(estimated_net_profit) AS estimated_net_profit
        FROM commerce.product_performance
        GROUP BY product_id, product_name, brand, category_name
        HAVING SUM(units_sold) > 0
        ORDER BY net_revenue DESC, product_id ASC
        LIMIT %s;
    """

    return _run_query(sql, (limit,))


def get_revenue_by_category() -> pd.DataFrame:
    """Net revenue and units sold, aggregated by product category."""

    sql = """
        SELECT
            category_name,
            SUM(units_sold) AS units_sold,
            SUM(net_revenue) AS net_revenue,
            SUM(estimated_net_profit) AS estimated_net_profit
        FROM commerce.product_performance
        GROUP BY category_name
        ORDER BY net_revenue DESC;
    """

    return _run_query(sql)
