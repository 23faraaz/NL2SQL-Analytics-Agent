import pandas as pd

ORDER_ITEM_FINAL_COLUMNS = [
    "order_item_id",
    "order_id",
    "variant_id",
    "quantity",
    "unit_sale_price",
    "unit_cost_at_sale",
    "line_revenue",
    "line_cost",
    "line_profit",
]

# DERIVED, not SYNTHETIC: variant_id is a deterministic selection among
# the real product's generated variants (no new random fabrication at
# this step); unit_cost_at_sale/line_cost/line_profit are computed
# directly from the S4b-generated variant's unit_cost.
DERIVED_COLUMNS = ["variant_id", "unit_cost_at_sale", "line_cost", "line_profit"]


def augment_order_items(
    order_items: pd.DataFrame,
    product_variants: pd.DataFrame,
) -> pd.DataFrame:
    """
    Resolve each real order item's product_id to one of that product's
    S4b-generated variants, and derive the cost-side fields commerce
    .order_items requires.

    commerce.order_items has UNIQUE(order_id, variant_id) -- one row per
    variant per order, with quantity capturing repeat units, matching
    real retail order-line semantics. Real Olist order_items instead
    has one row per unit (no quantity column), so a real order can have
    two or more separate rows for the same product. Every row for a
    given (order_id, product_id) is assigned the SAME variant
    (deterministic, based on order_id and product_id, not randomly) and
    then consolidated into a single order_items row, with quantity equal
    to the real row count and line_revenue/line_cost summed across them
    -- this is a genuine, deliberate re-shaping of real data to fit the
    schema's own line-item definition, not a data-loss shortcut: no
    revenue, cost, or quantity is dropped, only reshaped.

    unit_cost_at_sale is a direct copy of the chosen variant's real
    generated unit_cost; line_cost and line_profit are computed from it.
    line_discount is left unset (schema default 0 -- Olist has no
    per-item discount concept).
    """

    required_item_columns = {
        "order_item_id",
        "order_id",
        "product_id",
        "quantity",
        "unit_sale_price",
        "line_revenue",
    }
    missing_item_columns = required_item_columns - set(order_items.columns)

    if missing_item_columns:
        raise ValueError(
            "Processed order items are missing required columns: "
            f"{sorted(missing_item_columns)}"
        )

    required_variant_columns = {"variant_id", "product_id", "unit_cost"}
    missing_variant_columns = required_variant_columns - set(product_variants.columns)

    if missing_variant_columns:
        raise ValueError(
            "Product variants are missing required columns: "
            f"{sorted(missing_variant_columns)}"
        )

    variants_by_product: dict[int, list[dict]] = {}

    for _, variant in product_variants.iterrows():
        variants_by_product.setdefault(
            int(variant["product_id"]),
            [],
        ).append(
            {
                "variant_id": int(variant["variant_id"]),
                "unit_cost": float(variant["unit_cost"]),
            }
        )

    working = order_items.copy()

    resolved_variant_ids: list[int] = []

    for _, item in working.iterrows():
        order_id = int(item["order_id"])
        product_id = int(item["product_id"])
        candidates = variants_by_product.get(product_id)

        if not candidates:
            raise ValueError(
                f"No generated variants found for product_id={product_id}; "
                "every product must have at least one variant before "
                "order_items can be resolved"
            )

        # Every real row for this (order_id, product_id) resolves to the
        # same variant, so consolidation below produces exactly one
        # commerce.order_items row per (order_id, variant_id).
        chosen = candidates[(order_id + product_id) % len(candidates)]
        resolved_variant_ids.append(chosen["variant_id"])

    working["variant_id"] = resolved_variant_ids

    consolidated = (
        working.groupby(["order_id", "variant_id"])
        .agg(
            quantity=("quantity", "sum"),
            unit_sale_price=("unit_sale_price", "mean"),
            line_revenue=("line_revenue", "sum"),
        )
        .reset_index()
    )

    unit_cost_by_variant = {
        variant["variant_id"]: variant["unit_cost"]
        for variants in variants_by_product.values()
        for variant in variants
    }

    consolidated["unit_cost_at_sale"] = (
        consolidated["variant_id"].map(unit_cost_by_variant).round(2)
    )

    consolidated["unit_sale_price"] = consolidated["unit_sale_price"].round(2)

    consolidated["line_cost"] = (
        consolidated["quantity"] * consolidated["unit_cost_at_sale"]
    ).round(2)

    consolidated["line_profit"] = (
        consolidated["line_revenue"] - consolidated["line_cost"]
    ).round(2)

    consolidated = consolidated.sort_values(["order_id", "variant_id"]).reset_index(
        drop=True
    )

    consolidated.insert(
        0,
        "order_item_id",
        range(1, len(consolidated) + 1),
    )

    if consolidated[["order_id", "variant_id"]].duplicated().any():
        raise ValueError(
            "Consolidated order_items still contains duplicate "
            "(order_id, variant_id) pairs"
        )

    return consolidated[ORDER_ITEM_FINAL_COLUMNS]
