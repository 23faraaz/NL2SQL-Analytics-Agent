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
from typing import Any

import streamlit as st

import db
import llm
import sql_validator
from components.charts import render_chart
from components.metrics import render_result_summary
from services import customer_service
from services.analytics_service import execute_analytics_query
from services.chart_service import recommend_chart


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    stream=sys.stdout,
)

logger = logging.getLogger(__name__)


st.set_page_config(
    page_title="Commerce Intelligence",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
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

    if "view" not in st.session_state:
        st.session_state.view = "assistant"


def is_number_only(question: str) -> bool:
    cleaned = (
        question.strip()
        .replace(",", "")
        .replace("£", "")
        .replace("$", "")
    )

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
        understanding = llm.understand_question(
            question,
            schema,
        )
    except llm.LLMError as exc:
        st.error(f"I could not interpret that question: {exc}")
        logger.error("Question understanding failed: %s", exc)
        return None

    try:
        raw_sql = llm.generate_sql(
            question,
            schema,
            understanding,
        )
    except llm.LLMError as exc:
        st.error(f"I could not generate a safe query: {exc}")
        logger.error("Initial SQL generation failed: %s", exc)
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
                        st.markdown(
                            f"#### Attempt {attempt['attempt']}"
                        )
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
                    "The query failed the safety checks and "
                    "could not be corrected."
                )
                logger.error(
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
                        st.markdown(
                            f"#### Attempt {attempt['attempt']}"
                        )
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
                    "The database query failed and Gemini "
                    "could not generate a correction."
                )
                logger.error(
                    "SQL regeneration after database failure failed: %s",
                    regeneration_error,
                )
                return None

            continue

        break

    if safe_sql is None or query_result is None:
        logger.error(
            "Pipeline finished without a validated SQL query or result."
        )
        st.error("The analysis could not be completed.")
        return None

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
            explanation = (
                f"The query returned {query_result.row_count:,} rows."
            )

        logger.warning("Result explanation failed: %s", exc)

    try:
        followups = llm.suggest_followups(
            question,
            explanation,
            schema,
        )
    except llm.LLMError as exc:
        followups = []
        logger.warning("Follow-up generation failed: %s", exc)

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
        st.info(
            "The initial query failed and was corrected automatically."
        )

    if dataframe.empty:
        st.info(
            "The query ran successfully, but no matching records were found."
        )
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

        followup_columns = st.columns(
            min(len(followups), 3)
        )

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
            type=(
                "primary"
                if st.session_state.view == "assistant"
                else "secondary"
            ),
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

        st.markdown("Revenue")
        st.markdown("Sales performance")
        st.markdown("Products")
        st.markdown("History")

        st.markdown("---")

        with st.expander("Developer mode"):
            st.caption(
                "Schema and SQL details are available inside each response."
            )


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
        top_customers = customer_service.get_top_customers_by_lifetime_value(
            limit=10
        )
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
        render_customer_analytics()
        return

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

    typed_question = st.chat_input(
        "Ask about customers, revenue or sales performance"
    )

    if typed_question:
        process_question(
            typed_question.strip(),
            schema,
        )


if __name__ == "__main__":
    main()