from etl.io import load_raw_csv, save_processed_csv
from etl.logging_config import get_logger
from etl.transform import (
    transform_categories,
    transform_customers,
    transform_order_items,
    transform_orders,
    transform_payments,
    transform_products,
    transform_suppliers,
)
from etl.validate import (
    validate_all_processed,
    validate_all_raw,
    validate_all_relationships,
)


logger = get_logger(__name__)


def run_transformation_pipeline() -> None:
    """
    Run the ETL transformation and CSV staging pipeline.
    """

    logger.info("Starting ETL transformation pipeline")

    try:
        logger.info("Loading raw datasets")

        raw_customers = load_raw_csv(
            "olist_customers_dataset.csv"
        )

        raw_categories = load_raw_csv(
            "product_category_name_translation.csv"
        )

        raw_products = load_raw_csv(
            "olist_products_dataset.csv"
        )

        raw_suppliers = load_raw_csv(
            "olist_sellers_dataset.csv"
        )

        raw_orders = load_raw_csv(
            "olist_orders_dataset.csv"
        )

        raw_order_items = load_raw_csv(
            "olist_order_items_dataset.csv"
        )

        raw_payments = load_raw_csv(
            "olist_order_payments_dataset.csv"
        )

        logger.info(
            "Loaded raw datasets: customers=%d, categories=%d, "
            "products=%d, suppliers=%d, orders=%d, "
            "order_items=%d, payments=%d",
            len(raw_customers),
            len(raw_categories),
            len(raw_products),
            len(raw_suppliers),
            len(raw_orders),
            len(raw_order_items),
            len(raw_payments),
        )

        validate_all_raw(
            customers=raw_customers,
            categories=raw_categories,
            products=raw_products,
            suppliers=raw_suppliers,
            orders=raw_orders,
            order_items=raw_order_items,
            payments=raw_payments,
        )

        logger.info("Transforming customers")
        customers = transform_customers(
            raw_customers
        )

        logger.info("Transforming categories")
        categories = transform_categories(
            raw_categories
        )

        logger.info("Transforming products")
        products = transform_products(
            raw_products,
            categories,
        )

        logger.info("Transforming suppliers")
        suppliers = transform_suppliers(
            raw_suppliers
        )

        logger.info("Transforming orders")
        orders = transform_orders(
            raw_orders,
            customers,
        )

        logger.info("Transforming order items")
        order_items = transform_order_items(
            raw_order_items,
            orders,
            products,
            suppliers,
        )

        logger.info("Transforming payments")
        payments = transform_payments(
            raw_payments,
            orders,
        )

        logger.info(
            "Transformation row counts: customers=%d, categories=%d, "
            "products=%d, suppliers=%d, orders=%d, "
            "order_items=%d, payments=%d",
            len(customers),
            len(categories),
            len(products),
            len(suppliers),
            len(orders),
            len(order_items),
            len(payments),
        )

        validate_all_processed(
            customers=customers,
            categories=categories,
            products=products,
            suppliers=suppliers,
            orders=orders,
            order_items=order_items,
            payments=payments,
        )

        validate_all_relationships(
            customers=customers,
            categories=categories,
            products=products,
            suppliers=suppliers,
            orders=orders,
            order_items=order_items,
            payments=payments,
        )

        logger.info("Saving processed datasets")

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
            suppliers,
            "suppliers.csv",
        )

        save_processed_csv(
            orders,
            "orders.csv",
        )

        save_processed_csv(
            order_items,
            "order_items.csv",
        )

        save_processed_csv(
            payments,
            "payments.csv",
        )

    except Exception:
        logger.exception(
            "ETL transformation pipeline failed"
        )
        raise

    logger.info(
        "ETL transformation pipeline completed successfully"
    )