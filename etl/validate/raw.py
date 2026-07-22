import pandas as pd

from etl.logging_config import get_logger


logger = get_logger(__name__)


RAW_REQUIRED_COLUMNS = {
    "customers": {
        "customer_id",
        "customer_unique_id",
        "customer_zip_code_prefix",
        "customer_city",
        "customer_state",
    },
    "categories": {
        "product_category_name",
        "product_category_name_english",
    },
    "products": {
        "product_id",
        "product_category_name",
        "product_weight_g",
        "product_length_cm",
        "product_height_cm",
        "product_width_cm",
    },
    "orders": {
        "order_id",
        "customer_id",
        "order_status",
        "order_purchase_timestamp",
        "order_approved_at",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    },
    "order_items": {
        "order_id",
        "order_item_id",
        "product_id",
        "seller_id",
        "shipping_limit_date",
        "price",
        "freight_value",
    },
    "payments": {
        "order_id",
        "payment_sequential",
        "payment_type",
        "payment_installments",
        "payment_value",
    },
}


def validate_required_columns(
    dataset_name: str,
    dataframe: pd.DataFrame,
) -> None:
    """
    Verify that a raw dataset contains all required columns.
    """

    required_columns = RAW_REQUIRED_COLUMNS[dataset_name]
    missing_columns = required_columns - set(dataframe.columns)

    if missing_columns:
        raise ValueError(
            f"Raw {dataset_name} dataset is missing columns: "
            f"{sorted(missing_columns)}"
        )


def validate_not_empty(
    dataset_name: str,
    dataframe: pd.DataFrame,
) -> None:
    """
    Verify that a raw dataset contains at least one row.
    """

    if dataframe.empty:
        raise ValueError(
            f"Raw {dataset_name} dataset contains no rows"
        )


def validate_raw_dataset(
    dataset_name: str,
    dataframe: pd.DataFrame,
) -> None:
    """
    Run validation checks against one raw dataset.
    """

    validate_not_empty(
        dataset_name,
        dataframe,
    )

    validate_required_columns(
        dataset_name,
        dataframe,
    )

    logger.info(
        "Validated raw %s dataset (%d rows, %d columns)",
        dataset_name,
        len(dataframe),
        len(dataframe.columns),
    )


def validate_all_raw(
    *,
    customers: pd.DataFrame,
    categories: pd.DataFrame,
    products: pd.DataFrame,
    orders: pd.DataFrame,
    order_items: pd.DataFrame,
    payments: pd.DataFrame,
) -> None:
    """
    Validate all raw datasets required by the current pipeline.
    """

    logger.info("Starting raw dataset validation")

    datasets = {
        "customers": customers,
        "categories": categories,
        "products": products,
        "orders": orders,
        "order_items": order_items,
        "payments": payments,
    }

    for dataset_name, dataframe in datasets.items():
        validate_raw_dataset(
            dataset_name,
            dataframe,
        )

    logger.info("Raw dataset validation completed successfully")