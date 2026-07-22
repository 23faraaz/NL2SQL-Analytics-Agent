import pandas as pd

from etl.logging_config import get_logger


logger = get_logger(__name__)


PROCESSED_REQUIRED_COLUMNS = {
    "customers": {
        "customer_id",
        "source_customer_id",
        "source_customer_unique_id",
        "source_postcode_prefix",
        "source_city",
        "source_state",
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
        "source_supplier_id",
        "source_postcode_prefix",
        "source_city",
        "source_state",
    },
    "orders": {
        "order_id",
        "source_order_id",
        "customer_id",
        "status",
        "ordered_at",
        "approved_at",
        "shipped_at",
        "delivered_at",
        "estimated_delivery_at",
    },
    "order_items": {
        "order_item_key",
        "order_id",
        "product_id",
        "supplier_id",
        "line_number",
        "unit_price_gbp",
        "freight_value_gbp",
        "shipping_deadline",
    },
    "payments": {
        "payment_id",
        "order_id",
        "payment_sequence",
        "payment_type",
        "payment_installments",
        "payment_value_gbp",
    },
}


PRIMARY_KEYS = {
    "customers": "customer_id",
    "categories": "category_id",
    "products": "product_id",
    "suppliers": "supplier_id",
    "orders": "order_id",
    "order_items": "order_item_key",
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


def validate_order_dates(
    orders: pd.DataFrame,
) -> None:
    invalid_approval_dates = (
        orders["approved_at"].notna()
        & (orders["approved_at"] < orders["ordered_at"])
    )

    if invalid_approval_dates.any():
        logger.warning(
            "%d orders were approved before their purchase timestamp",
            int(invalid_approval_dates.sum()),
        )

    invalid_delivery_dates = (
        orders["delivered_at"].notna()
        & (orders["delivered_at"] < orders["ordered_at"])
    )

    if invalid_delivery_dates.any():
        logger.warning(
            "%d orders were delivered before their purchase timestamp",
            int(invalid_delivery_dates.sum()),
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
    logger.info("Starting processed dataset validation")

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
        "unit_price_gbp",
    )

    validate_non_negative_column(
        "order_items",
        order_items,
        "freight_value_gbp",
    )

    validate_non_negative_column(
        "payments",
        payments,
        "payment_value_gbp",
    )

    validate_order_dates(orders)

    logger.info(
        "Processed dataset validation completed successfully"
    )