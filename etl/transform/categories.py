import pandas as pd

CATEGORY_OUTPUT_COLUMNS = [
    "category_id",
    "source_category_name",
    "category_name",
]


def transform_categories(
    categories: pd.DataFrame,
) -> pd.DataFrame:
    """
    Transform the Olist category translation lookup.

    Category ID 0 is reserved for unknown or unmapped products.
    """

    required_columns = {
        "product_category_name",
        "product_category_name_english",
    }

    missing_columns = required_columns - set(categories.columns)

    if missing_columns:
        raise ValueError(
            "Category dataset is missing required columns: "
            f"{sorted(missing_columns)}"
        )

    transformed = categories.drop_duplicates(subset=["product_category_name"]).copy()

    transformed = transformed.rename(
        columns={
            "product_category_name": "source_category_name",
            "product_category_name_english": "category_name",
        }
    )

    transformed["category_name"] = (
        transformed["category_name"]
        .fillna("Unknown")
        .str.replace("_", " ", regex=False)
        .str.strip()
        .str.title()
    )

    transformed.insert(
        0,
        "category_id",
        range(1, len(transformed) + 1),
    )

    unknown_category = pd.DataFrame(
        [
            {
                "category_id": 0,
                "source_category_name": "unknown",
                "category_name": "Unknown",
            }
        ]
    )

    transformed = pd.concat(
        [
            unknown_category,
            transformed[CATEGORY_OUTPUT_COLUMNS],
        ],
        ignore_index=True,
    )

    return transformed[CATEGORY_OUTPUT_COLUMNS]
