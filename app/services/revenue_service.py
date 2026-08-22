"""
Revenue Analytics.

Deterministic, service-layer SQL against commerce.monthly_sales_metrics
-- never routed through the LLM, same pattern as customer_service.py.
No user-supplied parameters here (the whole view is returned), so there
is nothing to validate before it reaches SQL.
"""

from __future__ import annotations

import logging

import pandas as pd

import db


logger = logging.getLogger(__name__)


class RevenueServiceError(Exception):
    """
    Raised for an unrecoverable data problem in Revenue Analytics. Never
    a raw database exception -- callers (the UI) can display this
    message directly.
    """


def _run_query(
    sql: str,
    params: tuple = (),
) -> pd.DataFrame:
    try:
        columns, rows = db.execute_query(sql, params)
    except db.DatabaseError as exc:
        logger.error("Revenue analytics query failed: %s", exc)
        raise RevenueServiceError(
            "Revenue analytics data could not be retrieved."
        ) from exc

    return pd.DataFrame(rows, columns=columns)


def get_monthly_sales_metrics() -> pd.DataFrame:
    """
    Every month present in commerce.monthly_sales_metrics, oldest first.

    Reuses the view directly -- total_orders, gross_revenue, net_revenue,
    average_order_value etc. are not recomputed here.
    """

    sql = """
        SELECT
            sales_month,
            total_orders,
            unique_customers,
            total_units_sold,
            gross_revenue,
            refund_amount,
            net_revenue,
            estimated_profit,
            average_order_value,
            estimated_profit_margin_percentage
        FROM commerce.monthly_sales_metrics
        ORDER BY sales_month ASC;
    """

    return _run_query(sql)
