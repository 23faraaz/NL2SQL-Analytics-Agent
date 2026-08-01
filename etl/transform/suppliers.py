import pandas as pd

from etl.config import SOURCE_COUNTRY


SUPPLIER_OUTPUT_COLUMNS = [
    "supplier_id",
    "supplier_name",
    "country",
]


def transform_suppliers(
    suppliers: pd.DataFrame,
) -> pd.DataFrame:
    """
    Transform the Olist sellers dataset into the commerce.suppliers
    contract.

    Olist sellers have no real business/company name -- supplier_name is
    DERIVED as a deterministic, traceable placeholder built from the real
    source seller identifier, not a fabricated company name. country is
    DERIVED but real (see transform_customers for the same rationale);
    Olist's granular seller_city/seller_state have no home in this table
    (commerce.suppliers has a single country column, no city/region split),
    so that real detail is not retained here.

    commerce.order_items has no supplier/seller reference at all -- Olist's
    real seller assignment is per order line item (transaction-level),
    while commerce.products.supplier_id is a single catalog-level
    relationship. Forcing a one-to-one product-to-supplier link from
    many-to-many real data would misrepresent it, so products.supplier_id
    is left NULL rather than guessed; supplier records exist in this
    table but are not linked elsewhere in this MVP.
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

    # DERIVED: a deterministic, traceable placeholder built from the real
    # source identifier -- never a fabricated company name.
    transformed["supplier_name"] = (
        "Supplier " + transformed["source_supplier_id"].astype(str)
    )

    transformed["country"] = SOURCE_COUNTRY

    return transformed[SUPPLIER_OUTPUT_COLUMNS]
