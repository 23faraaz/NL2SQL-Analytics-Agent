-- ============================================================
-- 003_indexes.sql
-- Commerce Intelligence Platform
--
-- Purpose:
-- Improve PostgreSQL performance for joins, operational queries,
-- analytics views and NL2SQL-generated queries.
--
-- Run after:
--   001_schema.sql
--   002_views.sql
--
-- Recommended:
-- Run ANALYZE again after loading the synthetic dataset.
-- ============================================================

BEGIN;


-- ============================================================
-- CUSTOMERS
-- ============================================================

-- customers.email already has a UNIQUE constraint, so PostgreSQL
-- automatically creates an index for it.

CREATE INDEX IF NOT EXISTS idx_customers_created_at
    ON customers (created_at);

CREATE INDEX IF NOT EXISTS idx_customers_city
    ON customers (city);

CREATE INDEX IF NOT EXISTS idx_customers_region
    ON customers (region);

CREATE INDEX IF NOT EXISTS idx_customers_country
    ON customers (country);

CREATE INDEX IF NOT EXISTS idx_customers_acquisition_channel
    ON customers (acquisition_channel);

CREATE INDEX IF NOT EXISTS idx_customers_marketing_consent
    ON customers (marketing_consent)
    WHERE marketing_consent = TRUE;

CREATE INDEX IF NOT EXISTS idx_customers_location
    ON customers (country, region, city);


-- ============================================================
-- CUSTOMER SEGMENTS
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_customer_segment_memberships_segment_id
    ON customer_segment_memberships (segment_id);

CREATE INDEX IF NOT EXISTS idx_customer_segment_memberships_active
    ON customer_segment_memberships (customer_id, segment_id)
    WHERE removed_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_customer_segment_memberships_assigned_at
    ON customer_segment_memberships (assigned_at);


-- ============================================================
-- SUPPLIERS
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_suppliers_active
    ON suppliers (supplier_id)
    WHERE active = TRUE;

CREATE INDEX IF NOT EXISTS idx_suppliers_country
    ON suppliers (country);

CREATE INDEX IF NOT EXISTS idx_suppliers_lead_time_days
    ON suppliers (lead_time_days);


-- ============================================================
-- CATEGORIES
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_categories_parent_category_id
    ON categories (parent_category_id);


-- ============================================================
-- PRODUCTS
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_products_category_id
    ON products (category_id);

CREATE INDEX IF NOT EXISTS idx_products_supplier_id
    ON products (supplier_id);

CREATE INDEX IF NOT EXISTS idx_products_brand
    ON products (brand);

CREATE INDEX IF NOT EXISTS idx_products_launch_date
    ON products (launch_date);

CREATE INDEX IF NOT EXISTS idx_products_active
    ON products (product_id)
    WHERE active = TRUE;

CREATE INDEX IF NOT EXISTS idx_products_category_active
    ON products (category_id, product_id)
    WHERE active = TRUE;


-- ============================================================
-- PRODUCT VARIANTS
-- ============================================================

-- sku and barcode already have UNIQUE constraints, which create
-- indexes automatically.

CREATE INDEX IF NOT EXISTS idx_product_variants_product_id
    ON product_variants (product_id);

CREATE INDEX IF NOT EXISTS idx_product_variants_colour
    ON product_variants (colour);

CREATE INDEX IF NOT EXISTS idx_product_variants_size
    ON product_variants (size);

CREATE INDEX IF NOT EXISTS idx_product_variants_retail_price
    ON product_variants (retail_price);

CREATE INDEX IF NOT EXISTS idx_product_variants_unit_cost
    ON product_variants (unit_cost);

CREATE INDEX IF NOT EXISTS idx_product_variants_active
    ON product_variants (variant_id)
    WHERE active = TRUE;

CREATE INDEX IF NOT EXISTS idx_product_variants_product_active
    ON product_variants (product_id, variant_id)
    WHERE active = TRUE;

CREATE INDEX IF NOT EXISTS idx_product_variants_colour_size
    ON product_variants (colour, size);


-- ============================================================
-- CAMPAIGNS
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_campaigns_channel
    ON campaigns (channel);

CREATE INDEX IF NOT EXISTS idx_campaigns_start_date
    ON campaigns (start_date);

CREATE INDEX IF NOT EXISTS idx_campaigns_end_date
    ON campaigns (end_date);

CREATE INDEX IF NOT EXISTS idx_campaigns_active
    ON campaigns (campaign_id)
    WHERE active = TRUE;

