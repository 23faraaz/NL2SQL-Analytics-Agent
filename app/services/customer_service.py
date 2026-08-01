"""
Customer Analytics MVP.

Deterministic, service-layer SQL against the canonical commerce schema's
existing analytics views -- never routed through Gemini. Free-form
questions continue to use the NL2SQL pipeline (app/llm.py) unchanged;
this module exists specifically so the fixed dashboard questions (top
customers, order history, value-tier breakdown) get predictable,
auditable answers instead of LLM-generated SQL.

Reuses commerce.customer_lifetime_metrics for lifetime value and tier
(including its existing customer_value_tier definition -- see the
module-level TIER_DISPLAY_ORDER docstring below for the methodology
rationale) and commerce.order_financials for order-level detail, rather
than recomputing either from base tables.
"""

from __future__ import annotations

import logging

import pandas as pd

import db


logger = logging.getLogger(__name__)


class CustomerServiceError(Exception):
    """
    Raised for invalid input or an unrecoverable data problem in the
    Customer Analytics MVP. Never a raw database exception -- callers
    (the UI) can display this message directly.
    """


MAX_TOP_N_LIMIT = 100

# Fixed, documented display order matching the business hierarchy already
# defined in commerce.customer_lifetime_metrics.customer_value_tier
# (sql/002_views.sql). Not alphabetical, so results read VIP-first rather
# than in an arbitrary SQL GROUP BY order.
TIER_DISPLAY_ORDER = [
    "VIP",
    "HIGH_VALUE",
    "REGULAR",
    "LOW_VALUE",
    "NO_PURCHASE",
]


def _validate_limit(limit: int) -> int:
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise CustomerServiceError(
            f"limit must be an integer, got {type(limit).__name__}"
        )

    if limit < 1:
        raise CustomerServiceError(
            f"limit must be at least 1, got {limit}"
        )

    if limit > MAX_TOP_N_LIMIT:
        raise CustomerServiceError(
            f"limit cannot exceed {MAX_TOP_N_LIMIT}, got {limit}"
        )

    return limit


def _validate_customer_id(customer_id: int) -> int:
    if isinstance(customer_id, bool) or not isinstance(customer_id, int):
        raise CustomerServiceError(
            "customer_id must be an integer, got "
            f"{type(customer_id).__name__}"
        )

    if customer_id < 1:
        raise CustomerServiceError(
            f"customer_id must be a positive integer, got {customer_id}"
        )

    return customer_id


def _run_query(
    sql: str,
    params: tuple = (),
) -> pd.DataFrame:
    """
    Execute trusted, parameterized, developer-written SQL and return a
    DataFrame. Wraps db.DatabaseError so no raw database exception
    reaches the UI.
    """

    try:
        columns, rows = db.execute_query(sql, params)
    except db.DatabaseError as exc:
        logger.error("Customer analytics query failed: %s", exc)
        raise CustomerServiceError(
            "Customer analytics data could not be retrieved."
        ) from exc

    return pd.DataFrame(rows, columns=columns)


def get_top_customers_by_lifetime_value(
    limit: int = 10,
) -> pd.DataFrame:
    """
    Top-N customers by net lifetime revenue.

    Uses commerce.customer_lifetime_metrics directly; net_lifetime_revenue
    and customer_value_tier are not recomputed here.
    """

    limit = _validate_limit(limit)

    sql = """
        SELECT
            customer_id,
            customer_name,
            city,
            region,
            country,
            total_orders,
            net_lifetime_revenue,
            average_order_value,
            customer_value_tier,
            customer_activity_status,
            last_order_date
        FROM commerce.customer_lifetime_metrics
        WHERE total_orders > 0
        ORDER BY net_lifetime_revenue DESC, customer_id ASC
        LIMIT %s;
    """

    return _run_query(sql, (limit,))


def get_customer_order_history(
    customer_id: int,
) -> pd.DataFrame:
    """
    A single customer's order history, most recent first.

    Uses commerce.order_financials directly, filtered to the requested
    customer. Raises CustomerServiceError if no such customer exists at
    all (distinct from a real customer who simply has no orders yet,
    which returns an empty DataFrame, not an error).
    """

    customer_id = _validate_customer_id(customer_id)

    exists_sql = """
        SELECT 1
        FROM commerce.customer_lifetime_metrics
        WHERE customer_id = %s;
    """

    exists_result = _run_query(exists_sql, (customer_id,))

    if exists_result.empty:
        raise CustomerServiceError(
            f"No customer found with customer_id={customer_id}."
        )

    history_sql = """
        SELECT
            order_id,
            order_number,
            order_date,
            status,
            sales_channel,
            total_units,
            gross_item_revenue,
            shipping_cost,
            net_revenue_after_refunds,
            estimated_profit_after_refunds
        FROM commerce.order_financials
        WHERE customer_id = %s
        ORDER BY order_date DESC, order_id DESC;
    """

    return _run_query(history_sql, (customer_id,))


def get_customer_value_tier_breakdown() -> pd.DataFrame:
    """
    Customer count, and total/average lifetime revenue, per value tier.

    Reuses commerce.customer_lifetime_metrics.customer_value_tier as the
    single source of truth for tier assignment (see this module's
    docstring for why a parallel percentile-based tier was not added
    instead). Every customer appears in exactly one tier, including
    customers with zero orders (NO_PURCHASE) -- unlike
    get_top_customers_by_lifetime_value, this is not filtered to
    total_orders > 0, so tier counts sum to the full customer count.
    """

    sql = """
        SELECT
            customer_value_tier,
            COUNT(*) AS customer_count,
            SUM(net_lifetime_revenue) AS total_lifetime_revenue,
            ROUND(AVG(net_lifetime_revenue), 2) AS average_lifetime_revenue
        FROM commerce.customer_lifetime_metrics
        GROUP BY customer_value_tier;
    """

    breakdown = _run_query(sql, ())

    if breakdown.empty:
        return breakdown

    tier_order = {tier: index for index, tier in enumerate(TIER_DISPLAY_ORDER)}

    breakdown["_sort_order"] = breakdown["customer_value_tier"].map(
        lambda tier: tier_order.get(tier, len(TIER_DISPLAY_ORDER))
    )

    breakdown = (
        breakdown.sort_values("_sort_order")
        .drop(columns="_sort_order")
        .reset_index(drop=True)
    )

    return breakdown
