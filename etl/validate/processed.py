import pandas as pd

from etl.logging_config import get_logger


logger = get_logger(__name__)


# These contracts describe the S4a (real/derived) stage of the pipeline,
# before S4b synthetic augmentation runs. customers, products, and
# order_items are not yet in their final commerce-loadable shape at this
# point -- see etl/validate/augmented.py for the post-augmentation
# contracts that match the commerce schema exactly.
PROCESSED_REQUIRED_COLUMNS = {
    "customers": {
        "customer_id",
        "source_customer_id",
        "city",
        "region",
        "postcode",
        "country",
    },
    "categories": {
        "category_id",
        "source_category_name",
        "category_name",
    },
    "products": {
        "product_id",
        "source_product_id",
        "category_id",
        "weight_g",
        "length_cm",
        "height_cm",
        "width_cm",
    },
    "suppliers": {
        "supplier_id",
        "supplier_name",
        "country",
    },
    "orders": {
        "order_id",
        "source_order_id",
        "customer_id",
        "order_number",
        "order_date",
        "status",
        "sales_channel",
        "shipping_city",
        "shipping_region",
        "shipping_postcode",
        "shipping_country",
        "subtotal",
        "shipping_cost",
        "total_amount",
    },
    "order_items": {
        "order_item_id",
        "order_id",
        "product_id",
        "quantity",
        "unit_sale_price",
        "line_revenue",
        "freight_value_gbp",
    },
    "payments": {
        "payment_id",
        "order_id",
        "payment_reference",
        "payment_method",
        "payment_status",
        "amount",
        "payment_date",
    },
}


PRIMARY_KEYS = {
    "customers": "customer_id",
    "categories": "category_id",
    "products": "product_id",
    "suppliers": "supplier_id",
    "orders": "order_id",
    "order_items": "order_item_id",
    "payments": "payment_id",
}


def validate_required_columns(
    dataset_name: str,
    dataframe: pd.DataFrame,
) -> None:
    required_columns = PROCESSED_REQUIRED_COLUMNS[dataset_name]
    missing_columns = required_columns - set(dataframe.columns)

    if missing_columns:
        raise ValueError(
            f"Processed {dataset_name} dataset is missing columns: "
            f"{sorted(missing_columns)}"
        )


def validate_primary_key(
    dataset_name: str,
    dataframe: pd.DataFrame,
) -> None:
    primary_key = PRIMARY_KEYS[dataset_name]

    null_count = int(
        dataframe[primary_key].isna().sum()
    )

    if null_count:
        raise ValueError(
            f"Processed {dataset_name}.{primary_key} contains "
            f"{null_count:,} null values"
        )

    duplicate_count = int(
        dataframe[primary_key].duplicated().sum()
    )

    if duplicate_count:
        raise ValueError(
            f"Processed {dataset_name}.{primary_key} contains "
            f"{duplicate_count:,} duplicate values"
        )


def validate_non_negative_column(
    dataset_name: str,
    dataframe: pd.DataFrame,
    column: str,
) -> None:
    numeric_values = pd.to_numeric(
        dataframe[column],
        errors="coerce",
    )

    negative_count = int(
        (numeric_values < 0).sum()
    )

    if negative_count:
        raise ValueError(
            f"Processed {dataset_name}.{column} contains "
            f"{negative_count:,} negative values"
        )


def validate_processed_dataset(
    dataset_name: str,
    dataframe: pd.DataFrame,
) -> None:
    if dataframe.empty:
        raise ValueError(
            f"Processed {dataset_name} dataset contains no rows"
        )

    validate_required_columns(
        dataset_name,
        dataframe,
    )

    validate_primary_key(
        dataset_name,
        dataframe,
    )

    logger.info(
        "Validated processed %s dataset (%d rows)",
        dataset_name,
        len(dataframe),
    )


def validate_all_processed(
    *,
    customers: pd.DataFrame,
    categories: pd.DataFrame,
    products: pd.DataFrame,
    suppliers: pd.DataFrame,
    orders: pd.DataFrame,
    order_items: pd.DataFrame,
    payments: pd.DataFrame,
) -> None:
    logger.info("Starting processed (S4a) dataset validation")

    datasets = {
        "customers": customers,
        "categories": categories,
        "products": products,
        "suppliers": suppliers,
        "orders": orders,
        "order_items": order_items,
        "payments": payments,
    }

    for dataset_name, dataframe in datasets.items():
        validate_processed_dataset(
            dataset_name,
            dataframe,
        )

    validate_non_negative_column(
        "order_items",
        order_items,
        "unit_sale_price",
    )

    validate_non_negative_column(
        "order_items",
        order_items,
        "line_revenue",
    )

    validate_non_negative_column(
        "orders",
        orders,
        "subtotal",
    )

    validate_non_negative_column(
        "orders",
        orders,
        "total_amount",
    )

    validate_non_negative_column(
        "payments",
        payments,
        "amount",
    )

    logger.info(
        "Processed (S4a) dataset validation completed successfully"
    )
