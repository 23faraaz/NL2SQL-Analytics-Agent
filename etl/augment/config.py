import os

from etl.config import ACQUISITION_CHANNELS


__all__ = [
    "ACQUISITION_CHANNELS",
    "AUGMENTATION_SEED",
    "BRANDS",
    "MAX_MARKUP_MULTIPLIER",
    "MAX_VARIANTS_PER_PRODUCT",
    "MIN_MARKUP_MULTIPLIER",
    "MIN_VARIANTS_PER_PRODUCT",
    "VARIANT_COLOURS",
    "VARIANT_SIZES",
]


# Deterministic seed for every synthetic generator in this package.
# Overridable so a different (still deterministic, for a given value)
# dataset can be generated without touching code.
AUGMENTATION_SEED = int(os.getenv("ETL_AUGMENTATION_SEED", "42"))

# Tunable data volume: how many SKU-level variants to generate per real
# product. Olist has no variant concept at all, so this range is a
# modelling choice, not derived from any real signal.
MIN_VARIANTS_PER_PRODUCT = int(
    os.getenv("ETL_MIN_VARIANTS_PER_PRODUCT", "1")
)
MAX_VARIANTS_PER_PRODUCT = int(
    os.getenv("ETL_MAX_VARIANTS_PER_PRODUCT", "3")
)

# commerce.product_variants colour/size vocabularies. A modelling choice
# for a fashion-retail catalogue, not derived from Olist (which has no
# variant concept at all).
VARIANT_COLOURS = [
    "Black", "White", "Navy", "Grey", "Burgundy",
    "Olive", "Camel", "Charcoal", "Ivory", "Rust",
]
VARIANT_SIZES = ["XS", "S", "M", "L", "XL", "XXL"]

# Retail markup range applied to a synthetic unit_cost to derive
# retail_price (commerce.product_variants.chk_product_variants_margin
# requires retail_price >= unit_cost).
MIN_MARKUP_MULTIPLIER = float(
    os.getenv("ETL_MIN_MARKUP_MULTIPLIER", "1.4")
)
MAX_MARKUP_MULTIPLIER = float(
    os.getenv("ETL_MAX_MARKUP_MULTIPLIER", "2.5")
)

# commerce.products brand vocabulary. A modelling choice for a fashion
# retailer's house brands, not derived from Olist (which has none).
BRANDS = [
    "Northfield & Co.",
    "Aster Studio",
    "Marrow Supply",
    "Kestrel Goods",
    "Linden Row",
]
