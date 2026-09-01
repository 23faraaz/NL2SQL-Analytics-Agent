"""
Conversational sales intelligence interface.

The application preserves the NL2SQL pipeline while presenting results in
a business-focused order:

1. Direct answer
2. KPI or chart
3. Grounded insight
4. Interactive table
5. Suggested follow-up actions
6. Collapsed technical details
"""

import logging
import re
import sys
from datetime import datetime
from typing import Any

import streamlit as st

import db
import llm
import sql_validator
from components.charts import format_value, render_chart
from components.metrics import render_result_summary
from services import customer_service, product_service, revenue_service, voice_service
from services.analytics_service import execute_analytics_query
from services.chart_service import format_label, recommend_chart

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    stream=sys.stdout,
)

logger = logging.getLogger(__name__)


def escape_markdown_math_delimiters(text: str) -> str:
    """
    Streamlit's markdown renderer treats a pair of literal $ characters as
    LaTeX math delimiters. LLM-generated explanations routinely contain
    multiple currency figures such as "$9,582.75", so without escaping,
    any two dollar signs get read as "start/end of a math expression" --
    everything between them (spaces, **bold** markers included) is
    swallowed into math typesetting, which ignores literal whitespace and
    renders words with no spaces between them. A backslash-escaped dollar
    sign displays as a plain $ character without triggering math mode.
    """

    return text.replace("$", r"\$")


