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
    Runs the existing pipeline without rendering internal progress stages
    as the main user experience.
    """
    try:
        understanding = llm.understand_question(question, schema)
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
        logger.error("SQL generation failed: %s", exc)
        return None

    try:
        safe_sql = sql_validator.validate_select_only(raw_sql)
    except sql_validator.SQLValidationError as exc:
        st.error(
            "The generated query failed the safety checks and was not run."
        )

        with st.expander("Rejected SQL"):
            st.code(raw_sql, language="sql")
            st.caption(str(exc))

        logger.warning("SQL rejected: %s", exc)
        return None

    try:
        query_result = execute_analytics_query(safe_sql)
    except db.DatabaseError as exc:
        st.error(f"The database query could not be completed: {exc}")
        logger.error("Query execution failed: %s", exc)
        return None

    try:
        explanation = llm.explain_results(
            question,
            safe_sql,
            list(query_result.dataframe.columns),
            list(query_result.dataframe.itertuples(index=False, name=None)),
        )
    except llm.LLMError as exc:
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
    }


def render_business_answer(result: dict[str, Any]) -> None:
    query_result = result["query_result"]
    dataframe = query_result.dataframe

    st.markdown("### Answer")

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
        st.markdown("Assistant")
        st.markdown("Customers")
        st.markdown("Revenue")
        st.markdown("Sales performance")
        st.markdown("Products")
        st.markdown("History")

        st.markdown("---")

        with st.expander("Developer mode"):
            st.caption(
                "Schema and SQL details are available inside each response."
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