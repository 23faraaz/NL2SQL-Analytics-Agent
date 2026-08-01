-- ============================================================
-- 002_views.sql
-- Commerce Intelligence Platform
--
-- Purpose:
-- Create analytics-ready PostgreSQL views for customer,
-- product, order, refund and inventory analysis.
--
-- Run after:
--   001_schema.sql
--
-- Run before:
--   003_indexes.sql
-- ============================================================

BEGIN;


-- ============================================================
-- RESET EXISTING VIEWS
-- ============================================================

DROP VIEW IF EXISTS commerce.inventory_velocity CASCADE;
DROP VIEW IF EXISTS commerce.refund_metrics CASCADE;
DROP VIEW IF EXISTS commerce.product_performance CASCADE;
DROP VIEW IF EXISTS commerce.monthly_sales_metrics CASCADE;
DROP VIEW IF EXISTS commerce.customer_lifetime_metrics CASCADE;
DROP VIEW IF EXISTS commerce.order_financials CASCADE;
DROP VIEW IF EXISTS commerce.current_inventory CASCADE;


-- ============================================================
-- 1. CURRENT INVENTORY
-- ============================================================

CREATE VIEW commerce.current_inventory AS
SELECT
    pv.variant_id,
    pv.sku,
    p.product_id,
    p.product_name,
    p.brand,
    c.category_id,
    c.category_name,
    pv.colour,
    pv.size,
    pv.unit_cost,
    pv.retail_price,
    pv.active AS variant_active,
    p.active AS product_active,

    COALESCE(
        SUM(im.quantity_change),
        0
    )::BIGINT AS current_stock,

    COALESCE(
        SUM(im.quantity_change),
        0
    ) * pv.unit_cost AS stock_cost_value,

    COALESCE(
        SUM(im.quantity_change),
        0
    ) * pv.retail_price AS stock_retail_value,

    MAX(im.movement_date) AS last_inventory_movement_at

FROM commerce.product_variants pv
JOIN commerce.products p
    ON p.product_id = pv.product_id
JOIN commerce.categories c
    ON c.category_id = p.category_id
LEFT JOIN commerce.inventory_movements im
    ON im.variant_id = pv.variant_id

GROUP BY
    pv.variant_id,
    pv.sku,
    p.product_id,
    p.product_name,
    p.brand,
    c.category_id,
    c.category_name,
    pv.colour,
    pv.size,
    pv.unit_cost,
    pv.retail_price,
    pv.active,
    p.active;


COMMENT ON VIEW commerce.current_inventory IS
    'Current stock and inventory valuation calculated from immutable inventory movements.';


-- ============================================================
-- 2. ORDER FINANCIALS
-- ============================================================

CREATE VIEW commerce.order_financials AS
WITH item_totals AS (
    SELECT
        oi.order_id,

        SUM(oi.quantity) AS total_units,

        SUM(oi.line_revenue) AS gross_item_revenue,
        SUM(oi.line_discount) AS item_discount_amount,
        SUM(oi.line_cost) AS total_cost,
        SUM(oi.line_profit) AS gross_profit_before_refunds

    FROM commerce.order_items oi
    GROUP BY oi.order_id
),

refund_totals AS (
    SELECT
        r.order_id,

        SUM(
            CASE
                WHEN r.refund_status = 'PROCESSED'
                THEN r.refund_amount
                ELSE 0
            END
        ) AS processed_refund_amount,

        COUNT(*) FILTER (
            WHERE r.refund_status = 'PROCESSED'
        ) AS processed_refund_count

    FROM commerce.refunds r
    GROUP BY r.order_id
),

payment_totals AS (
    SELECT
        p.order_id,

        SUM(
            CASE
                WHEN p.payment_status IN (
                    'SUCCESSFUL',
                    'PARTIALLY_REFUNDED',
                    'REFUNDED'
                )
                THEN p.amount
                ELSE 0
            END
        ) AS successful_payment_amount,

        COUNT(*) FILTER (
            WHERE p.payment_status = 'FAILED'
        ) AS failed_payment_attempts

    FROM commerce.payments p
    GROUP BY p.order_id
)

