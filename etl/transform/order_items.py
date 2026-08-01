import pandas as pd

from etl.config import BRL_TO_GBP_RATE


ORDER_ITEM_OUTPUT_COLUMNS = [
    "order_item_id",
    "order_id",
    "product_id",
    "quantity",
    "unit_sale_price",
    "line_revenue",
    "freight_value_gbp",
]


def transform_order_items(
    order_items: pd.DataFrame,
    orders: pd.DataFrame,
    products: pd.DataFrame,
) -> pd.DataFrame:
    """
    Transform Olist order items into the real/derived subset of the
    commerce.order_items contract.

    unit_sale_price and line_revenue are REAL/DERIVED (existing
    BRL_TO_GBP_RATE conversion, retained). Real Olist order items have no
    explicit item-level quantity column -- each row is one unit, so
    quantity is DERIVED as 1 per row (rows sharing the same order/product
    are not pre-aggregated by Olist). freight_value_gbp is carried through
    only so orders.finalize_order_totals can roll it up to the order
    level; commerce.order_items has no freight column of its own.

    commerce.order_items.variant_id is NOT NULL and references
    product_variants, which only exists after the separate S4b synthetic
    augmentation step generates them. This function therefore returns
    product_id (not variant_id) -- S4b resolves product_id -> variant_id,
    and adds unit_cost_at_sale, line_cost, and line_profit once variant
    costs exist. The resulting rows cannot be loaded into commerce until
    that step has run.
    """

    required_order_columns = {"order_id", "source_order_id"}
    missing_order_columns = required_order_columns - set(orders.columns)

    if missing_order_columns:
        raise ValueError(
            "Orders dataframe is missing columns: "
            f"{sorted(missing_order_columns)}. "
            f"Available columns: {orders.columns.tolist()}"
        )

    required_product_columns = {"product_id", "source_product_id"}
    missing_product_columns = required_product_columns - set(products.columns)

    if missing_product_columns:
        raise ValueError(
            "Products dataframe is missing columns: "
            f"{sorted(missing_product_columns)}"
        )

    required_item_columns = {
        "order_id",
        "order_item_id",
        "product_id",
        "price",
        "freight_value",
    }

    missing_item_columns = required_item_columns - set(order_items.columns)

    if missing_item_columns:
        raise ValueError(
            "Order items dataset is missing required columns: "
            f"{sorted(missing_item_columns)}"
        )

    transformed = order_items.rename(
        columns={
            "order_id": "source_order_id",
            "product_id": "source_product_id",
            # Olist's line-number column has no equivalent in
            # commerce.order_items and would otherwise collide with the
            # synthetic order_item_id primary key inserted below.
            "order_item_id": "source_line_number",
        }
    ).copy()

    order_lookup = orders[
        [
            "order_id",
            "source_order_id",
        ]
    ]

    product_lookup = products[
        [
            "product_id",
            "source_product_id",
        ]
    ]

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

    if transformed["order_id"].isna().any():
        raise ValueError(
            "Some order items could not be matched to orders."
        )

    if transformed["product_id"].isna().any():
        raise ValueError(
            "Some order items could not be matched to products."
        )

    transformed["order_id"] = transformed["order_id"].astype(int)
    transformed["product_id"] = transformed["product_id"].astype(int)

    # Olist represents each unit sold as its own row rather than a
    # quantity column, so quantity is 1 for every real order item.
    transformed["quantity"] = 1

    transformed["unit_sale_price"] = (
        pd.to_numeric(
            transformed["price"],
            errors="coerce",
        )
        * BRL_TO_GBP_RATE
    ).round(2)

    transformed["line_revenue"] = (
        transformed["quantity"] * transformed["unit_sale_price"]
    ).round(2)

    transformed["freight_value_gbp"] = (
        pd.to_numeric(
            transformed["freight_value"],
            errors="coerce",
        )
        * BRL_TO_GBP_RATE
    ).round(2)

    transformed.insert(
        0,
        "order_item_id",
        range(1, len(transformed) + 1),
    )

    return transformed[ORDER_ITEM_OUTPUT_COLUMNS]
