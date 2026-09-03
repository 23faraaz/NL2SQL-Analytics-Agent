-- ============================================================
-- 001_schema.sql
-- Commerce Intelligence Platform
--
-- Purpose:
-- Create the transactional PostgreSQL schema for a UK fashion
-- e-commerce retailer.
--
-- Execution order:
--   1. 001_schema.sql
--   2. 002_views.sql
--   3. 003_indexes.sql
--   4. Load synthetic data
-- ============================================================


-- ============================================================
-- SCHEMA
-- ============================================================

CREATE SCHEMA IF NOT EXISTS commerce;

-- ============================================================
-- RESET
-- ============================================================



-- ============================================================
-- CUSTOMERS
-- ============================================================

CREATE TABLE IF NOT EXISTS commerce.customers (
    customer_id BIGSERIAL PRIMARY KEY,

    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,

    email VARCHAR(255) NOT NULL UNIQUE,
    phone VARCHAR(30),

    address_line_1 VARCHAR(255),
    address_line_2 VARCHAR(255),
    city VARCHAR(100),
    region VARCHAR(100),
    postcode VARCHAR(20),
    country VARCHAR(100) NOT NULL DEFAULT 'United Kingdom',

    acquisition_channel VARCHAR(50) NOT NULL,

    marketing_consent BOOLEAN NOT NULL DEFAULT FALSE,
    date_of_birth DATE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_customers_email
        CHECK (POSITION('@' IN email) > 1),

    CONSTRAINT chk_customers_acquisition_channel
        CHECK (
            acquisition_channel IN (
                'ORGANIC_SEARCH',
                'PAID_SEARCH',
                'PAID_SOCIAL',
                'ORGANIC_SOCIAL',
                'EMAIL',
                'REFERRAL',
                'INFLUENCER',
                'DIRECT',
                'AFFILIATE'
            )
        )
);


-- ============================================================
-- CUSTOMER SEGMENTS
-- ============================================================

