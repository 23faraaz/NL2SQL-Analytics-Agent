import pandas as pd

from etl.config import ORDER_STATUS_MAP, SOURCE_COUNTRY, SOURCE_SALES_CHANNEL

ORDER_OUTPUT_COLUMNS = [
    "order_id",
    "source_order_id",
    "customer_id",
    "order_number",
    "order_date",
    "status",
    "sales_channel",
    "shipping_city",
    "shipping_region",
    "shipping_postcode",
    "shipping_country",
]

ORDER_FINANCIAL_COLUMNS = [
    "order_id",
    "source_order_id",
    "customer_id",
    "order_number",
    "order_date",
    "status",
    "sales_channel",
    "shipping_city",
    "shipping_region",
    "shipping_postcode",
    "shipping_country",
    "subtotal",
    "shipping_cost",
    "total_amount",
]


def transform_orders(
    orders: pd.DataFrame,
    customers: pd.DataFrame,
) -> pd.DataFrame:
    """
    Transform orders and map them to processed customer IDs.

    This is the real/derived subset of the commerce.orders contract, prior
    to attaching financial totals (see finalize_order_totals, which needs
    order_items to exist first). order_date, status (crosswalked via
    ORDER_STATUS_MAP), and shipping geography (copied from the linked
    customer's real Olist city/region/postcode) are REAL/DERIVED.
    sales_channel is set to MARKETPLACE for every row -- not a per-row
    guess, but a real, documented fact about Olist's own business model
    as an online marketplace. order_number is DERIVED from the real
    source order ID. discount_code_id and campaign_id are left unset
    (nullable; no Future-phase data exists yet).
    """

    required_order_columns = {
        "order_id",
        "customer_id",
        "order_status",
        "order_purchase_timestamp",
    }

    missing_order_columns = required_order_columns - set(orders.columns)

    if missing_order_columns:
        raise ValueError(
            "Orders dataset is missing required columns: "
            f"{sorted(missing_order_columns)}"
        )

    required_customer_columns = {
        "customer_id",
        "source_customer_id",
        "city",
        "region",
        "postcode",
        "country",
    }

    missing_customer_columns = required_customer_columns - set(customers.columns)

    if missing_customer_columns:
        raise ValueError(
            "Processed customers are missing required columns: "
            f"{sorted(missing_customer_columns)}"
        )

    transformed = orders.rename(
        columns={
            "order_id": "source_order_id",
            "customer_id": "source_customer_id",
            "order_purchase_timestamp": "order_date",
        }
    ).copy()

    transformed["order_date"] = pd.to_datetime(
        transformed["order_date"],
        errors="coerce",
    )

    unmapped_status = set(transformed["order_status"].unique()) - set(ORDER_STATUS_MAP)

    if unmapped_status:
        raise ValueError(
            "Orders dataset contains order_status values with no "
            f"commerce.orders.status mapping: {sorted(unmapped_status)}"
        )

    transformed["status"] = transformed["order_status"].map(ORDER_STATUS_MAP)

    transformed["sales_channel"] = SOURCE_SALES_CHANNEL

    customer_lookup = customers[
        [
            "customer_id",
            "source_customer_id",
            "city",
            "region",
            "postcode",
        ]
    ].rename(
        columns={
            "city": "shipping_city",
            "region": "shipping_region",
            "postcode": "shipping_postcode",
        }
    )

    transformed = transformed.merge(
        customer_lookup,
        how="left",
        on="source_customer_id",
        validate="many_to_one",
    )

    missing_customer_matches = int(transformed["customer_id"].isna().sum())

    if missing_customer_matches:
        raise ValueError(
            f"{missing_customer_matches:,} orders could not be "
            "matched to processed customers"
        )

    transformed["customer_id"] = transformed["customer_id"].astype(int)

    transformed["shipping_country"] = SOURCE_COUNTRY

    transformed.insert(
        0,
        "order_id",
        range(1, len(transformed) + 1),
    )

    if transformed["source_order_id"].duplicated().any():
        raise ValueError("Duplicate source order IDs were found")

    transformed["order_number"] = "ORD-" + transformed["source_order_id"].astype(str)

    return transformed[ORDER_OUTPUT_COLUMNS]


def finalize_order_totals(
    orders: pd.DataFrame,
    order_items: pd.DataFrame,
) -> pd.DataFrame:
    """
    Attach REAL/DERIVED financial totals to orders once order_items has
    been transformed.

    subtotal is the sum of real item-level revenue; shipping_cost is the
    sum of real per-item freight (order_items has no freight column of
    its own in the commerce schema, so it rolls up to the order level
    instead); total_amount is their sum. discount_amount and tax_amount
    are left unset (schema default 0 -- Olist has neither concept).
    """

    required_order_columns = {"order_id"}
    missing_order_columns = required_order_columns - set(orders.columns)

    if missing_order_columns:
        raise ValueError(
            "Orders dataset is missing required columns: "
            f"{sorted(missing_order_columns)}"
        )

    required_item_columns = {"order_id", "line_revenue", "freight_value_gbp"}
    missing_item_columns = required_item_columns - set(order_items.columns)

    if missing_item_columns:
        raise ValueError(
            "Order items dataset is missing required columns: "
            f"{sorted(missing_item_columns)}"
        )

    order_totals = (
        order_items.groupby("order_id")
        .agg(
            subtotal=("line_revenue", "sum"),
            shipping_cost=("freight_value_gbp", "sum"),
        )
        .reset_index()
    )

    transformed = orders.merge(
        order_totals,
        how="left",
        on="order_id",
        validate="one_to_one",
    )

    transformed["subtotal"] = transformed["subtotal"].fillna(0).round(2)
    transformed["shipping_cost"] = transformed["shipping_cost"].fillna(0).round(2)
    transformed["total_amount"] = (
        transformed["subtotal"] + transformed["shipping_cost"]
    ).round(2)

    return transformed[ORDER_FINANCIAL_COLUMNS]
