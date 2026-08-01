import random
from datetime import timedelta

import pandas as pd
from faker import Faker

from etl.augment.config import AUGMENTATION_SEED, BRANDS


# commerce.products has no weight/dimension columns at all -- weight_g
# is carried through this function (needed by generate_product_variants
# to derive commerce.product_variants.weight_grams from a real value)
# but is not part of the true final commerce.products contract.
WORKING_COLUMNS = [
    "product_id",
    "category_id",
    "product_name",
    "brand",
    "launch_date",
    "weight_g",
]

PRODUCT_FINAL_COLUMNS = [
    "product_id",
    "category_id",
    "product_name",
    "brand",
    "launch_date",
]

# SYNTHETIC: product_name, brand, launch_date. category_id is REAL/DERIVED
# and passes through unchanged.
SYNTHETIC_COLUMNS = ["product_name", "brand", "launch_date"]


def augment_products(
    products: pd.DataFrame,
    categories: pd.DataFrame,
    earliest_order_date: pd.Timestamp,
) -> pd.DataFrame:
    """
    Add the product-identity fields Olist cannot provide (fully
    anonymised: category and physical dimensions only, no name or brand,
    and nothing that correlates with a launch date) to the S4a
    real/derived products output.

    product_name and brand are SYNTHETIC. launch_date is SYNTHETIC but
    bounded by a real anchor: every generated date falls before
    earliest_order_date (the earliest real order date in this dataset),
    so a product is never "launched" after its first real sale.
    """

    required_product_columns = {
        "product_id",
        "category_id",
        "weight_g",
    }
    missing_product_columns = (
        required_product_columns - set(products.columns)
    )

    if missing_product_columns:
        raise ValueError(
            "Processed products are missing required columns: "
            f"{sorted(missing_product_columns)}"
        )

    required_category_columns = {"category_id", "category_name"}
    missing_category_columns = (
        required_category_columns - set(categories.columns)
    )

    if missing_category_columns:
        raise ValueError(
            "Processed categories are missing required columns: "
            f"{sorted(missing_category_columns)}"
        )

    faker = Faker()
    faker.seed_instance(AUGMENTATION_SEED)
    rng = random.Random(AUGMENTATION_SEED)

    augmented = products.merge(
        categories[["category_id", "category_name"]],
        how="left",
        on="category_id",
        validate="many_to_one",
    )

    product_names: list[str] = []
    brands: list[str] = []
    launch_dates: list[pd.Timestamp] = []

    for _, row in augmented.iterrows():
        category_label = row["category_name"] or "General"

        descriptor = " ".join(
            word.title()
            for word in faker.words(nb=2)
        )

        product_names.append(f"{category_label} {descriptor}")
        brands.append(rng.choice(BRANDS))

        days_before_launch_window = rng.randint(30, 720)
        launch_dates.append(
            earliest_order_date - timedelta(days=days_before_launch_window)
        )

    augmented["product_name"] = product_names
    augmented["brand"] = brands
    augmented["launch_date"] = pd.to_datetime(launch_dates).date

    # weight_g is retained here for generate_product_variants; the
    # augmentation pipeline drops it before saving the true final
    # products.csv (see etl/augment/pipeline.py).
    return augmented[WORKING_COLUMNS]
