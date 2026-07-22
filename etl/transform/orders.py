import pandas as pd


ORDER_OUTPUT_COLUMNS = [
    "order_id",
    "source_order_id",
    "customer_id",
    "status",
    "ordered_at",
    "approved_at",
    "shipped_at",
    "delivered_at",
    "estimated_delivery_at",
]


def transform_orders(
    orders: pd.DataFrame,
    customers: pd.DataFrame,
) -> pd.DataFrame:
    """Transform orders and map them to processed customer IDs."""

    required_order_columns = {
        "order_id",
        "customer_id",
        "order_status",
        "order_purchase_timestamp",
        "order_approved_at",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    }

    missing_order_columns = (
        required_order_columns - set(orders.columns)
    )

    if missing_order_columns:
        raise ValueError(
            "Orders dataset is missing required columns: "
            f"{sorted(missing_order_columns)}"
        )

    required_customer_columns = {
        "customer_id",
        "source_customer_id",
    }

    missing_customer_columns = (
        required_customer_columns - set(customers.columns)
    )

    if missing_customer_columns:
        raise ValueError(
            "Processed customers are missing required columns: "
            f"{sorted(missing_customer_columns)}"
        )

    transformed = orders.rename(
        columns={
            "order_id": "source_order_id",
            "customer_id": "source_customer_id",
            "order_status": "status",
            "order_purchase_timestamp": "ordered_at",
            "order_approved_at": "approved_at",
            "order_delivered_carrier_date": "shipped_at",
            "order_delivered_customer_date": "delivered_at",
            "order_estimated_delivery_date": "estimated_delivery_at",
        }
    ).copy()

    datetime_columns = [
        "ordered_at",
        "approved_at",
        "shipped_at",
        "delivered_at",
        "estimated_delivery_at",
    ]

    for column in datetime_columns:
        transformed[column] = pd.to_datetime(
            transformed[column],
            errors="coerce",
        )

    customer_lookup = customers[
        [
            "customer_id",
            "source_customer_id",
        ]
    ].copy()

    transformed = transformed.merge(
        customer_lookup,
        how="left",
        on="source_customer_id",
        validate="many_to_one",
    )

    missing_customer_matches = int(
        transformed["customer_id"].isna().sum()
    )

    if missing_customer_matches:
        raise ValueError(
            f"{missing_customer_matches:,} orders could not be "
            "matched to processed customers"
        )

    transformed["customer_id"] = (
        transformed["customer_id"].astype(int)
    )

    transformed.insert(
        0,
        "order_id",
        range(1, len(transformed) + 1),
    )

    if transformed["source_order_id"].duplicated().any():
        raise ValueError(
            "Duplicate source order IDs were found"
        )

    return transformed[ORDER_OUTPUT_COLUMNS]