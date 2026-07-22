import pandas as pd

from etl.config import BRL_TO_GBP_RATE


ORDER_ITEM_OUTPUT_COLUMNS = [
    "order_item_key",
    "order_id",
    "product_id",
    "supplier_id",
    "line_number",
    "unit_price_gbp",
    "freight_value_gbp",
    "shipping_deadline",
]


def transform_order_items(
    order_items: pd.DataFrame,
    orders: pd.DataFrame,
    products: pd.DataFrame,
    suppliers: pd.DataFrame,
) -> pd.DataFrame:
    """
    Transform Olist order items into the warehouse fact table.
    """

    required_order_item_columns = {
        "order_id",
        "order_item_id",
        "product_id",
        "seller_id",
        "shipping_limit_date",
        "price",
        "freight_value",
    }

    missing_columns = (
        required_order_item_columns
        - set(order_items.columns)
    )

    if missing_columns:
        raise ValueError(
            "Order items dataset is missing required columns: "
            f"{sorted(missing_columns)}"
        )

    transformed = order_items.rename(
        columns={
            "order_id": "source_order_id",
            "product_id": "source_product_id",
            "seller_id": "source_supplier_id",
            "order_item_id": "line_number",
            "shipping_limit_date": "shipping_deadline",
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

    supplier_lookup = suppliers[
        [
            "supplier_id",
            "source_supplier_id",
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

    transformed = transformed.merge(
        supplier_lookup,
        how="left",
        on="source_supplier_id",
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

    if transformed["supplier_id"].isna().any():
        raise ValueError(
            "Some order items could not be matched to suppliers."
        )

    transformed["order_id"] = (
        transformed["order_id"]
        .astype(int)
    )

    transformed["product_id"] = (
        transformed["product_id"]
        .astype(int)
    )

    transformed["supplier_id"] = (
        transformed["supplier_id"]
        .astype(int)
    )

    transformed["line_number"] = (
        pd.to_numeric(
            transformed["line_number"],
            errors="raise",
        )
        .astype(int)
    )

    transformed["unit_price_gbp"] = (
        pd.to_numeric(
            transformed["price"],
            errors="coerce",
        )
        * BRL_TO_GBP_RATE
    ).round(2)

    transformed["freight_value_gbp"] = (
        pd.to_numeric(
            transformed["freight_value"],
            errors="coerce",
        )
        * BRL_TO_GBP_RATE
    ).round(2)

    transformed["shipping_deadline"] = pd.to_datetime(
        transformed["shipping_deadline"],
        errors="coerce",
    )

    transformed.insert(
        0,
        "order_item_key",
        range(
            1,
            len(transformed) + 1,
        ),
    )

    return transformed[
        ORDER_ITEM_OUTPUT_COLUMNS
    ]