import pandas as pd

from etl.logging_config import get_logger


logger = get_logger(__name__)


def validate_foreign_key(
    *,
    child_dataframe: pd.DataFrame,
    child_column: str,
    parent_dataframe: pd.DataFrame,
    parent_column: str,
    relationship_name: str,
) -> None:
    """
    Verify that every non-null child key exists in the parent table.
    """

    child_values = set(
        child_dataframe[child_column]
        .dropna()
        .tolist()
    )

    parent_values = set(
        parent_dataframe[parent_column]
        .dropna()
        .tolist()
    )

    missing_values = child_values - parent_values

    if missing_values:
        sample_values = sorted(
            missing_values,
            key=str,
        )[:10]

        raise ValueError(
            f"Relationship validation failed for {relationship_name}. "
            f"{len(missing_values):,} unresolved keys found. "
            f"Sample: {sample_values}"
        )

    logger.info(
        "Validated relationship: %s",
        relationship_name,
    )


def validate_all_relationships(
    *,
    customers: pd.DataFrame,
    categories: pd.DataFrame,
    products: pd.DataFrame,
    orders: pd.DataFrame,
    order_items: pd.DataFrame,
    payments: pd.DataFrame,
) -> None:
    """
    Validate all foreign-key relationships between processed datasets.
    """

    logger.info("Starting relationship validation")

    validate_foreign_key(
        child_dataframe=orders,
        child_column="customer_id",
        parent_dataframe=customers,
        parent_column="customer_id",
        relationship_name="orders.customer_id -> customers.customer_id",
    )

    validate_foreign_key(
        child_dataframe=products,
        child_column="category_id",
        parent_dataframe=categories,
        parent_column="category_id",
        relationship_name="products.category_id -> categories.category_id",
    )

    validate_foreign_key(
        child_dataframe=order_items,
        child_column="order_id",
        parent_dataframe=orders,
        parent_column="order_id",
        relationship_name="order_items.order_id -> orders.order_id",
    )

    validate_foreign_key(
        child_dataframe=order_items,
        child_column="product_id",
        parent_dataframe=products,
        parent_column="product_id",
        relationship_name="order_items.product_id -> products.product_id",
    )

    validate_foreign_key(
        child_dataframe=payments,
        child_column="order_id",
        parent_dataframe=orders,
        parent_column="order_id",
        relationship_name="payments.order_id -> orders.order_id",
    )

    logger.info(
        "Relationship validation completed successfully"
    )