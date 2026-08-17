"""
Live regression check for understand_and_generate_sql()'s SQL quality.

This is NOT run as part of the normal suite: it calls the real Gemini API
(spends real quota) and needs a live database (get_schema_description()
introspects commerce.*). It exists to answer one question -- "did merging
understand_question() + generate_sql() into a single prompt materially
reduce SQL correctness?" -- by exercising a small set of representative
question categories and checking each result against a structural
expectation for that category (not full data validation).

Run explicitly, opt-in only:

    RUN_LIVE_LLM_REGRESSION=1 ./.venv/bin/python -m pytest tests/test_llm_regression.py -v

Every test is skipped unless RUN_LIVE_LLM_REGRESSION=1 is set, so it never
runs in CI or as a side effect of `pytest`/`pytest tests/`.
"""

import os
import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import db  # noqa: E402
import llm  # noqa: E402
import sql_validator  # noqa: E402


RUN_LIVE = os.getenv("RUN_LIVE_LLM_REGRESSION") == "1"

pytestmark = pytest.mark.skipif(
    not RUN_LIVE,
    reason=(
        "Live regression: calls the real Gemini API and a live database. "
        "Set RUN_LIVE_LLM_REGRESSION=1 to run."
    ),
)


# One representative question per category the merged prompt must still
# handle correctly. Each entry's "check" receives (understanding, sql)
# and asserts a structural property -- not exact SQL text, since the
# model's exact phrasing can vary run to run.
REGRESSION_CASES = [
    (
        "simple_count",
        "How many orders have we received in total?",
        lambda understanding, sql: "COUNT(" in sql.upper(),
    ),
    (
        "aggregation",
        "What is our total revenue this year?",
        lambda understanding, sql: any(
            function in sql.upper() for function in ("SUM(", "COUNT(", "AVG(")
        ),
    ),
    (
        "ranking_top_n",
        "Who are our top 5 customers by revenue?",
        lambda understanding, sql: "ORDER BY" in sql.upper()
        and "LIMIT" in sql.upper(),
    ),
    (
        "date_filtering",
        "How much revenue did we generate last month?",
        lambda understanding, sql: understanding.get("time_filter"),
    ),
    (
        "grouping",
        "What is the total revenue by product category?",
        lambda understanding, sql: "GROUP BY" in sql.upper(),
    ),
    (
        "customer_query",
        "How many customers did we acquire through each channel?",
        lambda understanding, sql: any(
            "customer" in str(entity).lower()
            for entity in understanding.get("entities", [])
        ),
    ),
    (
        "product_query",
        "Which products have the highest retail price?",
        lambda understanding, sql: any(
            "product" in str(entity).lower()
            for entity in understanding.get("entities", [])
        ),
    ),
    (
        "revenue_query",
        "What is our average order value?",
        lambda understanding, sql: "AVG(" in sql.upper()
        or "avg" in understanding.get("aggregation", "").lower(),
    ),
    (
        "ambiguous_question",
        "How are sales doing?",
        lambda understanding, sql: bool(understanding.get("ambiguity"))
        or bool(understanding.get("assumptions")),
    ),
    (
        "invalid_unsupported_question",
        "What is the weather forecast for tomorrow?",
        lambda understanding, sql: "QUESTION_CANNOT_BE_ANSWERED_FROM_AVAILABLE_SCHEMA"
        in sql,
    ),
]


@pytest.fixture(scope="module")
def schema() -> str:
    return db.get_schema_description()


@pytest.mark.parametrize(
    "category,question,check",
    REGRESSION_CASES,
    ids=[case[0] for case in REGRESSION_CASES],
)
def test_understand_and_generate_sql_regression(category, question, check, schema):
    understanding, sql = llm.understand_and_generate_sql(question, schema)

    # Every generated query must still pass the same safety validator the
    # real pipeline uses, regardless of category.
    sql_validator.validate_select_only(sql)

    assert check(understanding, sql), (
        f"[{category}] structural expectation failed for question "
        f"{question!r}.\nunderstanding={understanding}\nsql={sql}"
    )