CREATE INDEX IF NOT EXISTS idx_campaigns_date_range
    ON campaigns (start_date, end_date);


-- ============================================================
-- DISCOUNT CODES
-- ============================================================

-- discount_codes.code already has a UNIQUE constraint.

CREATE INDEX IF NOT EXISTS idx_discount_codes_campaign_id
    ON discount_codes (campaign_id);

CREATE INDEX IF NOT EXISTS idx_discount_codes_valid_from
    ON discount_codes (valid_from);

CREATE INDEX IF NOT EXISTS idx_discount_codes_valid_until
    ON discount_codes (valid_until);

CREATE INDEX IF NOT EXISTS idx_discount_codes_active
    ON discount_codes (discount_code_id)
    WHERE active = TRUE;

CREATE INDEX IF NOT EXISTS idx_discount_codes_validity
    ON discount_codes (valid_from, valid_until)
    WHERE active = TRUE;


-- ============================================================
-- ORDERS
-- ============================================================

-- order_number already has a UNIQUE constraint.

CREATE INDEX IF NOT EXISTS idx_orders_customer_id
    ON orders (customer_id);

CREATE INDEX IF NOT EXISTS idx_orders_discount_code_id
    ON orders (discount_code_id);

CREATE INDEX IF NOT EXISTS idx_orders_campaign_id
    ON orders (campaign_id);

CREATE INDEX IF NOT EXISTS idx_orders_order_date
    ON orders (order_date);

CREATE INDEX IF NOT EXISTS idx_orders_status
    ON orders (status);

CREATE INDEX IF NOT EXISTS idx_orders_sales_channel
    ON orders (sales_channel);

CREATE INDEX IF NOT EXISTS idx_orders_shipping_city
    ON orders (shipping_city);

CREATE INDEX IF NOT EXISTS idx_orders_shipping_region
    ON orders (shipping_region);

CREATE INDEX IF NOT EXISTS idx_orders_total_amount
    ON orders (total_amount);

CREATE INDEX IF NOT EXISTS idx_orders_customer_date
    ON orders (customer_id, order_date DESC);

CREATE INDEX IF NOT EXISTS idx_orders_status_date
    ON orders (status, order_date DESC);

CREATE INDEX IF NOT EXISTS idx_orders_channel_date
    ON orders (sales_channel, order_date DESC);

CREATE INDEX IF NOT EXISTS idx_orders_campaign_date
    ON orders (campaign_id, order_date DESC)
    WHERE campaign_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_orders_non_cancelled_date
    ON orders (order_date DESC)
    WHERE status <> 'CANCELLED';

CREATE INDEX IF NOT EXISTS idx_orders_delivered_date
    ON orders (order_date DESC)
    WHERE status = 'DELIVERED';

CREATE INDEX IF NOT EXISTS idx_orders_refunded_date
    ON orders (order_date DESC)
    WHERE status IN ('PARTIALLY_REFUNDED', 'REFUNDED');

CREATE INDEX IF NOT EXISTS idx_orders_cancelled_date
    ON orders (order_date DESC)
    WHERE status = 'CANCELLED';


-- ============================================================
-- ORDER ITEMS
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_order_items_order_id
    ON order_items (order_id);

CREATE INDEX IF NOT EXISTS idx_order_items_variant_id
    ON order_items (variant_id);

CREATE INDEX IF NOT EXISTS idx_order_items_variant_order
    ON order_items (variant_id, order_id);

CREATE INDEX IF NOT EXISTS idx_order_items_line_revenue
    ON order_items (line_revenue);

CREATE INDEX IF NOT EXISTS idx_order_items_line_profit
    ON order_items (line_profit);

CREATE INDEX IF NOT EXISTS idx_order_items_quantity
    ON order_items (quantity);


-- ============================================================
-- PAYMENTS
-- ============================================================

-- payment_reference already has a UNIQUE constraint.

CREATE INDEX IF NOT EXISTS idx_payments_order_id
    ON payments (order_id);

CREATE INDEX IF NOT EXISTS idx_payments_payment_date
    ON payments (payment_date);

CREATE INDEX IF NOT EXISTS idx_payments_payment_method
    ON payments (payment_method);

CREATE INDEX IF NOT EXISTS idx_payments_payment_status
    ON payments (payment_status);

CREATE INDEX IF NOT EXISTS idx_payments_amount
    ON payments (amount);

