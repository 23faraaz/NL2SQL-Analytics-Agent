import pandas as pd

from etl.config import SOURCE_COUNTRY

CUSTOMER_OUTPUT_COLUMNS = [
    "customer_id",
    "source_customer_id",
    "city",
    "region",
    "postcode",
    "country",
]


def transform_customers(
    customers: pd.DataFrame,
) -> pd.DataFrame:
    """
    Transform raw Olist customers into the real/derived subset of the
    commerce.customers contract.

    Only fields Olist genuinely provides are populated here:
      - city, region (Olist's real state code), postcode (postcode prefix)
        -- REAL
      - country -- DERIVED but real: the Olist dataset is real Brazilian
        marketplace data, so country is set to Brazil rather than
        overwritten to fit a UK-retailer narrative the source data does
        not represent.

    Customer identity fields required by commerce.customers (first_name,
    last_name, email, phone, acquisition_channel) do not exist in Olist
    at all -- Olist customers are anonymised. Those fields are added by
    the separate S4b synthetic augmentation step, not here. source_customer_id
    is retained only as an internal join key for downstream transforms
    (orders) and is dropped before the final processed CSV is written.
    """

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
            "customer_city": "city",
            "customer_state": "region",
            "customer_zip_code_prefix": "postcode",
        }
    ).copy()

    transformed["country"] = SOURCE_COUNTRY

    transformed.insert(
        0,
        "customer_id",
        range(1, len(transformed) + 1),
    )

    if transformed["source_customer_id"].duplicated().any():
        raise ValueError("Duplicate source customer IDs were found")

    return transformed[CUSTOMER_OUTPUT_COLUMNS]
