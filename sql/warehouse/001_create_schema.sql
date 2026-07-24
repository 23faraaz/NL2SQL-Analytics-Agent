BEGIN;

CREATE SCHEMA IF NOT EXISTS warehouse;

DROP TABLE IF EXISTS warehouse.payments CASCADE;
DROP TABLE IF EXISTS warehouse.order_items CASCADE;
DROP TABLE IF EXISTS warehouse.orders CASCADE;
DROP TABLE IF EXISTS warehouse.products CASCADE;
DROP TABLE IF EXISTS warehouse.suppliers CASCADE;
DROP TABLE IF EXISTS warehouse.categories CASCADE;
DROP TABLE IF EXISTS warehouse.customers CASCADE;


CREATE TABLE warehouse.customers (
    customer_id INTEGER PRIMARY KEY,
    source_customer_id VARCHAR(32) NOT NULL UNIQUE,
    source_customer_unique_id VARCHAR(32) NOT NULL,
    source_postcode_prefix INTEGER,
    source_city VARCHAR(255) NOT NULL,
    source_state VARCHAR(10) NOT NULL
);


CREATE TABLE warehouse.categories (
    category_id INTEGER PRIMARY KEY,
    source_category_name VARCHAR(255),
    category_name VARCHAR(255) NOT NULL
);


CREATE TABLE warehouse.products (
    product_id INTEGER PRIMARY KEY,
    source_product_id VARCHAR(32) NOT NULL UNIQUE,
    category_id INTEGER,
    weight_g NUMERIC(12, 2),
    length_cm NUMERIC(12, 2),
    height_cm NUMERIC(12, 2),
    width_cm NUMERIC(12, 2),

    CONSTRAINT fk_products_category
        FOREIGN KEY (category_id)
        REFERENCES warehouse.categories(category_id),

    CONSTRAINT chk_products_weight_non_negative
        CHECK (weight_g IS NULL OR weight_g >= 0),

    CONSTRAINT chk_products_length_non_negative
        CHECK (length_cm IS NULL OR length_cm >= 0),

    CONSTRAINT chk_products_height_non_negative
        CHECK (height_cm IS NULL OR height_cm >= 0),

    CONSTRAINT chk_products_width_non_negative
        CHECK (width_cm IS NULL OR width_cm >= 0)
);


CREATE TABLE warehouse.suppliers (
    supplier_id INTEGER PRIMARY KEY,
    source_supplier_id VARCHAR(32) NOT NULL UNIQUE,
    source_postcode_prefix INTEGER,
    source_city VARCHAR(255) NOT NULL,
    source_state VARCHAR(10) NOT NULL
);


CREATE TABLE warehouse.orders (
    order_id INTEGER PRIMARY KEY,
    source_order_id VARCHAR(32) NOT NULL UNIQUE,
    customer_id INTEGER NOT NULL,
    status VARCHAR(50) NOT NULL,
    ordered_at TIMESTAMP,
    approved_at TIMESTAMP,
    shipped_at TIMESTAMP,
    delivered_at TIMESTAMP,
    estimated_delivery_at TIMESTAMP,

    CONSTRAINT fk_orders_customer
        FOREIGN KEY (customer_id)
        REFERENCES warehouse.customers(customer_id)
);


CREATE TABLE warehouse.order_items (
    order_item_key INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    supplier_id INTEGER NOT NULL,
    line_number INTEGER NOT NULL,
    unit_price_gbp NUMERIC(12, 2) NOT NULL,
    freight_value_gbp NUMERIC(12, 2) NOT NULL,
    shipping_deadline TIMESTAMP,

    CONSTRAINT fk_order_items_order
        FOREIGN KEY (order_id)
        REFERENCES warehouse.orders(order_id),

    CONSTRAINT fk_order_items_product
        FOREIGN KEY (product_id)
        REFERENCES warehouse.products(product_id),

    CONSTRAINT fk_order_items_supplier
        FOREIGN KEY (supplier_id)
        REFERENCES warehouse.suppliers(supplier_id),

    CONSTRAINT uq_order_items_order_line
        UNIQUE (order_id, line_number),

    CONSTRAINT chk_order_items_line_number_positive
        CHECK (line_number > 0),

    CONSTRAINT chk_order_items_unit_price_non_negative
        CHECK (unit_price_gbp >= 0),

    CONSTRAINT chk_order_items_freight_non_negative
        CHECK (freight_value_gbp >= 0)
);


CREATE TABLE warehouse.payments (
    payment_id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL,
    payment_sequence INTEGER NOT NULL,
    payment_type VARCHAR(50) NOT NULL,
    payment_installments INTEGER NOT NULL,
    payment_value_gbp NUMERIC(12, 2) NOT NULL,

    CONSTRAINT fk_payments_order
        FOREIGN KEY (order_id)
        REFERENCES warehouse.orders(order_id),

    CONSTRAINT uq_payments_order_sequence
        UNIQUE (order_id, payment_sequence),

    CONSTRAINT chk_payments_sequence_positive
        CHECK (payment_sequence > 0),

    CONSTRAINT chk_payments_installments_non_negative
        CHECK (payment_installments >= 0),

    CONSTRAINT chk_payments_value_non_negative
        CHECK (payment_value_gbp >= 0)
);


CREATE INDEX idx_customers_unique_id
    ON warehouse.customers(source_customer_unique_id);

CREATE INDEX idx_customers_location
    ON warehouse.customers(source_state, source_city);

CREATE INDEX idx_products_category_id
    ON warehouse.products(category_id);

CREATE INDEX idx_suppliers_location
    ON warehouse.suppliers(source_state, source_city);

CREATE INDEX idx_orders_customer_id
    ON warehouse.orders(customer_id);

CREATE INDEX idx_orders_status
    ON warehouse.orders(status);

CREATE INDEX idx_orders_ordered_at
    ON warehouse.orders(ordered_at);

CREATE INDEX idx_order_items_order_id
    ON warehouse.order_items(order_id);

CREATE INDEX idx_order_items_product_id
    ON warehouse.order_items(product_id);

CREATE INDEX idx_order_items_supplier_id
    ON warehouse.order_items(supplier_id);

CREATE INDEX idx_payments_order_id
    ON warehouse.payments(order_id);

CREATE INDEX idx_payments_type
    ON warehouse.payments(payment_type);

COMMIT;