SELECT
    o.order_id,
    o.order_number,
    o.customer_id,

    o.order_date,
    o.status,
    o.sales_channel,

    o.shipping_city,
    o.shipping_region,
    o.shipping_country,

    o.subtotal,
    o.discount_amount AS order_discount_amount,
    o.shipping_cost,
    o.tax_amount,
    o.total_amount,
    o.currency,

    COALESCE(it.total_units, 0) AS total_units,
    COALESCE(it.gross_item_revenue, 0) AS gross_item_revenue,
    COALESCE(it.item_discount_amount, 0) AS item_discount_amount,
    COALESCE(it.total_cost, 0) AS total_cost,
    COALESCE(it.gross_profit_before_refunds, 0)
        AS gross_profit_before_refunds,

    COALESCE(rt.processed_refund_amount, 0)
        AS processed_refund_amount,

    COALESCE(rt.processed_refund_count, 0)
        AS processed_refund_count,

    COALESCE(pt.successful_payment_amount, 0)
        AS successful_payment_amount,

    COALESCE(pt.failed_payment_attempts, 0)
        AS failed_payment_attempts,

    o.total_amount
        - COALESCE(rt.processed_refund_amount, 0)
        AS net_revenue_after_refunds,

    COALESCE(it.gross_profit_before_refunds, 0)
        - COALESCE(rt.processed_refund_amount, 0)
        AS estimated_profit_after_refunds,

    CASE
        WHEN o.total_amount > 0
        THEN ROUND(
            (
                (
                    COALESCE(it.gross_profit_before_refunds, 0)
                    - COALESCE(rt.processed_refund_amount, 0)
                )
                / o.total_amount
            ) * 100,
            2
        )
        ELSE 0
    END AS estimated_profit_margin_percentage

FROM commerce.orders o
LEFT JOIN item_totals it
    ON it.order_id = o.order_id
LEFT JOIN refund_totals rt
    ON rt.order_id = o.order_id
LEFT JOIN payment_totals pt
    ON pt.order_id = o.order_id;


COMMENT ON VIEW commerce.order_financials IS
    'Order-level revenue, cost, payment, refund and estimated profit metrics.';


-- ============================================================
-- 3. CUSTOMER LIFETIME METRICS
-- ============================================================

CREATE VIEW commerce.customer_lifetime_metrics AS
WITH customer_orders AS (
    SELECT
        o.customer_id,

        COUNT(*) FILTER (
            WHERE o.status <> 'CANCELLED'
        ) AS total_orders,

        COUNT(*) FILTER (
            WHERE o.status = 'DELIVERED'
        ) AS delivered_orders,

        COUNT(*) FILTER (
            WHERE o.status IN (
                'PARTIALLY_REFUNDED',
                'REFUNDED'
            )
        ) AS refunded_orders,

        MIN(o.order_date) FILTER (
            WHERE o.status <> 'CANCELLED'
        ) AS first_order_date,

        MAX(o.order_date) FILTER (
            WHERE o.status <> 'CANCELLED'
        ) AS last_order_date,

        SUM(
            CASE
                WHEN o.status <> 'CANCELLED'
                THEN ofn.total_units
                ELSE 0
            END
        ) AS lifetime_units,

        SUM(
            CASE
                WHEN o.status <> 'CANCELLED'
                THEN ofn.total_amount
                ELSE 0
            END
        ) AS gross_lifetime_revenue,

        SUM(
            CASE
                WHEN o.status <> 'CANCELLED'
                THEN ofn.processed_refund_amount
                ELSE 0
            END
        ) AS lifetime_refund_amount,

        SUM(
            CASE
                WHEN o.status <> 'CANCELLED'
                THEN ofn.net_revenue_after_refunds
                ELSE 0
            END
        ) AS net_lifetime_revenue,

        SUM(
            CASE
                WHEN o.status <> 'CANCELLED'
                THEN ofn.estimated_profit_after_refunds
                ELSE 0
            END
        ) AS estimated_lifetime_profit

    FROM commerce.orders o
    JOIN commerce.order_financials ofn
        ON ofn.order_id = o.order_id
    GROUP BY o.customer_id
),

segment_list AS (
    SELECT
        csm.customer_id,
        STRING_AGG(
            cs.segment_name,
            ', '
            ORDER BY cs.segment_name
        ) AS active_segments

    FROM commerce.customer_segment_memberships csm
    JOIN commerce.customer_segments cs
        ON cs.segment_id = csm.segment_id
    WHERE csm.removed_at IS NULL
    GROUP BY csm.customer_id
)

