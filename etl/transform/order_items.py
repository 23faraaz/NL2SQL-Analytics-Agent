import pandas as pd

from etl.config import BRL_TO_GBP_RATE


ORDER_ITEM_OUTPUT_COLUMNS = [
    "order_item_key",
    "order_id",
    "product_id",
    "line_number",
    "unit_price_gbp",
    "freight_value_gbp",
    "shipping_deadline",
    "seller_id",
]


def transform_order_items(
    order_items: pd.DataFrame,
    orders: pd.DataFrame,
    products: pd.DataFrame,
) -> pd.DataFrame:
    """Transform order items and map order and product relationships."""

    required_item_columns = {
        "order_id",
        "order_item_id",
        "product_id",
        "seller_id",
        "shipping_limit_date",
        "price",
        "freight_value",
    }

    missing_item_columns = (
        required_item_columns - set(order_items.columns)
    )

    if missing_item_columns:
        raise ValueError(
            "Order-items dataset is missing required columns: "
            f"{sorted(missing_item_columns)}"
        )

    transformed = order_items.rename(
        columns={
            "order_id": "source_order_id",
            "product_id": "source_product_id",
            "order_item_id": "line_number",
            "shipping_limit_date": "shipping_deadline",
        }
    ).copy()

    transformed["shipping_deadline"] = pd.to_datetime(
        transformed["shipping_deadline"],
        errors="coerce",
    )

    order_lookup = orders[
        [
            "order_id",
            "source_order_id",
        ]
    ].copy()

    product_lookup = products[
        [
            "product_id",
            "source_product_id",
        ]
    ].copy()

    transformed = transformed.merge(
        order_lookup,
        how="left",
        on="source_order_id",
        validate="many_to_one",
    )

    transformed = transformed.merge(
        product_lookup,
        how="left",
        on="source_product_id",
        validate="many_to_one",
    )

    missing_orders = int(
        transformed["order_id"].isna().sum()
    )

    if missing_orders:
        raise ValueError(
            f"{missing_orders:,} order items could not be matched "
            "to processed orders"
        )

    missing_products = int(
        transformed["product_id"].isna().sum()
    )

    if missing_products:
        raise ValueError(
            f"{missing_products:,} order items could not be matched "
            "to processed products"
        )

    transformed["order_id"] = (
        transformed["order_id"].astype(int)
    )

    transformed["product_id"] = (
        transformed["product_id"].astype(int)
    )

    transformed["unit_price_gbp"] = (
        transformed["price"] * BRL_TO_GBP_RATE
    ).round(2)

    transformed["freight_value_gbp"] = (
        transformed["freight_value"] * BRL_TO_GBP_RATE
    ).round(2)

    if (transformed["unit_price_gbp"] < 0).any():
        raise ValueError(
            "Negative order-item prices were found"
        )

    if (transformed["freight_value_gbp"] < 0).any():
        raise ValueError(
            "Negative freight values were found"
        )

    transformed.insert(
        0,
        "order_item_key",
        range(1, len(transformed) + 1),
    )

    return transformed[ORDER_ITEM_OUTPUT_COLUMNS]