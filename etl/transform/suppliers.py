import pandas as pd


SUPPLIER_OUTPUT_COLUMNS = [
    "supplier_id",
    "source_supplier_id",
    "source_postcode_prefix",
    "source_city",
    "source_state",
]


def transform_suppliers(
    suppliers: pd.DataFrame,
) -> pd.DataFrame:
    """
    Transform the Olist sellers dataset into the suppliers dimension.
    """

    required_columns = {
        "seller_id",
        "seller_zip_code_prefix",
        "seller_city",
        "seller_state",
    }

    missing_columns = required_columns - set(suppliers.columns)

    if missing_columns:
        raise ValueError(
            "Suppliers dataset is missing required columns: "
            f"{sorted(missing_columns)}"
        )

    transformed = suppliers.rename(
        columns={
            "seller_id": "source_supplier_id",
            "seller_zip_code_prefix": "source_postcode_prefix",
            "seller_city": "source_city",
            "seller_state": "source_state",
        }
    ).copy()

    duplicate_count = int(
        transformed["source_supplier_id"].duplicated().sum()
    )

    if duplicate_count:
        raise ValueError(
            "Suppliers dataset contains "
            f"{duplicate_count:,} duplicate supplier identifiers"
        )

    transformed.insert(
        0,
        "supplier_id",
        range(1, len(transformed) + 1),
    )

    transformed["source_city"] = (
        transformed["source_city"]
        .fillna("Unknown")
        .astype(str)
        .str.strip()
    )

    transformed["source_state"] = (
        transformed["source_state"]
        .fillna("Unknown")
        .astype(str)
        .str.strip()
        .str.upper()
    )

    return transformed[SUPPLIER_OUTPUT_COLUMNS]