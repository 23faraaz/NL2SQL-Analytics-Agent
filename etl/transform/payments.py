import pandas as pd

from etl.config import BRL_TO_GBP_RATE


PAYMENT_OUTPUT_COLUMNS = [
    "payment_id",
    "order_id",
    "payment_sequence",
    "payment_type",
    "payment_installments",
    "payment_value_gbp",
]


def transform_payments(
    payments: pd.DataFrame,
    orders: pd.DataFrame,
) -> pd.DataFrame:
    """Transform payments and map them to processed order IDs."""

    required_payment_columns = {
        "order_id",
        "payment_sequential",
        "payment_type",
        "payment_installments",
        "payment_value",
    }

    missing_payment_columns = (
        required_payment_columns - set(payments.columns)
    )

    if missing_payment_columns:
        raise ValueError(
            "Payments dataset is missing required columns: "
            f"{sorted(missing_payment_columns)}"
        )

    required_order_columns = {
        "order_id",
        "source_order_id",
    }

    missing_order_columns = (
        required_order_columns - set(orders.columns)
    )

    if missing_order_columns:
        raise ValueError(
            "Processed orders are missing required columns: "
            f"{sorted(missing_order_columns)}"
        )

    transformed = payments.rename(
        columns={
            "order_id": "source_order_id",
            "payment_sequential": "payment_sequence",
        }
    ).copy()

    order_lookup = orders[
        [
            "order_id",
            "source_order_id",
        ]
    ].copy()

    transformed = transformed.merge(
        order_lookup,
        how="left",
        on="source_order_id",
        validate="many_to_one",
    )

    missing_orders = int(
        transformed["order_id"].isna().sum()
    )

    if missing_orders:
        raise ValueError(
            f"{missing_orders:,} payments could not be matched "
            "to processed orders"
        )

    transformed["order_id"] = (
        transformed["order_id"].astype(int)
    )

    transformed["payment_installments"] = pd.to_numeric(
        transformed["payment_installments"],
        errors="coerce",
    ).fillna(0).astype(int)

    transformed["payment_value_gbp"] = (
        pd.to_numeric(
            transformed["payment_value"],
            errors="coerce",
        )
        * BRL_TO_GBP_RATE
    ).round(2)

    if transformed["payment_value_gbp"].isna().any():
        raise ValueError(
            "Payments contain invalid payment values"
        )

    if (transformed["payment_value_gbp"] < 0).any():
        raise ValueError(
            "Payments contain negative payment values"
        )

    if (transformed["payment_installments"] < 0).any():
        raise ValueError(
            "Payments contain negative instalment counts"
        )

    transformed.insert(
        0,
        "payment_id",
        range(1, len(transformed) + 1),
    )

    return transformed[PAYMENT_OUTPUT_COLUMNS]