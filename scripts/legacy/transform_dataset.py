 from pathlib import Path
import sys

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"

BRL_TO_GBP_RATE = 0.15


def load_csv(filename: str, **kwargs) -> pd.DataFrame:
    file_path = RAW_DATA_DIR / filename

    if not file_path.exists():
        raise FileNotFoundError(f"Missing raw file: {file_path}")

    return pd.read_csv(file_path, **kwargs)


def transform_customers() -> pd.DataFrame:
    df = load_csv("olist_customers_dataset.csv")

    df = df.rename(
        columns={
            "customer_id": "source_customer_id",
            "customer_unique_id": "source_customer_unique_id",
            "customer_zip_code_prefix": "source_postcode_prefix",
            "customer_city": "source_city",
            "customer_state": "source_state",
        }
    ).copy()

    df.insert(0, "customer_id", range(1, len(df) + 1))

    return df[
        [
            "customer_id",
            "source_customer_id",
            "source_customer_unique_id",
            "source_postcode_prefix",
            "source_city",
            "source_state",
        ]
    ]


def transform_categories() -> pd.DataFrame:
    df = load_csv("product_category_name_translation.csv")

    df = df.drop_duplicates(
        subset=["product_category_name"]
    ).copy()

    df = df.rename(
        columns={
            "product_category_name": "source_category_name",
            "product_category_name_english": "category_name",
        }
    )

    df["category_name"] = (
        df["category_name"]
        .fillna("Unknown")
        .str.replace("_", " ", regex=False)
        .str.strip()
        .str.title()
    )

    df.insert(0, "category_id", range(1, len(df) + 1))

    return df[
        [
            "category_id",
            "source_category_name",
            "category_name",
        ]
    ]


def transform_products(categories: pd.DataFrame) -> pd.DataFrame:
    df = load_csv("olist_products_dataset.csv")

    df = df.rename(
        columns={
            "product_id": "source_product_id",
            "product_weight_g": "weight_g",
            "product_length_cm": "length_cm",
            "product_height_cm": "height_cm",
            "product_width_cm": "width_cm",
        }
    ).copy()

    category_lookup = categories[
        ["category_id", "source_category_name"]
    ].copy()

    df = df.merge(
        category_lookup,
        how="left",
        left_on="product_category_name",
        right_on="source_category_name",
        validate="many_to_one",
    )

    df["category_id"] = df["category_id"].fillna(0).astype(int)
    df.insert(0, "product_id", range(1, len(df) + 1))

    return df[
        [
            "product_id",
            "source_product_id",
            "category_id",
            "weight_g",
            "length_cm",
            "height_cm",
            "width_cm",
        ]
    ]


def transform_orders(customers: pd.DataFrame) -> pd.DataFrame:
    df = load_csv(
        "olist_orders_dataset.csv",
        parse_dates=[
            "order_purchase_timestamp",
            "order_approved_at",
            "order_delivered_carrier_date",
            "order_delivered_customer_date",
            "order_estimated_delivery_date",
        ],
    )

    df = df.rename(
        columns={
            "order_id": "source_order_id",
            "customer_id": "source_customer_id",
            "order_status": "status",
            "order_purchase_timestamp": "ordered_at",
            "order_approved_at": "approved_at",
            "order_delivered_carrier_date": "shipped_at",
            "order_delivered_customer_date": "delivered_at",
            "order_estimated_delivery_date": "estimated_delivery_at",
        }
    ).copy()

    customer_lookup = customers[
        ["customer_id", "source_customer_id"]
    ].copy()

    df = df.merge(
        customer_lookup,
        how="left",
        on="source_customer_id",
        validate="many_to_one",
    )

    if df["customer_id"].isna().any():
        missing = int(df["customer_id"].isna().sum())
        raise ValueError(
            f"{missing:,} orders could not be matched to customers"
        )

    df["customer_id"] = df["customer_id"].astype(int)
    df.insert(0, "order_id", range(1, len(df) + 1))

    result = df[
        [
            "order_id",
            "source_order_id",
            "customer_id",
            "status",
            "ordered_at",
            "approved_at",
            "shipped_at",
            "delivered_at",
            "estimated_delivery_at",
        ]
    ].copy()

    print("Orders columns:", result.columns.tolist())

    return result


def transform_order_items(
    orders: pd.DataFrame,
    products: pd.DataFrame,
) -> pd.DataFrame:
    required_order_columns = {"order_id", "source_order_id"}
    missing_order_columns = required_order_columns - set(orders.columns)

    if missing_order_columns:
        raise ValueError(
            "Orders dataframe is missing columns: "
            f"{sorted(missing_order_columns)}. "
            f"Available columns: {orders.columns.tolist()}"
        )

    required_product_columns = {"product_id", "source_product_id"}
    missing_product_columns = required_product_columns - set(products.columns)

    if missing_product_columns:
        raise ValueError(
            "Products dataframe is missing columns: "
            f"{sorted(missing_product_columns)}"
        )

    df = load_csv(
        "olist_order_items_dataset.csv",
        parse_dates=["shipping_limit_date"],
    )

    df = df.rename(
        columns={
            "order_id": "source_order_id",
            "product_id": "source_product_id",
            "order_item_id": "line_number",
            "shipping_limit_date": "shipping_deadline",
        }
    ).copy()

    order_lookup = orders[
        ["order_id", "source_order_id"]
    ].copy()

    product_lookup = products[
        ["product_id", "source_product_id"]
    ].copy()

    df = df.merge(
        order_lookup,
        how="left",
        on="source_order_id",
        validate="many_to_one",
    )

    df = df.merge(
        product_lookup,
        how="left",
        on="source_product_id",
        validate="many_to_one",
    )

    if df["order_id"].isna().any():
        missing = int(df["order_id"].isna().sum())
        raise ValueError(
            f"{missing:,} order items could not be matched to orders"
        )

    if df["product_id"].isna().any():
        missing = int(df["product_id"].isna().sum())
        raise ValueError(
            f"{missing:,} order items could not be matched to products"
        )

    df["order_id"] = df["order_id"].astype(int)
    df["product_id"] = df["product_id"].astype(int)

    df["unit_price_gbp"] = (
        df["price"] * BRL_TO_GBP_RATE
    ).round(2)

    df["freight_value_gbp"] = (
        df["freight_value"] * BRL_TO_GBP_RATE
    ).round(2)

    df.insert(0, "order_item_key", range(1, len(df) + 1))

    return df[
        [
            "order_item_key",
            "order_id",
            "product_id",
            "line_number",
            "unit_price_gbp",
            "freight_value_gbp",
            "shipping_deadline",
            "seller_id",
        ]
    ]


def save_dataframe(
    dataframe: pd.DataFrame,
    filename: str,
) -> None:
    output_path = PROCESSED_DATA_DIR / filename
    dataframe.to_csv(output_path, index=False)

    print(f"Saved {filename}: {len(dataframe):,} rows")


def main() -> int:
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)

    try:
        customers = transform_customers()
        categories = transform_categories()
        products = transform_products(categories)
        orders = transform_orders(customers)
        order_items = transform_order_items(orders, products)

        save_dataframe(customers, "customers.csv")
        save_dataframe(categories, "categories.csv")
        save_dataframe(products, "products.csv")
        save_dataframe(orders, "orders.csv")
        save_dataframe(order_items, "order_items.csv")

    except Exception as exc:
        print(f"TRANSFORMATION FAILED: {exc}")
        return 1

    print("\nInitial transformation completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
PY