SELECT
    c.customer_id,
    c.first_name,
    c.last_name,
    CONCAT(c.first_name, ' ', c.last_name) AS customer_name,

    c.email,
    c.phone,
    c.city,
    c.region,
    c.country,

    c.acquisition_channel,
    c.marketing_consent,
    c.created_at AS customer_created_at,

    COALESCE(co.total_orders, 0) AS total_orders,
    COALESCE(co.delivered_orders, 0) AS delivered_orders,
    COALESCE(co.refunded_orders, 0) AS refunded_orders,

    co.first_order_date,
    co.last_order_date,

    COALESCE(co.lifetime_units, 0) AS lifetime_units,
    COALESCE(co.gross_lifetime_revenue, 0)
        AS gross_lifetime_revenue,
    COALESCE(co.lifetime_refund_amount, 0)
        AS lifetime_refund_amount,
    COALESCE(co.net_lifetime_revenue, 0)
        AS net_lifetime_revenue,
    COALESCE(co.estimated_lifetime_profit, 0)
        AS estimated_lifetime_profit,

    CASE
        WHEN COALESCE(co.total_orders, 0) > 0
        THEN ROUND(
            co.net_lifetime_revenue
            / co.total_orders,
            2
        )
        ELSE 0
    END AS average_order_value,

    CASE
        WHEN co.last_order_date IS NOT NULL
        THEN CURRENT_DATE - co.last_order_date::DATE
        ELSE NULL
    END AS days_since_last_order,

    CASE
        WHEN COALESCE(co.total_orders, 0) = 0
            THEN 'PROSPECT'

        WHEN co.last_order_date >= CURRENT_DATE - INTERVAL '90 days'
            THEN 'ACTIVE'

        WHEN co.last_order_date >= CURRENT_DATE - INTERVAL '180 days'
            THEN 'AT_RISK'

        ELSE 'INACTIVE'
    END AS customer_activity_status,

    CASE
        WHEN COALESCE(co.net_lifetime_revenue, 0) >= 1000
            THEN 'VIP'

        WHEN COALESCE(co.net_lifetime_revenue, 0) >= 500
            THEN 'HIGH_VALUE'

        WHEN COALESCE(co.net_lifetime_revenue, 0) >= 150
            THEN 'REGULAR'

        WHEN COALESCE(co.net_lifetime_revenue, 0) > 0
            THEN 'LOW_VALUE'

        ELSE 'NO_PURCHASE'
    END AS customer_value_tier,

    sl.active_segments

FROM commerce.customers c
LEFT JOIN customer_orders co
    ON co.customer_id = c.customer_id
LEFT JOIN segment_list sl
    ON sl.customer_id = c.customer_id;


COMMENT ON VIEW commerce.customer_lifetime_metrics IS
    'Customer lifetime value, purchase activity, segmentation and retention metrics.';


-- ============================================================
-- 4. MONTHLY SALES METRICS
-- ============================================================

CREATE VIEW commerce.monthly_sales_metrics AS
SELECT
    DATE_TRUNC(
        'month',
        ofn.order_date
    )::DATE AS sales_month,

    COUNT(*) FILTER (
        WHERE ofn.status <> 'CANCELLED'
    ) AS total_orders,

    COUNT(DISTINCT ofn.customer_id) FILTER (
        WHERE ofn.status <> 'CANCELLED'
    ) AS unique_customers,

    SUM(
        CASE
            WHEN ofn.status <> 'CANCELLED'
            THEN ofn.total_units
            ELSE 0
        END
    ) AS total_units_sold,

    SUM(
        CASE
            WHEN ofn.status <> 'CANCELLED'
            THEN ofn.total_amount
            ELSE 0
        END
    ) AS gross_revenue,

    SUM(
        CASE
            WHEN ofn.status <> 'CANCELLED'
            THEN ofn.processed_refund_amount
            ELSE 0
        END
    ) AS refund_amount,

    SUM(
        CASE
            WHEN ofn.status <> 'CANCELLED'
            THEN ofn.net_revenue_after_refunds
            ELSE 0
        END
    ) AS net_revenue,

    SUM(
        CASE
            WHEN ofn.status <> 'CANCELLED'
            THEN ofn.total_cost
            ELSE 0
        END
    ) AS total_cost,

    SUM(
        CASE
            WHEN ofn.status <> 'CANCELLED'
            THEN ofn.estimated_profit_after_refunds
            ELSE 0
        END
    ) AS estimated_profit,

    CASE
        WHEN COUNT(*) FILTER (
            WHERE ofn.status <> 'CANCELLED'
        ) > 0
        THEN ROUND(
            SUM(
                CASE
                    WHEN ofn.status <> 'CANCELLED'
                    THEN ofn.net_revenue_after_refunds
                    ELSE 0
                END
            )
            /
            COUNT(*) FILTER (
                WHERE ofn.status <> 'CANCELLED'
            ),
            2
        )
        ELSE 0
    END AS average_order_value,

    CASE
        WHEN SUM(
            CASE
                WHEN ofn.status <> 'CANCELLED'
                THEN ofn.net_revenue_after_refunds
                ELSE 0
            END
        ) > 0
        THEN ROUND(
            (
                SUM(
                    CASE
                        WHEN ofn.status <> 'CANCELLED'
                        THEN ofn.estimated_profit_after_refunds
                        ELSE 0
                    END
                )
                /
                SUM(
                    CASE
                        WHEN ofn.status <> 'CANCELLED'
                        THEN ofn.net_revenue_after_refunds
                        ELSE 0
                    END
                )
            ) * 100,
            2
        )
        ELSE 0
    END AS estimated_profit_margin_percentage

