import pandas as pd


PRODUCT_OUTPUT_COLUMNS = [
    "product_id",
    "source_product_id",
    "category_id",
    "weight_g",
]


def transform_products(
    products: pd.DataFrame,
    categories: pd.DataFrame,
) -> pd.DataFrame:
    """
    Transform products and map them to processed category IDs.

    This is the real/derived subset of the commerce.products contract:
    category_id is REAL Olist data. Olist products carry no name or
    brand at all (fully anonymised, category and physical dimensions
    only) and nothing that correlates with a launch date --
    commerce.products.product_name, .brand, and .launch_date are all
    NOT NULL with no real source, so they are added by the separate S4b
    synthetic augmentation step, not here. source_product_id is retained
    only as an internal join key for downstream transforms (order_items)
    and is dropped before the final processed CSV is written.

    Real Olist product_weight_g is retained as weight_g -- not because
    commerce.products has a weight column (it does not), but because S4b
    needs it to derive commerce.product_variants.weight_grams from a
    real value rather than inventing one; weight_g is dropped before the
    final products.csv is saved. Real product_length_cm/height_cm/
    width_cm have no equivalent column anywhere in the canonical schema
    (neither commerce.products nor commerce.product_variants represents
    physical dimensions beyond weight) and are not carried through at
    all -- a genuine, documented loss of real data the schema has no
    place for, not an omission.
    """

    required_product_columns = {
        "product_id",
        "product_category_name",
        "product_weight_g",
    }

    missing_product_columns = (
        required_product_columns - set(products.columns)
    )

    if missing_product_columns:
        raise ValueError(
            "Products dataset is missing required columns: "
            f"{sorted(missing_product_columns)}"
        )

    required_category_columns = {
        "category_id",
        "source_category_name",
    }

    missing_category_columns = (
        required_category_columns - set(categories.columns)
    )

    if missing_category_columns:
        raise ValueError(
            "Processed categories are missing required columns: "
            f"{sorted(missing_category_columns)}"
        )

    transformed = products.rename(
        columns={
            "product_id": "source_product_id",
            "product_weight_g": "weight_g",
        }
    ).copy()

    category_lookup = categories[
        [
            "category_id",
            "source_category_name",
        ]
    ].copy()

    transformed = transformed.merge(
        category_lookup,
        how="left",
        left_on="product_category_name",
        right_on="source_category_name",
        validate="many_to_one",
    )

    # Zero temporarily represents an unknown or unmapped category.
    transformed["category_id"] = (
        transformed["category_id"]
        .fillna(0)
        .astype(int)
    )

    transformed.insert(
        0,
        "product_id",
        range(1, len(transformed) + 1),
    )

    if transformed["source_product_id"].duplicated().any():
        raise ValueError(
            "Duplicate source product IDs were found"
        )

    return transformed[PRODUCT_OUTPUT_COLUMNS]
