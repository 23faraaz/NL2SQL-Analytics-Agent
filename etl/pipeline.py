from etl.io import load_raw_csv, save_processed_csv
from etl.transform import (
    transform_categories,
    transform_customers,
    transform_order_items,
    transform_orders,
    transform_products,
)


def run_transformation_pipeline() -> None:
    """Run the current extract, transform and CSV staging pipeline."""

    print("Starting ETL transformation pipeline...\n")

    raw_customers = load_raw_csv(
        "olist_customers_dataset.csv"
    )

    raw_categories = load_raw_csv(
        "product_category_name_translation.csv"
    )

    raw_products = load_raw_csv(
        "olist_products_dataset.csv"
    )

    raw_orders = load_raw_csv(
        "olist_orders_dataset.csv"
    )

    raw_order_items = load_raw_csv(
        "olist_order_items_dataset.csv"
    )

    customers = transform_customers(
        raw_customers
    )

    categories = transform_categories(
        raw_categories
    )

    products = transform_products(
        raw_products,
        categories,
    )

    orders = transform_orders(
        raw_orders,
        customers,
    )

    order_items = transform_order_items(
        raw_order_items,
        orders,
        products,
    )

    save_processed_csv(
        customers,
        "customers.csv",
    )

    save_processed_csv(
        categories,
        "categories.csv",
    )

    save_processed_csv(
        products,
        "products.csv",
    )

    save_processed_csv(
        orders,
        "orders.csv",
    )

    save_processed_csv(
        order_items,
        "order_items.csv",
    )

    print(
        "\nETL transformation pipeline completed successfully."
    )