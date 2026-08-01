# Raw data

This directory holds the real Olist Brazilian E-Commerce Public Dataset.
It is not committed to this repository (see `.gitignore`) and is not
bundled into any Docker image — the dataset is large and is not this
project's to redistribute.

Before running `docker compose up` or `python -m scripts.run_etl`,
download the dataset from Kaggle and place the following files directly
in this directory:

- `olist_customers_dataset.csv`
- `product_category_name_translation.csv`
- `olist_products_dataset.csv`
- `olist_sellers_dataset.csv`
- `olist_orders_dataset.csv`
- `olist_order_items_dataset.csv`
- `olist_order_payments_dataset.csv`

Source: <https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce>

Without these files present, `scripts/run_etl.py` (and therefore the
`db-init` container in `docker-compose.yml`) will fail immediately with a
clear `FileNotFoundError` naming the missing file, rather than silently
producing an empty or fabricated dataset.