FROM commerce.order_financials ofn

GROUP BY
    DATE_TRUNC(
        'month',
        ofn.order_date
    )::DATE;


COMMENT ON VIEW commerce.monthly_sales_metrics IS
    'Monthly order volume, revenue, refunds, costs, profit and customer metrics.';


-- ============================================================
-- 5. PRODUCT PERFORMANCE
-- ============================================================

CREATE VIEW commerce.product_performance AS
WITH sales_metrics AS (
    SELECT
        pv.variant_id,

        COUNT(DISTINCT oi.order_id) AS total_orders,

        SUM(oi.quantity) AS units_sold,

        SUM(oi.line_revenue) AS gross_revenue,

        SUM(oi.line_cost) AS total_cost,

        SUM(oi.line_profit) AS gross_profit,

        MAX(o.order_date) AS last_sold_at

    FROM commerce.order_items oi
    JOIN commerce.orders o
        ON o.order_id = oi.order_id
    JOIN commerce.product_variants pv
        ON pv.variant_id = oi.variant_id

    WHERE o.status <> 'CANCELLED'

    GROUP BY pv.variant_id
),

refund_metrics_by_variant AS (
    SELECT
        oi.variant_id,

        SUM(
            CASE
                WHEN r.refund_status = 'PROCESSED'
                THEN ri.quantity
                ELSE 0
            END
        ) AS units_refunded,

        SUM(
            CASE
                WHEN r.refund_status = 'PROCESSED'
                THEN ri.refund_amount
                ELSE 0
            END
        ) AS refund_amount

    FROM commerce.refund_items ri
    JOIN commerce.refunds r
        ON r.refund_id = ri.refund_id
    JOIN commerce.order_items oi
        ON oi.order_item_id = ri.order_item_id

    GROUP BY oi.variant_id
)

SELECT
    pv.variant_id,
    pv.sku,

    p.product_id,
    p.product_name,
    p.brand,

    c.category_id,
    c.category_name,

    pv.colour,
    pv.size,

    pv.unit_cost,
    pv.retail_price,

    pv.active AS variant_active,
    p.active AS product_active,

    COALESCE(sm.total_orders, 0) AS total_orders,
    COALESCE(sm.units_sold, 0) AS units_sold,
    COALESCE(sm.gross_revenue, 0) AS gross_revenue,
    COALESCE(sm.total_cost, 0) AS total_cost,
    COALESCE(sm.gross_profit, 0) AS gross_profit,

    COALESCE(rm.units_refunded, 0) AS units_refunded,
    COALESCE(rm.refund_amount, 0) AS refund_amount,

    COALESCE(sm.gross_revenue, 0)
        - COALESCE(rm.refund_amount, 0)
        AS net_revenue,

    COALESCE(sm.gross_profit, 0)
        - COALESCE(rm.refund_amount, 0)
        AS estimated_net_profit,

    ci.current_stock,
    ci.stock_cost_value,
    ci.stock_retail_value,

    sm.last_sold_at,

    CASE
        WHEN COALESCE(sm.units_sold, 0) > 0
        THEN ROUND(
            (
                COALESCE(rm.units_refunded, 0)::NUMERIC
                / sm.units_sold
            ) * 100,
            2
        )
        ELSE 0
    END AS unit_refund_rate_percentage,

    CASE
        WHEN COALESCE(sm.gross_revenue, 0) > 0
        THEN ROUND(
            (
                (
                    COALESCE(sm.gross_profit, 0)
                    - COALESCE(rm.refund_amount, 0)
                )
                / sm.gross_revenue
            ) * 100,
            2
        )
        ELSE 0
    END AS estimated_profit_margin_percentage

FROM commerce.product_variants pv
JOIN commerce.products p
    ON p.product_id = pv.product_id
JOIN commerce.categories c
    ON c.category_id = p.category_id
LEFT JOIN sales_metrics sm
    ON sm.variant_id = pv.variant_id
LEFT JOIN refund_metrics_by_variant rm
    ON rm.variant_id = pv.variant_id
