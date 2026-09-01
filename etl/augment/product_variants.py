import random

import pandas as pd

from etl.augment.config import (
    AUGMENTATION_SEED,
    MAX_MARKUP_MULTIPLIER,
    MAX_VARIANTS_PER_PRODUCT,
    MIN_MARKUP_MULTIPLIER,
    MIN_VARIANTS_PER_PRODUCT,
    VARIANT_COLOURS,
    VARIANT_SIZES,
)

# Cost as a fraction of a product's real average observed sale price, for
# products that have real order_items to calibrate against. Keeps
# unit_cost DERIVED from real transaction prices rather than an
# arbitrary independent SYNTHETIC value, so unit_sale_price >
# unit_cost_at_sale (a positive line_profit) holds in the common case --
# occasional negative-profit line items from real price variance are
# still possible and realistic, not a data bug.
MIN_COST_RATIO_OF_REAL_PRICE = 0.35
MAX_COST_RATIO_OF_REAL_PRICE = 0.65


VARIANT_OUTPUT_COLUMNS = [
    "variant_id",
    "product_id",
    "sku",
    "colour",
    "size",
    "unit_cost",
    "retail_price",
    "weight_grams",
]

# SYNTHETIC: sku, colour, size, unit_cost, retail_price -- Olist has no
# variant concept at all, so all five are a modelling choice, not derived
# from any real signal. weight_grams is DERIVED: copied directly from the
# product's REAL Olist weight_g rather than invented.
SYNTHETIC_COLUMNS = ["sku", "colour", "size", "unit_cost", "retail_price"]


def generate_product_variants(
    products: pd.DataFrame,
    order_items: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """
    Generate commerce.product_variants rows for every real product.

    colour, size, and sku are entirely SYNTHETIC. weight_grams is
    DERIVED from the product's real Olist weight. unit_cost is DERIVED
    where possible: for a product with real order_items, it is a
    calibrated fraction of that product's real average sale price rather
    than an arbitrary independent value, so unit_cost_at_sale rarely
    exceeds a real transaction's price. Products with no observed real
    order items (none in this dataset) fall back to a SYNTHETIC cost
    range. retail_price is DERIVED from unit_cost via a random markup
    (commerce's chk_product_variants_margin requires retail_price >=
    unit_cost, trivially satisfied by construction).

    Generation is deterministic for a given ETL_AUGMENTATION_SEED and the
    number of variants per product is configurable via
    ETL_MIN_VARIANTS_PER_PRODUCT / ETL_MAX_VARIANTS_PER_PRODUCT.
    """

    required_columns = {"product_id", "weight_g"}
    missing_columns = required_columns - set(products.columns)

    if missing_columns:
        raise ValueError(
            "Processed products are missing required columns: "
            f"{sorted(missing_columns)}"
        )

    average_real_price_by_product: dict[int, float] = {}

    if order_items is not None and not order_items.empty:
        required_item_columns = {"product_id", "unit_sale_price"}
        missing_item_columns = required_item_columns - set(order_items.columns)

        if missing_item_columns:
            raise ValueError(
                "Order items are missing required columns: "
                f"{sorted(missing_item_columns)}"
            )

        average_real_price_by_product = (
            order_items.groupby("product_id")["unit_sale_price"].mean().to_dict()
        )

    rng = random.Random(AUGMENTATION_SEED)

    rows: list[dict] = []
    next_variant_id = 1

    for _, product in products.iterrows():
        variant_count = rng.randint(
            MIN_VARIANTS_PER_PRODUCT,
            MAX_VARIANTS_PER_PRODUCT,
        )

        colours = rng.sample(
            VARIANT_COLOURS,
            k=min(variant_count, len(VARIANT_COLOURS)),
        )

        real_average_price = average_real_price_by_product.get(
            int(product["product_id"])
        )

        if real_average_price:
            cost_ratio = rng.uniform(
                MIN_COST_RATIO_OF_REAL_PRICE,
                MAX_COST_RATIO_OF_REAL_PRICE,
            )
            unit_cost = round(real_average_price * cost_ratio, 2)
        else:
            # No real order_items observed for this product -- fall
            # back to a SYNTHETIC cost range with no real anchor.
            unit_cost = round(rng.uniform(4.0, 60.0), 2)

        markup = rng.uniform(MIN_MARKUP_MULTIPLIER, MAX_MARKUP_MULTIPLIER)
        retail_price = round(unit_cost * markup, 2)

        product_weight = product["weight_g"]

        for index in range(variant_count):
            colour = colours[index % len(colours)]
            size = rng.choice(VARIANT_SIZES)

            rows.append(
                {
                    "variant_id": next_variant_id,
                    "product_id": int(product["product_id"]),
                    "sku": (
                        f"SKU-{int(product['product_id']):05d}"
                        f"-{colour[:3].upper()}-{size}"
                    ),
                    "colour": colour,
                    "size": size,
                    "unit_cost": unit_cost,
                    "retail_price": retail_price,
                    # DERIVED from the product's real Olist weight, not
                    # invented -- weight does not vary by colour/size here.
                    # commerce's chk_product_variants_weight requires NULL
                    # or a strictly positive value; a handful of real
                    # Olist rows record product_weight_g=0, which is not
                    # a real measurement of a weightless product -- it is
                    # the same "unknown" signal as a missing value, so it
                    # is treated identically (NULL), not passed through as
                    # a literal 0 that would violate a legitimate
                    # constraint on a data-entry artifact.
                    "weight_grams": (
                        int(product_weight)
                        if pd.notna(product_weight) and product_weight > 0
                        else None
                    ),
                }
            )

            next_variant_id += 1

    variants = pd.DataFrame(rows, columns=VARIANT_OUTPUT_COLUMNS)

    # weight_grams is a real-valued mix of ints and (for the small number
    # of real products with no recorded weight) None. A plain pandas
    # column can't hold that combination as int64 (no null representation)
    # and silently upcasts the whole column to float64 instead, which
    # writes clean integers like 225 as "225.0" in the saved CSV --
    # invalid input for commerce.product_variants.weight_grams INTEGER.
    # The nullable "Int64" extension dtype keeps real values as clean
    # integers and nulls as genuinely empty (not "nan"/"<NA>" text).
    variants["weight_grams"] = variants["weight_grams"].astype("Int64")

    if variants["sku"].duplicated().any():
        raise ValueError("Generated variant SKUs are not unique")

    return variants