CREATE INDEX IF NOT EXISTS idx_payments_order_status
    ON payments (order_id, payment_status);

CREATE INDEX IF NOT EXISTS idx_payments_status_date
    ON payments (payment_status, payment_date DESC);

CREATE INDEX IF NOT EXISTS idx_payments_successful_date
    ON payments (payment_date DESC)
    WHERE payment_status = 'SUCCESSFUL';

CREATE INDEX IF NOT EXISTS idx_payments_failed_date
    ON payments (payment_date DESC)
    WHERE payment_status = 'FAILED';


-- ============================================================
-- REFUNDS
-- ============================================================

-- refund_reference already has a UNIQUE constraint.

CREATE INDEX IF NOT EXISTS idx_refunds_order_id
    ON refunds (order_id);

CREATE INDEX IF NOT EXISTS idx_refunds_refund_date
    ON refunds (refund_date);

CREATE INDEX IF NOT EXISTS idx_refunds_refund_reason
    ON refunds (refund_reason);

CREATE INDEX IF NOT EXISTS idx_refunds_refund_status
    ON refunds (refund_status);

CREATE INDEX IF NOT EXISTS idx_refunds_refund_amount
    ON refunds (refund_amount);

CREATE INDEX IF NOT EXISTS idx_refunds_order_status
    ON refunds (order_id, refund_status);

CREATE INDEX IF NOT EXISTS idx_refunds_reason_date
    ON refunds (refund_reason, refund_date DESC);

CREATE INDEX IF NOT EXISTS idx_refunds_processed_date
    ON refunds (refund_date DESC)
    WHERE refund_status = 'PROCESSED';

CREATE INDEX IF NOT EXISTS idx_refunds_pending
    ON refunds (refund_date DESC)
    WHERE refund_status IN ('REQUESTED', 'APPROVED');


-- ============================================================
-- REFUND ITEMS
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_refund_items_refund_id
    ON refund_items (refund_id);

CREATE INDEX IF NOT EXISTS idx_refund_items_order_item_id
    ON refund_items (order_item_id);

CREATE INDEX IF NOT EXISTS idx_refund_items_return_to_stock
    ON refund_items (order_item_id)
    WHERE return_to_stock = TRUE;

CREATE INDEX IF NOT EXISTS idx_refund_items_not_returned_to_stock
    ON refund_items (order_item_id)
    WHERE return_to_stock = FALSE;


-- ============================================================
-- INVENTORY MOVEMENTS
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_inventory_movements_variant_id
    ON inventory_movements (variant_id);

CREATE INDEX IF NOT EXISTS idx_inventory_movements_movement_date
    ON inventory_movements (movement_date);

CREATE INDEX IF NOT EXISTS idx_inventory_movements_movement_type
    ON inventory_movements (movement_type);

CREATE INDEX IF NOT EXISTS idx_inventory_movements_warehouse
    ON inventory_movements (warehouse);

CREATE INDEX IF NOT EXISTS idx_inventory_movements_variant_date
    ON inventory_movements (variant_id, movement_date DESC);

CREATE INDEX IF NOT EXISTS idx_inventory_movements_type_date
    ON inventory_movements (movement_type, movement_date DESC);

CREATE INDEX IF NOT EXISTS idx_inventory_movements_warehouse_variant
    ON inventory_movements (warehouse, variant_id);

CREATE INDEX IF NOT EXISTS idx_inventory_movements_reference
    ON inventory_movements (reference_type, reference_id)
    WHERE reference_type IS NOT NULL
      AND reference_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_inventory_movements_sales
    ON inventory_movements (variant_id, movement_date DESC)
    WHERE movement_type = 'SALE';

CREATE INDEX IF NOT EXISTS idx_inventory_movements_purchase_receipts
    ON inventory_movements (variant_id, movement_date DESC)
    WHERE movement_type = 'PURCHASE_RECEIPT';

CREATE INDEX IF NOT EXISTS idx_inventory_movements_returns
    ON inventory_movements (variant_id, movement_date DESC)
    WHERE movement_type = 'RETURN';

CREATE INDEX IF NOT EXISTS idx_inventory_movements_negative_adjustments
    ON inventory_movements (variant_id, movement_date DESC)
    WHERE movement_type IN ('DAMAGED', 'LOST', 'TRANSFER_OUT');


COMMIT;

-- Planner statistics will initially contain little information because
-- the tables are empty. Run ANALYZE again after loading synthetic data.
ANALYZE;