st.set_page_config(
    page_title="Commerce Intelligence",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


# Custom polish beyond what .streamlit/config.toml's [theme] table can
# reach. Every selector below was confirmed against this installed
# Streamlit version's actual compiled frontend bundle (grepped for the
# literal data-testid strings) before being used here, not guessed --
# an unmatched selector would just silently do nothing, but a wrong
# guess is still wasted, unverifiable styling.
st.markdown(
    """
    <style>
    .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
    }

    [data-testid="stSidebar"] h2 {
        font-weight: 700;
        letter-spacing: -0.01em;
    }

    [data-testid="stChatMessage"] {
        border-radius: 1rem;
        padding: 0.5rem 0.75rem;
        margin-bottom: 0.5rem;
    }

    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
        background-color: #F5F6FA;
    }

    [data-testid^="stBaseButton"] {
        transition: transform 0.08s ease, box-shadow 0.08s ease;
    }

    [data-testid^="stBaseButton"]:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 10px rgba(79, 70, 229, 0.15);
    }

    div[data-testid="stMetric"] {
        background-color: #FFFFFF;
        border: 1px solid #E4E6F0;
        border-radius: 0.75rem;
        padding: 1rem 1.25rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


SUGGESTED_QUESTIONS = [
    "How much revenue did we generate this month?",
    "Who are our top ten customers by revenue?",
    "Compare sales this month with last month.",
    "Which products generated the most revenue?",
]


@st.cache_data(ttl=300)
def load_schema() -> str:
    return db.get_schema_description()


def initialise_session_state() -> None:
    if "messages" not in st.session_state:
        st.session_state.messages = []

    if "pending_question" not in st.session_state:
        st.session_state.pending_question = None

    if "processed_audio_id" not in st.session_state:
        st.session_state.processed_audio_id = None

    if "view" not in st.session_state:
        st.session_state.view = "assistant"


def is_number_only(question: str) -> bool:
    cleaned = question.strip().replace(",", "").replace("£", "").replace("$", "")

    return bool(re.fullmatch(r"-?\d+(\.\d+)?", cleaned))


def validate_question(question: str) -> tuple[bool, str | None]:
    if not question.strip():
        return False, "Enter a question about your sales data."

    if is_number_only(question):
        return (
            False,
            "What would you like to analyse about this number? "
            "For example: revenue above £20,000, orders worth £20,000, "
            "or progress towards a £20,000 target.",
        )

    if len(question.split()) < 3:
        return (
            False,
            "Please include the sales metric, customer, product or period "
            "you want to analyse.",
        )

    return True, None


# Matches the sentinel literal embedded in prompts.py's
# UNDERSTAND_AND_GENERATE_SQL_PROMPT / SQL_REGENERATION_PROMPT. Detecting
# it here lets execute_pipeline() skip explain_results() entirely for
# this case -- deterministic, no extra LLM call, and a chance to say
# something more specific than the LLM's own generic phrasing.
_UNANSWERABLE_SENTINEL = "QUESTION_CANNOT_BE_ANSWERED_FROM_AVAILABLE_SCHEMA"


def _is_unanswerable_result(safe_sql: str) -> bool:
    return _UNANSWERABLE_SENTINEL in safe_sql


def _format_month_year(iso_timestamp: str) -> str | None:
    try:
        return datetime.fromisoformat(iso_timestamp).strftime("%B %Y")
    except (TypeError, ValueError):
        return None


def _build_unanswerable_explanation() -> str:
    """
    Deterministic fallback for the QUESTION_CANNOT_BE_ANSWERED sentinel.

    The single most common real cause (verified against this app's real
    dataset) is a question about a date outside the data's actual range,
    so the message states that range explicitly when available, instead
    of a generic "cannot be answered" with no actionable detail.
    """

    try:
        metadata = db.get_database_metadata()
    except db.DatabaseError:
        metadata = {}

    earliest_label = _format_month_year(metadata.get("earliest_order", ""))
    latest_label = _format_month_year(metadata.get("latest_order", ""))

    if earliest_label and latest_label:
        return (
            "This question cannot be answered from the available data. "
            f"The dataset only covers **{earliest_label}** to "
            f"**{latest_label}** -- if your question was about a period "
            "outside that range, that's why. Otherwise, try rephrasing "
            "using only customers, orders, products, or payments data."
        )

    return (
        "This question cannot be answered from the available data. "
        "Try rephrasing using only customers, orders, products, or "
        "payments data."
    )


def is_single_value_metric_result(
    dataframe,
    recommendation,
) -> bool:
    """
    True only when the result is genuinely a single value: exactly one
    row, exactly one column in the whole result, and that column is the
    numeric column recommend_chart() identified.

    recommend_chart()'s own "metric" classification only requires one row
    and exactly one *numeric* column -- a one-row result with an extra
    non-numeric column (for example product_name alongside a total, from
    a "which product has the highest revenue" question) also satisfies
    that check. Rendering only the numeric value in that case would
    silently drop the non-numeric column from the answer, so this
    stricter check additionally requires the result to have no other
    columns before the deterministic (non-LLM) explanation path is used.
    """

    return (
        recommendation.chart_type == "metric"
        and len(dataframe) == 1
        and len(dataframe.columns) == 1
    )


def execute_pipeline(
    question: str,
    schema: str,
) -> dict[str, Any] | None:
    """
    Run the NL2SQL pipeline with one automatic SQL correction attempt.

    Every generated query, including regenerated SQL, must pass the same
    safety validator before it can be executed.
    """

    max_sql_attempts = 2

    try:
        understanding, raw_sql = llm.understand_and_generate_sql(
            question,
            schema,
        )
    except llm.LLMError as exc:
        st.error(
            "The AI service is temporarily unavailable. " "Please try again shortly."
        )
        logger.exception("Question understanding and SQL generation failed: %s", exc)
        return None

    sql_attempts: list[dict[str, Any]] = []
    safe_sql: str | None = None
    query_result = None

    for attempt_number in range(1, max_sql_attempts + 1):
        try:
            safe_sql = sql_validator.validate_select_only(raw_sql)

        except sql_validator.SQLValidationError as exc:
            logger.warning(
                "SQL validation failed on attempt %d/%d: %s",
                attempt_number,
                max_sql_attempts,
                exc,
            )

            sql_attempts.append(
                {
                    "attempt": attempt_number,
                    "sql": raw_sql,
                    "failure_type": "validation_error",
                    "error": str(exc),
                }
            )

            if attempt_number >= max_sql_attempts:
                st.error(
                    "The generated query failed the safety checks "
                    "after one correction attempt and was not run."
                )

                with st.expander("Rejected SQL attempts"):
                    for attempt in sql_attempts:
                        st.markdown(f"#### Attempt {attempt['attempt']}")
                        st.code(
                            attempt["sql"],
                            language="sql",
                        )
                        st.caption(attempt["error"])

                return None

            try:
                raw_sql = llm.regenerate_sql(
                    question=question,
                    schema=schema,
                    understanding=understanding,
                    previous_sql=raw_sql,
                    failure_type="validation_error",
                    error_message=str(exc),
                )
            except llm.LLMError as regeneration_error:
                st.error(
                    "The query failed the safety checks and " "could not be corrected."
                )
                logger.exception(
                    "SQL regeneration after validation failure failed: %s",
                    regeneration_error,
                )
                return None

            continue

        try:
            query_result = execute_analytics_query(safe_sql)

        except db.DatabaseError as exc:
            logger.warning(
                "SQL execution failed on attempt %d/%d: %s",
                attempt_number,
                max_sql_attempts,
                exc,
            )

            sql_attempts.append(
                {
                    "attempt": attempt_number,
                    "sql": safe_sql,
                    "failure_type": "database_error",
                    "error": str(exc),
                }
            )

            if attempt_number >= max_sql_attempts:
                st.error(
                    "The database query could not be completed "
                    "after one correction attempt."
                )

                with st.expander("Failed SQL attempts"):
                    for attempt in sql_attempts:
                        st.markdown(f"#### Attempt {attempt['attempt']}")
                        st.code(
                            attempt["sql"],
                            language="sql",
                        )
                        st.caption(attempt["error"])

                return None

            try:
                raw_sql = llm.regenerate_sql(
                    question=question,
                    schema=schema,
                    understanding=understanding,
                    previous_sql=safe_sql,
                    failure_type="database_error",
                    error_message=str(exc),
                )
            except llm.LLMError as regeneration_error:
                st.error(
                    "The database query failed and the AI service "
                    "could not generate a correction."
                )
                logger.exception(
                    "SQL regeneration after database failure failed: %s",
                    regeneration_error,
                )
                return None

            continue

        break

    if safe_sql is None or query_result is None:
        logger.error("Pipeline finished without a validated SQL query or result.")
        st.error("The analysis could not be completed.")
        return None

    recommendation = recommend_chart(query_result.dataframe)

    if _is_unanswerable_result(safe_sql):
        explanation = _build_unanswerable_explanation()
    elif is_single_value_metric_result(query_result.dataframe, recommendation):
        value = query_result.dataframe[recommendation.y_column].iloc[0]
        explanation = (
            f"{format_label(recommendation.y_column)}: "
            f"{format_value(recommendation.y_column, value)}"
        )
    else:
        try:
            explanation = llm.explain_results(
                question,
                safe_sql,
                list(query_result.dataframe.columns),
                list(
                    query_result.dataframe.itertuples(
                        index=False,
                        name=None,
                    )
                ),
            )
        except llm.LLMError as exc:
            if query_result.row_count == 0:
                explanation = "No matching records were found."
            else:
                explanation = f"The query returned {query_result.row_count:,} rows."

            logger.exception("Result explanation failed: %s", exc)

    followups = llm.suggest_followups(
        question,
        understanding,
        SUGGESTED_QUESTIONS,
    )

    return {
        "question": question,
        "understanding": understanding,
        "raw_sql": raw_sql,
        "safe_sql": safe_sql,
        "query_result": query_result,
        "explanation": explanation,
        "followups": followups,
        "sql_attempts": sql_attempts,
        "attempt_count": len(sql_attempts) + 1,
        "regenerated": bool(sql_attempts),
    }


def render_business_answer(result: dict[str, Any]) -> None:
    query_result = result["query_result"]
    dataframe = query_result.dataframe

    st.markdown("### Answer")

    if result.get("regenerated"):
        st.info("The initial query failed and was corrected automatically.")

    if dataframe.empty:
        st.info("The query ran successfully, but no matching records were found.")
    else:
        recommendation = recommend_chart(dataframe)

        render_chart(
            dataframe,
            recommendation,
        )

        st.markdown("### Insight")
        st.write(result["explanation"])

        st.markdown("### Results")

        st.dataframe(
            dataframe,
            use_container_width=True,
            hide_index=True,
        )

        csv_data = dataframe.to_csv(index=False).encode("utf-8")

        st.download_button(
            label="Download CSV",
            data=csv_data,
            file_name="sales-analysis.csv",
            mime="text/csv",
        )

        if query_result.truncated:
            st.warning(
                "The displayed table was limited to the first "
                f"{len(dataframe):,} rows."
            )

    followups = result["followups"]

    if followups:
        st.markdown("### Continue analysing")

        followup_columns = st.columns(min(len(followups), 3))

        for index, followup in enumerate(followups[:3]):
            with followup_columns[index]:
                if st.button(
                    followup,
                    key=f"followup-{index}-{followup}",
                    use_container_width=True,
                ):
                    st.session_state.pending_question = followup
                    st.rerun()

    with st.expander("Technical details"):
        render_result_summary(
            row_count=query_result.row_count,
            execution_ms=query_result.execution_ms,
            truncated=query_result.truncated,
        )

        st.markdown("#### Generated SQL")
        st.code(result["safe_sql"], language="sql")

        if result.get("sql_attempts"):
            st.markdown("#### Correction history")

            for attempt in result["sql_attempts"]:
                st.markdown(
                    f"**Attempt {attempt['attempt']} failed: "
                    f"{attempt['failure_type']}**"
                )
                st.code(
                    attempt["sql"],
                    language="sql",
                )
                st.caption(attempt["error"])

        st.markdown("#### Question understanding")
        st.json(result["understanding"])

        with st.expander("Database schema"):
            st.text(load_schema())


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown("## Commerce Intelligence")
        st.caption("Sales intelligence workspace")

        st.markdown("---")

        st.markdown("### Navigation")
        st.markdown("**Overview**")

        if st.button(
            "Assistant",
            use_container_width=True,
            type=("primary" if st.session_state.view == "assistant" else "secondary"),
        ):
            st.session_state.view = "assistant"
            st.rerun()

        if st.button(
            "Customers",
            use_container_width=True,
            type=(
                "primary"
                if st.session_state.view == "customer_analytics"
                else "secondary"
            ),
        ):
            st.session_state.view = "customer_analytics"
            st.rerun()

        if st.button(
            "Revenue",
            use_container_width=True,
            type=(
                "primary"
                if st.session_state.view == "revenue_analytics"
                else "secondary"
            ),
        ):
            st.session_state.view = "revenue_analytics"
            st.rerun()

        if st.button(
            "Products",
            use_container_width=True,
            type=(
                "primary"
                if st.session_state.view == "product_analytics"
                else "secondary"
            ),
        ):
            st.session_state.view = "product_analytics"
            st.rerun()

        st.markdown("---")

        with st.expander("Developer mode"):
            st.caption("Schema and SQL details are available inside each response.")


def render_customer_analytics() -> None:
    """
    Customer Analytics MVP: deterministic queries against the existing
    canonical analytics views, never routed through the LLM.
    """

    st.title("Customer Analytics")
    st.caption(
        "Deterministic answers from the commerce schema's analytics "
        "views -- not generated by the assistant."
    )

    st.markdown("### Top 10 customers by lifetime value")

    try:
        top_customers = customer_service.get_top_customers_by_lifetime_value(limit=10)
    except customer_service.CustomerServiceError as exc:
        st.error(str(exc))
        top_customers = None

    if top_customers is not None:
        if top_customers.empty:
            st.info("No customers with orders yet.")
        else:
            st.dataframe(
                top_customers,
                use_container_width=True,
                hide_index=True,
            )

    st.markdown("### Customer value tiers")

    try:
        tier_breakdown = customer_service.get_customer_value_tier_breakdown()
    except customer_service.CustomerServiceError as exc:
        st.error(str(exc))
        tier_breakdown = None

    if tier_breakdown is not None:
        if tier_breakdown.empty:
            st.info("No customer data available.")
        else:
            st.dataframe(
                tier_breakdown,
                use_container_width=True,
                hide_index=True,
            )

    st.markdown("### Look up a customer's order history")

    customer_id_input = st.number_input(
        "Customer ID",
        min_value=1,
        step=1,
        value=1,
    )

    if st.button("Show order history"):
        try:
            history = customer_service.get_customer_order_history(
                int(customer_id_input)
            )
        except customer_service.CustomerServiceError as exc:
            st.warning(str(exc))
        else:
            if history.empty:
                st.info("This customer has no orders yet.")
            else:
                st.dataframe(
                    history,
                    use_container_width=True,
                    hide_index=True,
                )


def render_revenue_analytics() -> None:
    """
    Revenue Analytics: deterministic queries against
    commerce.monthly_sales_metrics, never routed through the LLM. Same
    pattern as render_customer_analytics().
    """

    st.title("Revenue Analytics")
    st.caption(
        "Deterministic answers from the commerce schema's analytics "
        "views -- not generated by the assistant."
    )

    try:
        monthly = revenue_service.get_monthly_sales_metrics()
    except revenue_service.RevenueServiceError as exc:
        st.error(str(exc))
        return

    if monthly.empty:
        st.info("No sales data available.")
        return

    with st.container(border=True):
        kpi_columns = st.columns(3)

        with kpi_columns[0]:
            st.metric(
                "Net revenue (all time)",
                format_value("net_revenue", monthly["net_revenue"].sum()),
            )

        with kpi_columns[1]:
            st.metric(
                "Total orders (all time)",
                format_value("total_orders", int(monthly["total_orders"].sum())),
            )

        with kpi_columns[2]:
            # net_revenue comes back as Decimal (no NUMERIC->float
            # adapter is registered in db.py); total_orders as a numpy
            # int from pandas. Casting both to float before dividing
            # avoids a Decimal/numpy TypeError -- format_value below
            # only needs a plain float/int.
            total_net_revenue = float(monthly["net_revenue"].sum())
            total_orders_sum = int(monthly["total_orders"].sum())
            overall_aov = (
                round(total_net_revenue / total_orders_sum, 2)
                if total_orders_sum
                else 0
            )
            st.metric(
                "Average order value",
                format_value("average_order_value", overall_aov),
            )

    st.markdown("### Net revenue by month")

    with st.container(border=True):
        # net_revenue comes back as Decimal (object dtype); chart
        # widgets need a native numeric dtype.
        chart_data = monthly.set_index("sales_month")[["net_revenue"]].astype(float)
        st.line_chart(chart_data)

    st.markdown("### Monthly detail")

    st.dataframe(
        monthly,
        use_container_width=True,
        hide_index=True,
    )


def render_product_analytics() -> None:
    """
    Product Analytics: deterministic queries against
    commerce.product_performance, never routed through the LLM. Same
    pattern as render_customer_analytics().
    """

    st.title("Product Analytics")
    st.caption(
        "Deterministic answers from the commerce schema's analytics "
        "views -- not generated by the assistant."
    )

    st.markdown("### Top 10 products by net revenue")

    try:
        top_products = product_service.get_top_products_by_revenue(limit=10)
    except product_service.ProductServiceError as exc:
        st.error(str(exc))
        top_products = None

    if top_products is not None:
        if top_products.empty:
            st.info("No product sales yet.")
        else:
            st.dataframe(
                top_products,
                use_container_width=True,
                hide_index=True,
            )

    st.markdown("### Revenue by category")

    try:
        by_category = product_service.get_revenue_by_category()
    except product_service.ProductServiceError as exc:
        st.error(str(exc))
        by_category = None

    if by_category is not None:
        if by_category.empty:
            st.info("No category data available.")
        else:
            with st.container(border=True):
                st.bar_chart(
                    by_category.set_index("category_name")[["net_revenue"]].astype(
                        float
                    )
                )

            st.dataframe(
                by_category,
                use_container_width=True,
                hide_index=True,
            )


def render_welcome_screen() -> None:
    st.title("Commerce Intelligence")
    st.caption(
        "Ask questions about customers, revenue and sales performance "
        "without writing SQL."
    )

    st.markdown("### Ask your sales data")

    suggestion_columns = st.columns(2)

    for index, suggestion in enumerate(SUGGESTED_QUESTIONS):
        with suggestion_columns[index % 2]:
            if st.button(
                suggestion,
                key=f"starter-{index}",
                use_container_width=True,
            ):
                st.session_state.pending_question = suggestion
                st.rerun()


def render_chat_history() -> None:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])


def process_question(question: str, schema: str) -> None:
    valid, validation_message = validate_question(question)

    st.session_state.messages.append(
        {
            "role": "user",
            "content": question,
        }
    )

    with st.chat_message("user"):
        st.markdown(question)

    if not valid:
        response = validation_message or "Please provide more detail."

        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": response,
            }
        )

        with st.chat_message("assistant"):
            st.warning(response)

        return

    with st.chat_message("assistant"):
        with st.spinner("Analysing your sales data..."):
            result = execute_pipeline(question, schema)

        if result is None:
            return

        # Escaped once here so both this turn's render and every future
        # replay via render_chat_history() (which re-renders
        # st.session_state.messages, populated below with this same
        # string) get the safe version -- not just the first display.
        result["explanation"] = escape_markdown_math_delimiters(result["explanation"])

        render_business_answer(result)

        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": result["explanation"],
            }
        )


def main() -> None:
    initialise_session_state()
    render_sidebar()

    if st.session_state.view == "customer_analytics":
        # Deterministic service-layer queries only -- never touches the
        # LLM, so it does not need llm.validate_config() below.
        render_customer_analytics()
        return

    if st.session_state.view == "revenue_analytics":
        render_revenue_analytics()
        return

    if st.session_state.view == "product_analytics":
        render_product_analytics()
        return

    try:
        llm.validate_config()
    except llm.LLMError as exc:
        st.error(f"The assistant is not configured correctly: {exc}")
        st.stop()

    try:
        schema = load_schema()
    except db.DatabaseError as exc:
        st.error(f"Could not connect to the database: {exc}")
        st.stop()

    render_welcome_screen()
    render_chat_history()

    pending_question = st.session_state.pending_question

    if pending_question:
        st.session_state.pending_question = None
        process_question(pending_question, schema)

    audio_file = st.audio_input("Or ask by voice")

    if (
        audio_file is not None
        and audio_file.file_id != st.session_state.processed_audio_id
    ):
        # Marked before the attempt, success or failure: st.audio_input
        # keeps returning the same recording every rerun until the user
        # records a new one, so this must be set regardless of outcome --
        # otherwise an unrelated rerun (any other button on the page)
        # would silently re-attempt transcribing a failed clip forever.
        st.session_state.processed_audio_id = audio_file.file_id

        with st.spinner("Transcribing..."):
            try:
                transcript = voice_service.transcribe_audio(
                    audio_file.getvalue(),
                    filename=audio_file.name,
                )
            except voice_service.VoiceServiceError as exc:
                st.error(str(exc))
                logger.exception("Voice transcription failed: %s", exc)
            else:
                # Routed through the same pending_question mechanism the
                # welcome-screen and follow-up buttons already use, so it
                # gets the same validation and renders in the chat
                # transcript exactly like a typed question -- that chat
                # bubble is the transcription being shown to the user.
                st.session_state.pending_question = transcript
                st.rerun()

    typed_question = st.chat_input("Ask about customers, revenue or sales performance")

    if typed_question:
        process_question(
            typed_question.strip(),
            schema,
        )


if __name__ == "__main__":
    main()
