import pandas as pd

from etl.config import ACQUISITION_CHANNELS
from etl.logging_config import get_logger


logger = get_logger(__name__)


# These contracts describe the final, commerce-loadable shape produced
# after S4b synthetic augmentation -- they match commerce.customers,
# commerce.products, commerce.product_variants, and commerce.order_items
# exactly (the columns this loader will COPY).
AUGMENTED_REQUIRED_COLUMNS = {
    "customers": {
        "customer_id",
        "first_name",
        "last_name",
        "email",
        "phone",
        "address_line_1",
        "city",
        "region",
        "postcode",
        "country",
        "acquisition_channel",
    },
    "products": {
        "product_id",
        "category_id",
        "product_name",
        "brand",
        "launch_date",
    },
    "product_variants": {
        "variant_id",
        "product_id",
        "sku",
        "colour",
        "size",
        "unit_cost",
        "retail_price",
        "weight_grams",
    },
    "order_items": {
        "order_item_id",
        "order_id",
        "variant_id",
        "quantity",
        "unit_sale_price",
        "unit_cost_at_sale",
        "line_revenue",
        "line_cost",
        "line_profit",
    },
}


PRIMARY_KEYS = {
    "customers": "customer_id",
    "products": "product_id",
    "product_variants": "variant_id",
    "order_items": "order_item_id",
}


def validate_required_columns(
    dataset_name: str,
    dataframe: pd.DataFrame,
) -> None:
    required_columns = AUGMENTED_REQUIRED_COLUMNS[dataset_name]
    missing_columns = required_columns - set(dataframe.columns)

    if missing_columns:
        raise ValueError(
            f"Augmented {dataset_name} dataset is missing columns: "
            f"{sorted(missing_columns)}"
        )


def validate_primary_key(
    dataset_name: str,
    dataframe: pd.DataFrame,
) -> None:
    primary_key = PRIMARY_KEYS[dataset_name]

    null_count = int(dataframe[primary_key].isna().sum())

    if null_count:
        raise ValueError(
            f"Augmented {dataset_name}.{primary_key} contains "
            f"{null_count:,} null values"
        )

    duplicate_count = int(dataframe[primary_key].duplicated().sum())

    if duplicate_count:
        raise ValueError(
            f"Augmented {dataset_name}.{primary_key} contains "
            f"{duplicate_count:,} duplicate values"
        )


def validate_no_null_required_fields(
    dataset_name: str,
    dataframe: pd.DataFrame,
) -> None:
    """
    commerce's NOT NULL columns must never be silently null after
    augmentation -- this is the check that would have caught the exact
    gap S4a's loader run deliberately demonstrated.
    """

    required_columns = AUGMENTED_REQUIRED_COLUMNS[dataset_name]

    for column in required_columns:
        null_count = int(dataframe[column].isna().sum())

        if null_count:
            raise ValueError(
                f"Augmented {dataset_name}.{column} contains "
                f"{null_count:,} null values, but commerce.{dataset_name} "
                "requires it to be NOT NULL"
            )


def validate_customers(customers: pd.DataFrame) -> None:
    validate_required_columns("customers", customers)
    validate_primary_key("customers", customers)
    validate_no_null_required_fields("customers", customers)

    if customers["email"].duplicated().any():
        raise ValueError(
            "Augmented customers.email contains duplicate values, but "
            "commerce.customers.email is UNIQUE"
        )

    invalid_channels = (
        set(customers["acquisition_channel"].unique())
        - set(ACQUISITION_CHANNELS)
    )

    if invalid_channels:
        raise ValueError(
            "Augmented customers.acquisition_channel contains values "
            f"outside the commerce schema's CHECK constraint: "
            f"{sorted(invalid_channels)}"
        )

    logger.info(
        "Validated augmented customers dataset (%d rows)",
        len(customers),
    )


def validate_products(products: pd.DataFrame) -> None:
    validate_required_columns("products", products)
    validate_primary_key("products", products)
    validate_no_null_required_fields("products", products)

    logger.info(
        "Validated augmented products dataset (%d rows)",
        len(products),
    )


def validate_product_variants(product_variants: pd.DataFrame) -> None:
    validate_required_columns("product_variants", product_variants)
    validate_primary_key("product_variants", product_variants)
    validate_no_null_required_fields("product_variants", product_variants)

    if product_variants["sku"].duplicated().any():
        raise ValueError(
            "Augmented product_variants.sku contains duplicate values, "
            "but commerce.product_variants.sku is UNIQUE"
        )

    if (product_variants["unit_cost"] < 0).any():
        raise ValueError(
            "Augmented product_variants.unit_cost contains negative values"
        )

    if (product_variants["retail_price"] < 0).any():
        raise ValueError(
            "Augmented product_variants.retail_price contains negative "
            "values"
        )

    margin_violations = int(
        (
            product_variants["retail_price"]
            < product_variants["unit_cost"]
        ).sum()
    )

    if margin_violations:
        raise ValueError(
            f"{margin_violations:,} generated variants have "
            "retail_price < unit_cost, violating "
            "chk_product_variants_margin"
        )

    logger.info(
        "Validated augmented product_variants dataset (%d rows)",
        len(product_variants),
    )


def validate_order_items(order_items: pd.DataFrame) -> None:
    validate_required_columns("order_items", order_items)
    validate_primary_key("order_items", order_items)
    validate_no_null_required_fields("order_items", order_items)

    if (order_items["quantity"] <= 0).any():
        raise ValueError(
            "Augmented order_items.quantity contains non-positive values"
        )

    if (order_items["unit_sale_price"] < 0).any():
        raise ValueError(
            "Augmented order_items.unit_sale_price contains negative values"
        )

    if (order_items["unit_cost_at_sale"] < 0).any():
        raise ValueError(
            "Augmented order_items.unit_cost_at_sale contains negative "
            "values"
        )

    if (order_items["line_revenue"] < 0).any():
        raise ValueError(
            "Augmented order_items.line_revenue contains negative values"
        )

    if (order_items["line_cost"] < 0).any():
        raise ValueError(
            "Augmented order_items.line_cost contains negative values"
        )

    logger.info(
        "Validated augmented order_items dataset (%d rows)",
        len(order_items),
    )


def validate_all_augmented(
    *,
    customers: pd.DataFrame,
    products: pd.DataFrame,
    product_variants: pd.DataFrame,
    order_items: pd.DataFrame,
) -> None:
    logger.info("Starting augmented (S4b) dataset validation")

    validate_customers(customers)
    validate_products(products)
    validate_product_variants(product_variants)
    validate_order_items(order_items)

    unresolved_variants = (
        set(order_items["variant_id"].dropna())
        - set(product_variants["variant_id"])
    )

    if unresolved_variants:
        raise ValueError(
            "order_items references variant_id values that do not exist "
            f"in the generated product_variants: {sorted(unresolved_variants)[:10]}"
        )

    logger.info(
        "Validated relationship: order_items.variant_id -> "
        "product_variants.variant_id"
    )

    logger.info(
        "Augmented (S4b) dataset validation completed successfully"
    )
