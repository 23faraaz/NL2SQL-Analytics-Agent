import pandas as pd

from etl.config import BRL_TO_GBP_RATE, PAYMENT_METHOD_MAP


PAYMENT_OUTPUT_COLUMNS = [
    "payment_id",
    "order_id",
    "payment_reference",
    "payment_method",
    "payment_status",
    "amount",
    "payment_date",
]


def transform_payments(
    payments: pd.DataFrame,
    orders: pd.DataFrame,
) -> pd.DataFrame:
    """
    Transform payments and map them to processed order IDs.

    amount is REAL/DERIVED (existing BRL_TO_GBP_RATE conversion, retained).
    payment_method is DERIVED via a real semantic crosswalk from Olist's
    payment_type (PAYMENT_METHOD_MAP). Real Olist payments have no status,
    reference, or date field at all:
      - payment_status is DERIVED from the linked order's real status
        (SUCCESSFUL unless the order is CANCELLED).
      - payment_reference is DERIVED, built deterministically from the
        real source order ID and payment sequence (a genuine natural key
        in Olist), not fabricated.
      - payment_date is DERIVED from the linked order's real order_date,
        since Olist payments carry no date of their own.
    """

    required_payment_columns = {
        "order_id",
        "payment_sequential",
        "payment_type",
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
        "order_date",
        "status",
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
        }
    ).copy()

    unmapped_methods = (
        set(transformed["payment_type"].unique())
        - set(PAYMENT_METHOD_MAP)
    )

    if unmapped_methods:
        raise ValueError(
            "Payments dataset contains payment_type values with no "
            f"commerce.payments.payment_method mapping: "
            f"{sorted(unmapped_methods)}"
        )

    transformed["payment_method"] = transformed["payment_type"].map(
        PAYMENT_METHOD_MAP
    )

    order_lookup = orders[
        [
            "order_id",
            "source_order_id",
            "order_date",
            "status",
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

    transformed["payment_status"] = transformed["status"].apply(
        lambda status: "SUCCESSFUL" if status != "CANCELLED" else "FAILED"
    )

    transformed["payment_date"] = transformed["order_date"]

    transformed["payment_reference"] = (
        transformed["source_order_id"].astype(str)
        + "-"
        + transformed["payment_sequential"].astype(str)
    )

    if transformed["payment_reference"].duplicated().any():
        raise ValueError(
            "Derived payment references are not unique"
        )

    transformed["amount"] = (
        pd.to_numeric(
            transformed["payment_value"],
            errors="coerce",
        )
        * BRL_TO_GBP_RATE
    ).round(2)

    if transformed["amount"].isna().any():
        raise ValueError(
            "Payments contain invalid payment values"
        )

    if (transformed["amount"] < 0).any():
        raise ValueError(
            "Payments contain negative payment values"
        )

    transformed.insert(
        0,
        "payment_id",
        range(1, len(transformed) + 1),
    )

    return transformed[PAYMENT_OUTPUT_COLUMNS]
