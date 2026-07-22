import pandas as pd


CUSTOMER_OUTPUT_COLUMNS = [
    "customer_id",
    "source_customer_id",
    "source_customer_unique_id",
    "source_postcode_prefix",
    "source_city",
    "source_state",
]


def transform_customers(
    customers: pd.DataFrame,
) -> pd.DataFrame:
    """Transform raw Olist customers into the processed schema."""

    required_columns = {
        "customer_id",
        "customer_unique_id",
        "customer_zip_code_prefix",
        "customer_city",
        "customer_state",
    }

    missing_columns = required_columns - set(customers.columns)

    if missing_columns:
        raise ValueError(
            "Customers dataset is missing required columns: "
            f"{sorted(missing_columns)}"
        )

    transformed = customers.rename(
        columns={
            "customer_id": "source_customer_id",
            "customer_unique_id": "source_customer_unique_id",
            "customer_zip_code_prefix": "source_postcode_prefix",
            "customer_city": "source_city",
            "customer_state": "source_state",
        }
    ).copy()

    transformed.insert(
        0,
        "customer_id",
        range(1, len(transformed) + 1),
    )

    if transformed["source_customer_id"].duplicated().any():
        raise ValueError(
            "Duplicate source customer IDs were found"
        )

    return transformed[CUSTOMER_OUTPUT_COLUMNS]