LEFT JOIN commerce.current_inventory ci
    ON ci.variant_id = pv.variant_id;


COMMENT ON VIEW commerce.product_performance IS
    'Variant-level sales, profitability, refunds and current inventory metrics.';


-- ============================================================
-- 6. REFUND METRICS
-- ============================================================

CREATE VIEW commerce.refund_metrics AS
SELECT
    DATE_TRUNC(
        'month',
        r.refund_date
    )::DATE AS refund_month,

    r.refund_reason,
    r.refund_status,

    COUNT(DISTINCT r.refund_id) AS refund_count,
    COUNT(DISTINCT r.order_id) AS affected_orders,

    COALESCE(
        SUM(ri.quantity),
        0
    ) AS units_refunded,

    SUM(r.refund_amount) AS refund_amount,

    COUNT(*) FILTER (
        WHERE ri.return_to_stock = TRUE
    ) AS refund_items_returned_to_stock,

    COUNT(*) FILTER (
        WHERE ri.return_to_stock = FALSE
    ) AS refund_items_not_returned_to_stock

FROM commerce.refunds r
LEFT JOIN commerce.refund_items ri
    ON ri.refund_id = r.refund_id

GROUP BY
    DATE_TRUNC(
        'month',
        r.refund_date
    )::DATE,
    r.refund_reason,
    r.refund_status;


COMMENT ON VIEW commerce.refund_metrics IS
    'Monthly refund metrics grouped by refund reason and processing status.';


-- ============================================================
-- 7. INVENTORY VELOCITY
-- ============================================================

CREATE VIEW commerce.inventory_velocity AS
WITH recent_sales AS (
    SELECT
        oi.variant_id,

        SUM(
            CASE
                WHEN o.order_date >= CURRENT_DATE - INTERVAL '30 days'
                AND o.status <> 'CANCELLED'
                THEN oi.quantity
                ELSE 0
            END
        ) AS units_sold_last_30_days,

        SUM(
            CASE
                WHEN o.order_date >= CURRENT_DATE - INTERVAL '90 days'
                AND o.status <> 'CANCELLED'
                THEN oi.quantity
                ELSE 0
            END
        ) AS units_sold_last_90_days,

        MAX(o.order_date) FILTER (
            WHERE o.status <> 'CANCELLED'
        ) AS last_sold_at

    FROM commerce.order_items oi
    JOIN commerce.orders o
        ON o.order_id = oi.order_id

    GROUP BY oi.variant_id
)

SELECT
    ci.variant_id,
    ci.sku,

    ci.product_id,
    ci.product_name,
    ci.brand,
    ci.category_name,

    ci.colour,
    ci.size,

    ci.current_stock,

    COALESCE(rs.units_sold_last_30_days, 0)
        AS units_sold_last_30_days,

    COALESCE(rs.units_sold_last_90_days, 0)
        AS units_sold_last_90_days,

    ROUND(
        COALESCE(rs.units_sold_last_30_days, 0)::NUMERIC
        / 30,
        2
    ) AS average_daily_units_sold_30_days,

    CASE
        WHEN COALESCE(rs.units_sold_last_30_days, 0) > 0
        THEN ROUND(
            ci.current_stock
            /
            (
                rs.units_sold_last_30_days::NUMERIC
                / 30
            ),
            2
        )
        ELSE NULL
    END AS estimated_days_of_stock_remaining,

    CASE
        WHEN ci.current_stock <= 0
            THEN 'OUT_OF_STOCK'

        WHEN COALESCE(rs.units_sold_last_30_days, 0) = 0
            THEN 'NO_RECENT_DEMAND'

        WHEN (
            ci.current_stock
            /
            NULLIF(
                rs.units_sold_last_30_days::NUMERIC / 30,
                0
            )
        ) <= 14
            THEN 'CRITICAL'

        WHEN (
            ci.current_stock
            /
            NULLIF(
                rs.units_sold_last_30_days::NUMERIC / 30,
                0
            )
        ) <= 30
            THEN 'LOW_STOCK'

        WHEN (
            ci.current_stock
            /
            NULLIF(
                rs.units_sold_last_30_days::NUMERIC / 30,
                0
            )
        ) >= 180
            THEN 'OVERSTOCKED'

        ELSE 'HEALTHY'
    END AS stock_status,

    rs.last_sold_at,
    ci.last_inventory_movement_at

FROM commerce.current_inventory ci
LEFT JOIN recent_sales rs
    ON rs.variant_id = ci.variant_id;


COMMENT ON VIEW commerce.inventory_velocity IS
    'Recent product demand, estimated stock coverage and inventory risk status.';


COMMIT;