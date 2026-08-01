import pandas as pd

from etl.augment.customers import augment_customers
from etl.augment.order_items import augment_order_items
from etl.augment.product_variants import generate_product_variants
from etl.augment.products import PRODUCT_FINAL_COLUMNS, augment_products
from etl.config import PROCESSED_DATA_DIR
from etl.io import save_processed_csv
from etl.logging_config import get_logger
from etl.validate.augmented import validate_all_augmented


logger = get_logger(__name__)


def run_augmentation_pipeline() -> None:
    """
    Run the S4b synthetic augmentation pipeline.

    Reads the S4a real/derived processed CSVs from disk and completes the
    commerce-loadable shape: customer identity, product identity, and
    product variants are added; order_items is resolved from product_id
    to variant_id with derived cost fields. Overwrites customers.csv,
    products.csv, and order_items.csv with their final versions, and
    writes the new product_variants.csv.
    """

    logger.info("Starting ETL synthetic augmentation pipeline (S4b)")

    try:
        customers = pd.read_csv(PROCESSED_DATA_DIR / "customers.csv")
        categories = pd.read_csv(PROCESSED_DATA_DIR / "categories.csv")
        products = pd.read_csv(PROCESSED_DATA_DIR / "products.csv")
        orders = pd.read_csv(PROCESSED_DATA_DIR / "orders.csv")
        order_items = pd.read_csv(PROCESSED_DATA_DIR / "order_items.csv")

        logger.info(
            "Loaded S4a processed datasets: customers=%d, categories=%d, "
            "products=%d, orders=%d, order_items=%d",
            len(customers),
            len(categories),
            len(products),
            len(orders),
            len(order_items),
        )

        logger.info("Augmenting customers with synthetic identity fields")
        customers = augment_customers(customers)

        earliest_order_date = pd.to_datetime(orders["order_date"]).min()

        logger.info("Augmenting products with synthetic identity fields")
        products = augment_products(
            products,
            categories,
            earliest_order_date,
        )

        logger.info("Generating synthetic product variants")
        product_variants = generate_product_variants(
            products,
            order_items,
        )

        logger.info("Resolving order items to generated variants")
        order_items = augment_order_items(
            order_items,
            product_variants,
        )

        logger.info(
            "Augmentation row counts: customers=%d, products=%d, "
            "product_variants=%d, order_items=%d",
            len(customers),
            len(products),
            len(product_variants),
            len(order_items),
        )

        validate_all_augmented(
            customers=customers,
            products=products,
            product_variants=product_variants,
            order_items=order_items,
        )

        logger.info("Saving augmented processed datasets")

        save_processed_csv(customers, "customers.csv")
        save_processed_csv(
            products[PRODUCT_FINAL_COLUMNS],
            "products.csv",
        )
        save_processed_csv(product_variants, "product_variants.csv")
        save_processed_csv(order_items, "order_items.csv")

    except Exception:
        logger.exception(
            "ETL synthetic augmentation pipeline failed"
        )
        raise

    logger.info(
        "ETL synthetic augmentation pipeline completed successfully"
    )
