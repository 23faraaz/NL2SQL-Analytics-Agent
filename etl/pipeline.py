from etl.io import load_raw_csv, save_processed_csv
from etl.logging_config import get_logger
from etl.transform import (
    finalize_order_totals,
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


# Columns to save to each processed CSV, in commerce-schema order. This
# strips internal join-only columns (source_*, and order_items'
# freight_value_gbp, which is consumed by finalize_order_totals but has
# no home on commerce.order_items) that transform functions retain in
# memory for downstream joins but that are not real commerce columns --
# the loader builds its COPY column list directly from each CSV's
# header, so an internal linkage column left in the file would be
# rejected by PostgreSQL as "column does not exist".
#
# order_items keeps product_id: it is not a commerce.order_items column
# either, but S4b's augmentation step needs it to resolve product_id ->
# variant_id, so it is intentionally retained here and dropped only once
# S4b produces the final order_items contract.
FINAL_PROCESSED_COLUMNS = {
    "customers": [
        "customer_id",
        "city",
        "region",
        "postcode",
        "country",
    ],
    "categories": [
        "category_id",
        "category_name",
    ],
    "products": [
        "product_id",
        "category_id",
        "weight_g",
        "length_cm",
        "height_cm",
        "width_cm",
    ],
    "suppliers": [
        "supplier_id",
        "supplier_name",
        "country",
    ],
    "orders": [
        "order_id",
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
    ],
    "order_items": [
        "order_item_id",
        "order_id",
        "product_id",
        "quantity",
        "unit_sale_price",
        "line_revenue",
    ],
    "payments": [
        "payment_id",
        "order_id",
        "payment_reference",
        "payment_method",
        "payment_status",
        "amount",
        "payment_date",
    ],
}


def run_transformation_pipeline() -> None:
    """
    Run the S4a ETL transformation and CSV staging pipeline.

    This produces the real/derived subset of the commerce schema
    contracts. It does not populate synthetic fields (customer identity,
    product identity, product variants) -- that is the separate S4b
    augmentation step, which reads this stage's processed CSVs and
    completes the commerce-loadable shape.
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
        )

        logger.info("Finalising order financial totals")
        orders = finalize_order_totals(
            orders,
            order_items,
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
            customers[FINAL_PROCESSED_COLUMNS["customers"]],
            "customers.csv",
        )

        save_processed_csv(
            categories[FINAL_PROCESSED_COLUMNS["categories"]],
            "categories.csv",
        )

        save_processed_csv(
            products[FINAL_PROCESSED_COLUMNS["products"]],
            "products.csv",
        )

        save_processed_csv(
            suppliers[FINAL_PROCESSED_COLUMNS["suppliers"]],
            "suppliers.csv",
        )

        save_processed_csv(
            orders[FINAL_PROCESSED_COLUMNS["orders"]],
            "orders.csv",
        )

        save_processed_csv(
            order_items[FINAL_PROCESSED_COLUMNS["order_items"]],
            "order_items.csv",
        )

        save_processed_csv(
            payments[FINAL_PROCESSED_COLUMNS["payments"]],
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