CREATE TABLE IF NOT EXISTS commerce.customer_segments (
    segment_id BIGSERIAL PRIMARY KEY,

    segment_name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE IF NOT EXISTS commerce.customer_segment_memberships (
    customer_id BIGINT NOT NULL,
    segment_id BIGINT NOT NULL,

    assigned_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    removed_at TIMESTAMPTZ,

    PRIMARY KEY (customer_id, segment_id),

    CONSTRAINT fk_segment_membership_customer
        FOREIGN KEY (customer_id)
        REFERENCES commerce.customers(customer_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_segment_membership_segment
        FOREIGN KEY (segment_id)
        REFERENCES commerce.customer_segments(segment_id)
        ON DELETE CASCADE,

    CONSTRAINT chk_segment_membership_dates
        CHECK (
            removed_at IS NULL
            OR removed_at >= assigned_at
        )
);


-- ============================================================
-- SUPPLIERS
-- ============================================================

CREATE TABLE IF NOT EXISTS commerce.suppliers (
    supplier_id BIGSERIAL PRIMARY KEY,

    supplier_name VARCHAR(255) NOT NULL UNIQUE,
    contact_name VARCHAR(200),
    contact_email VARCHAR(255),
    contact_phone VARCHAR(30),

    country VARCHAR(100),
    lead_time_days INTEGER NOT NULL DEFAULT 14,

    active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_supplier_lead_time
        CHECK (lead_time_days >= 0)
);


-- ============================================================
-- CATEGORIES
-- ============================================================

CREATE TABLE IF NOT EXISTS commerce.categories (
    category_id BIGSERIAL PRIMARY KEY,

    category_name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,

    parent_category_id BIGINT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_categories_parent
        FOREIGN KEY (parent_category_id)
        REFERENCES commerce.categories(category_id)
        ON DELETE SET NULL
);


-- ============================================================
-- PRODUCTS
-- ============================================================

CREATE TABLE IF NOT EXISTS commerce.products (
    product_id BIGSERIAL PRIMARY KEY,

    category_id BIGINT NOT NULL,
    supplier_id BIGINT,

    product_name VARCHAR(255) NOT NULL,
    brand VARCHAR(150) NOT NULL,

    description TEXT,
    material VARCHAR(150),

    launch_date DATE NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_products_category
        FOREIGN KEY (category_id)
        REFERENCES commerce.categories(category_id)
        ON DELETE RESTRICT,

    CONSTRAINT fk_products_supplier
        FOREIGN KEY (supplier_id)
        REFERENCES commerce.suppliers(supplier_id)
        ON DELETE SET NULL
);


-- ============================================================
-- PRODUCT VARIANTS
-- ============================================================

CREATE TABLE IF NOT EXISTS commerce.product_variants (
    variant_id BIGSERIAL PRIMARY KEY,

    product_id BIGINT NOT NULL,

    sku VARCHAR(100) NOT NULL UNIQUE,
    barcode VARCHAR(50) UNIQUE,

    colour VARCHAR(100) NOT NULL,
    size VARCHAR(30) NOT NULL,

    unit_cost NUMERIC(12, 2) NOT NULL,
    retail_price NUMERIC(12, 2) NOT NULL,

    weight_grams INTEGER,

    active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_product_variants_product
        FOREIGN KEY (product_id)
        REFERENCES commerce.products(product_id)
        ON DELETE CASCADE,

    CONSTRAINT chk_product_variants_cost
        CHECK (unit_cost >= 0),

    CONSTRAINT chk_product_variants_price
        CHECK (retail_price >= 0),

    CONSTRAINT chk_product_variants_margin
        CHECK (retail_price >= unit_cost),

    CONSTRAINT chk_product_variants_weight
        CHECK (
            weight_grams IS NULL
            OR weight_grams > 0
        )
);


-- ============================================================
-- CAMPAIGNS
-- ============================================================

CREATE TABLE IF NOT EXISTS commerce.campaigns (
    campaign_id BIGSERIAL PRIMARY KEY,

    campaign_name VARCHAR(255) NOT NULL,
    channel VARCHAR(50) NOT NULL,

    start_date DATE NOT NULL,
    end_date DATE,

    budget NUMERIC(12, 2) NOT NULL DEFAULT 0,

    active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_campaign_channel
        CHECK (
            channel IN (
                'EMAIL',
                'PAID_SEARCH',
                'PAID_SOCIAL',
                'ORGANIC_SOCIAL',
                'INFLUENCER',
                'AFFILIATE'
            )
        ),

    CONSTRAINT chk_campaign_dates
        CHECK (
            end_date IS NULL
            OR end_date >= start_date
        ),

    CONSTRAINT chk_campaign_budget
        CHECK (budget >= 0)
);


-- ============================================================
-- DISCOUNT CODES
-- ============================================================

CREATE TABLE IF NOT EXISTS commerce.discount_codes (
    discount_code_id BIGSERIAL PRIMARY KEY,

    campaign_id BIGINT,

    code VARCHAR(50) NOT NULL UNIQUE,

    discount_type VARCHAR(20) NOT NULL,
    discount_value NUMERIC(12, 2) NOT NULL,

    minimum_order_value NUMERIC(12, 2) NOT NULL DEFAULT 0,

    valid_from TIMESTAMPTZ NOT NULL,
    valid_until TIMESTAMPTZ,

    maximum_uses INTEGER,
    active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_discount_codes_campaign
        FOREIGN KEY (campaign_id)
        REFERENCES commerce.campaigns(campaign_id)
        ON DELETE SET NULL,

    CONSTRAINT chk_discount_type
        CHECK (
            discount_type IN (
                'PERCENTAGE',
                'FIXED_AMOUNT'
            )
        ),

    CONSTRAINT chk_discount_value
        CHECK (discount_value > 0),

    CONSTRAINT chk_percentage_discount
        CHECK (
            discount_type <> 'PERCENTAGE'
            OR discount_value <= 100
        ),

    CONSTRAINT chk_discount_minimum_order
        CHECK (minimum_order_value >= 0),

    CONSTRAINT chk_discount_dates
        CHECK (
            valid_until IS NULL
            OR valid_until >= valid_from
        ),

    CONSTRAINT chk_discount_maximum_uses
        CHECK (
            maximum_uses IS NULL
            OR maximum_uses > 0
        )
);


-- ============================================================
-- ORDERS
-- ============================================================

CREATE TABLE IF NOT EXISTS commerce.orders (
    order_id BIGSERIAL PRIMARY KEY,

    customer_id BIGINT NOT NULL,
    discount_code_id BIGINT,
    campaign_id BIGINT,

    order_number VARCHAR(50) NOT NULL UNIQUE,

    order_date TIMESTAMPTZ NOT NULL,

    status VARCHAR(30) NOT NULL,
    sales_channel VARCHAR(30) NOT NULL,

    shipping_city VARCHAR(100),
    shipping_region VARCHAR(100),
    shipping_postcode VARCHAR(20),
    shipping_country VARCHAR(100) NOT NULL DEFAULT 'United Kingdom',

    subtotal NUMERIC(12, 2) NOT NULL,
    discount_amount NUMERIC(12, 2) NOT NULL DEFAULT 0,
    shipping_cost NUMERIC(12, 2) NOT NULL DEFAULT 0,
    tax_amount NUMERIC(12, 2) NOT NULL DEFAULT 0,
    total_amount NUMERIC(12, 2) NOT NULL,

    currency CHAR(3) NOT NULL DEFAULT 'GBP',

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_orders_customer
        FOREIGN KEY (customer_id)
        REFERENCES commerce.customers(customer_id)
        ON DELETE RESTRICT,

    CONSTRAINT fk_orders_discount_code
        FOREIGN KEY (discount_code_id)
        REFERENCES commerce.discount_codes(discount_code_id)
        ON DELETE SET NULL,

    CONSTRAINT fk_orders_campaign
        FOREIGN KEY (campaign_id)
        REFERENCES commerce.campaigns(campaign_id)
        ON DELETE SET NULL,

    CONSTRAINT chk_orders_status
        CHECK (
            status IN (
                'PENDING',
                'PAID',
                'PROCESSING',
                'SHIPPED',
                'DELIVERED',
                'PARTIALLY_REFUNDED',
                'REFUNDED',
                'CANCELLED'
            )
        ),

    CONSTRAINT chk_orders_sales_channel
        CHECK (
            sales_channel IN (
                'WEBSITE',
                'MOBILE_APP',
                'MARKETPLACE',
                'SOCIAL_COMMERCE'
            )
        ),

    CONSTRAINT chk_orders_subtotal
        CHECK (subtotal >= 0),

    CONSTRAINT chk_orders_discount
        CHECK (discount_amount >= 0),

    CONSTRAINT chk_orders_shipping
        CHECK (shipping_cost >= 0),

    CONSTRAINT chk_orders_tax
        CHECK (tax_amount >= 0),

    CONSTRAINT chk_orders_total
        CHECK (total_amount >= 0),

    CONSTRAINT chk_orders_currency
        CHECK (currency = 'GBP')
);


-- ============================================================
-- ORDER ITEMS
-- ============================================================

CREATE TABLE IF NOT EXISTS commerce.order_items (
    order_item_id BIGSERIAL PRIMARY KEY,

    order_id BIGINT NOT NULL,
    variant_id BIGINT NOT NULL,

    quantity INTEGER NOT NULL,

    unit_sale_price NUMERIC(12, 2) NOT NULL,
    unit_cost_at_sale NUMERIC(12, 2) NOT NULL,

    line_discount NUMERIC(12, 2) NOT NULL DEFAULT 0,
    line_revenue NUMERIC(12, 2) NOT NULL,
    line_cost NUMERIC(12, 2) NOT NULL,
    line_profit NUMERIC(12, 2) NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_order_items_order
        FOREIGN KEY (order_id)
        REFERENCES commerce.orders(order_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_order_items_variant
        FOREIGN KEY (variant_id)
        REFERENCES commerce.product_variants(variant_id)
        ON DELETE RESTRICT,

    CONSTRAINT uq_order_item_variant
        UNIQUE (order_id, variant_id),

    CONSTRAINT chk_order_items_quantity
        CHECK (quantity > 0),

    CONSTRAINT chk_order_items_sale_price
        CHECK (unit_sale_price >= 0),

    CONSTRAINT chk_order_items_cost
        CHECK (unit_cost_at_sale >= 0),

    CONSTRAINT chk_order_items_discount
        CHECK (line_discount >= 0),

    CONSTRAINT chk_order_items_revenue
        CHECK (line_revenue >= 0),

    CONSTRAINT chk_order_items_line_cost
        CHECK (line_cost >= 0)
);


-- ============================================================
-- PAYMENTS
-- ============================================================

CREATE TABLE IF NOT EXISTS commerce.payments (
    payment_id BIGSERIAL PRIMARY KEY,

    order_id BIGINT NOT NULL,

    payment_reference VARCHAR(100) NOT NULL UNIQUE,

    payment_method VARCHAR(30) NOT NULL,
    payment_status VARCHAR(30) NOT NULL,

    amount NUMERIC(12, 2) NOT NULL,
    currency CHAR(3) NOT NULL DEFAULT 'GBP',

    payment_date TIMESTAMPTZ NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_payments_order
        FOREIGN KEY (order_id)
        REFERENCES commerce.orders(order_id)
        ON DELETE CASCADE,

    CONSTRAINT chk_payments_method
        CHECK (
            payment_method IN (
                'CARD',
                'PAYPAL',
                'APPLE_PAY',
                'GOOGLE_PAY',
                'KLARNA',
                'BANK_TRANSFER',
                'GIFT_CARD'
            )
        ),

    CONSTRAINT chk_payments_status
        CHECK (
            payment_status IN (
                'PENDING',
                'SUCCESSFUL',
                'FAILED',
                'REFUNDED',
                'PARTIALLY_REFUNDED'
            )
        ),

    CONSTRAINT chk_payments_amount
        CHECK (amount >= 0),

    CONSTRAINT chk_payments_currency
        CHECK (currency = 'GBP')
);


-- ============================================================
-- REFUNDS
-- ============================================================

CREATE TABLE IF NOT EXISTS commerce.refunds (
    refund_id BIGSERIAL PRIMARY KEY,

    order_id BIGINT NOT NULL,

    refund_reference VARCHAR(100) NOT NULL UNIQUE,

    refund_date TIMESTAMPTZ NOT NULL,

    refund_reason VARCHAR(50) NOT NULL,
    refund_status VARCHAR(30) NOT NULL,

    refund_amount NUMERIC(12, 2) NOT NULL,

    notes TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_refunds_order
        FOREIGN KEY (order_id)
        REFERENCES commerce.orders(order_id)
        ON DELETE CASCADE,

    CONSTRAINT chk_refunds_reason
        CHECK (
            refund_reason IN (
                'SIZE_ISSUE',
                'DAMAGED',
                'DEFECTIVE',
                'WRONG_ITEM',
                'CHANGED_MIND',
                'LATE_DELIVERY',
                'NOT_AS_DESCRIBED',
                'OTHER'
            )
        ),

    CONSTRAINT chk_refunds_status
        CHECK (
            refund_status IN (
                'REQUESTED',
                'APPROVED',
                'REJECTED',
                'PROCESSED'
            )
        ),

    CONSTRAINT chk_refunds_amount
        CHECK (refund_amount > 0)
);


-- ============================================================
-- REFUND ITEMS
-- ============================================================

CREATE TABLE IF NOT EXISTS commerce.refund_items (
    refund_item_id BIGSERIAL PRIMARY KEY,

    refund_id BIGINT NOT NULL,
    order_item_id BIGINT NOT NULL,

    quantity INTEGER NOT NULL,
    refund_amount NUMERIC(12, 2) NOT NULL,

    return_to_stock BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_refund_items_refund
        FOREIGN KEY (refund_id)
        REFERENCES commerce.refunds(refund_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_refund_items_order_item
        FOREIGN KEY (order_item_id)
        REFERENCES commerce.order_items(order_item_id)
        ON DELETE RESTRICT,

    CONSTRAINT uq_refund_order_item
        UNIQUE (refund_id, order_item_id),

    CONSTRAINT chk_refund_items_quantity
        CHECK (quantity > 0),

    CONSTRAINT chk_refund_items_amount
        CHECK (refund_amount > 0)
);


-- ============================================================
-- INVENTORY MOVEMENTS
-- ============================================================

CREATE TABLE IF NOT EXISTS commerce.inventory_movements (
    movement_id BIGSERIAL PRIMARY KEY,

    variant_id BIGINT NOT NULL,

    movement_type VARCHAR(30) NOT NULL,
    quantity_change INTEGER NOT NULL,

    warehouse VARCHAR(100) NOT NULL DEFAULT 'London Fulfilment Centre',

    movement_date TIMESTAMPTZ NOT NULL,

    reference_type VARCHAR(30),
    reference_id BIGINT,

    notes TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_inventory_movements_variant
        FOREIGN KEY (variant_id)
        REFERENCES commerce.product_variants(variant_id)
        ON DELETE RESTRICT,

    CONSTRAINT chk_inventory_movement_type
        CHECK (
            movement_type IN (
                'OPENING_STOCK',
                'PURCHASE_RECEIPT',
                'SALE',
                'RETURN',
                'DAMAGED',
                'LOST',
                'MANUAL_ADJUSTMENT',
                'TRANSFER_IN',
                'TRANSFER_OUT'
            )
        ),

    CONSTRAINT chk_inventory_quantity_change
        CHECK (quantity_change <> 0),

    CONSTRAINT chk_inventory_movement_direction
        CHECK (
            (
                movement_type IN (
                    'OPENING_STOCK',
                    'PURCHASE_RECEIPT',
                    'RETURN',
                    'TRANSFER_IN'
                )
                AND quantity_change > 0
            )
            OR
            (
                movement_type IN (
                    'SALE',
                    'DAMAGED',
                    'LOST',
                    'TRANSFER_OUT'
                )
                AND quantity_change < 0
            )
            OR movement_type = 'MANUAL_ADJUSTMENT'
        ),

    CONSTRAINT chk_inventory_reference
        CHECK (
            (
                reference_type IS NULL
                AND reference_id IS NULL
            )
            OR
            (
                reference_type IS NOT NULL
                AND reference_id IS NOT NULL
            )
        )
);


-- ============================================================
-- COMMENTS FOR SCHEMA INTROSPECTION
-- ============================================================

COMMENT ON TABLE commerce.customers IS
    'Fashion retail customers and acquisition information.';

COMMENT ON TABLE commerce.customer_segments IS
    'Named business segments such as VIP, active, at-risk and inactive customers.';

COMMENT ON TABLE commerce.customer_segment_memberships IS
    'Assignment history between customers and business segments.';

COMMENT ON TABLE commerce.suppliers IS
    'Suppliers responsible for manufacturing or distributing products.';

COMMENT ON TABLE commerce.categories IS
    'Hierarchical fashion product categories.';

COMMENT ON TABLE commerce.products IS
    'Parent fashion products independent of size and colour.';

COMMENT ON TABLE commerce.product_variants IS
    'Sellable SKUs representing a product, colour and size combination.';

COMMENT ON TABLE commerce.campaigns IS
    'Marketing campaigns used for customer acquisition and sales attribution.';

COMMENT ON TABLE commerce.discount_codes IS
    'Promotional discount codes associated with campaigns.';

COMMENT ON TABLE commerce.orders IS
    'Customer orders with order-level financial totals and fulfilment status.';

COMMENT ON TABLE commerce.order_items IS
    'Products sold within an order, including historical price, cost and profit.';

COMMENT ON TABLE commerce.payments IS
    'Payment attempts and successful payment transactions for orders.';

COMMENT ON TABLE commerce.refunds IS
    'Order-level refund transactions.';

COMMENT ON TABLE commerce.refund_items IS
    'Individual refunded items linked to the original order items.';

COMMENT ON TABLE commerce.inventory_movements IS
    'Immutable stock movements used to calculate current and historical inventory.';


