from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"

EXPECTED_FILES = {
    "customers": "olist_customers_dataset.csv",
    "geolocation": "olist_geolocation_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "order_payments": "olist_order_payments_dataset.csv",
    "order_reviews": "olist_order_reviews_dataset.csv",
    "orders": "olist_orders_dataset.csv",
    "products": "olist_products_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "category_translation": "product_category_name_translation.csv",
}

REQUIRED_COLUMNS = {
    "customers": {
        "customer_id",
        "customer_unique_id",
        "customer_zip_code_prefix",
        "customer_city",
        "customer_state",
    },
    "geolocation": {
        "geolocation_zip_code_prefix",
        "geolocation_lat",
        "geolocation_lng",
        "geolocation_city",
        "geolocation_state",
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
    "order_payments": {
        "order_id",
        "payment_sequential",
        "payment_type",
        "payment_installments",
        "payment_value",
    },
    "order_reviews": {
        "review_id",
        "order_id",
        "review_score",
    },
    "orders": {
        "order_id",
        "customer_id",
        "order_status",
        "order_purchase_timestamp",
    },
    "products": {
        "product_id",
        "product_category_name",
    },
    "sellers": {
        "seller_id",
        "seller_zip_code_prefix",
        "seller_city",
        "seller_state",
    },
    "category_translation": {
        "product_category_name",
        "product_category_name_english",
    },
}


def validate_file_exists(dataset_name: str, filename: str) -> Path:
    file_path = RAW_DATA_DIR / filename

    if not file_path.exists():
        raise FileNotFoundError(
            f"Missing required dataset file for '{dataset_name}': {file_path}"
        )

    if file_path.stat().st_size == 0:
        raise ValueError(f"Dataset file is empty: {file_path}")

    return file_path


def load_dataset(dataset_name: str, filename: str) -> pd.DataFrame:
    file_path = validate_file_exists(dataset_name, filename)

    try:
        dataframe = pd.read_csv(file_path)
    except Exception as exc:
        raise RuntimeError(f"Could not read {file_path}: {exc}") from exc

    return dataframe


def validate_columns(dataset_name: str, dataframe: pd.DataFrame) -> None:
    required = REQUIRED_COLUMNS[dataset_name]
    actual = set(dataframe.columns)
    missing = required - actual

    if missing:
        raise ValueError(
            f"{dataset_name} is missing required columns: {sorted(missing)}"
        )


def print_dataset_summary(dataset_name: str, dataframe: pd.DataFrame) -> None:
    total_rows = len(dataframe)
    total_columns = len(dataframe.columns)
    duplicate_rows = int(dataframe.duplicated().sum())
    missing_cells = int(dataframe.isna().sum().sum())

    print(f"\n{dataset_name}")
    print("-" * len(dataset_name))
    print(f"Rows:              {total_rows:,}")
    print(f"Columns:           {total_columns}")
    print(f"Duplicate rows:    {duplicate_rows:,}")
    print(f"Missing cells:     {missing_cells:,}")
    print(
        f"Memory usage:      {dataframe.memory_usage(deep=True).sum() / 1_048_576:.2f} MB"
    )

    missing_by_column = dataframe.isna().sum()
    missing_by_column = missing_by_column[missing_by_column > 0].sort_values(
        ascending=False
    )

    if not missing_by_column.empty:
        print("Columns with missing values:")

        for column, count in missing_by_column.items():
            percentage = count / total_rows * 100 if total_rows else 0
            print(f"  - {column}: {count:,} ({percentage:.2f}%)")


def main() -> int:
    print(f"Raw dataset directory: {RAW_DATA_DIR}")

    if not RAW_DATA_DIR.exists():
        print(f"ERROR: Raw data directory does not exist: {RAW_DATA_DIR}")
        return 1

    loaded_datasets: dict[str, pd.DataFrame] = {}

    try:
        for dataset_name, filename in EXPECTED_FILES.items():
            dataframe = load_dataset(dataset_name, filename)
            validate_columns(dataset_name, dataframe)
            loaded_datasets[dataset_name] = dataframe
            print_dataset_summary(dataset_name, dataframe)

    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"\nVALIDATION FAILED: {exc}")
        return 1

    total_rows = sum(len(dataframe) for dataframe in loaded_datasets.values())

    print("\nDataset validation completed successfully.")
    print(f"Files validated: {len(loaded_datasets)}")
    print(f"Combined rows:   {total_rows:,}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
