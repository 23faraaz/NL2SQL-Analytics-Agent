"""
Prompt templates for the NL2SQL pipeline.

Prompts are kept separate from API integration so prompt behaviour can be
tested and changed independently from Gemini request handling.
"""


QUESTION_UNDERSTANDING_PROMPT = """
You are analysing a natural-language analytics question for a PostgreSQL
e-commerce data warehouse.

Your job is to identify the user's analytical intent before SQL generation.

Database schema:
{schema}

User question:
{question}

Interpret the question only using concepts and fields supported by the supplied
schema.

Identify:

- intent: a concise description of the requested business analysis
- entities: the relevant schema entities, such as customers, orders, products,
  categories, suppliers, order items, or payments
- time_filter: the requested date or time period, or null when none is stated
- aggregation: the main calculation required, such as count, sum, average,
  minimum, maximum, ranking, trend, comparison, or null
- assumptions: any necessary interpretation that is not explicitly stated by
  the user
- ambiguity: whether the question has multiple reasonable interpretations

Rules:

- Do not invent tables, columns, business definitions, or relationships.
- Use only the supplied schema.
- Treat "sales" or "revenue" as ambiguous unless the schema clearly provides
  the monetary field required to calculate it.
- Treat "top" as requiring a ranking and a sensible descending order.
- Preserve explicit date ranges exactly.
- Do not generate SQL in this step.
"""


SQL_REGENERATION_PROMPT = """
You are a PostgreSQL analytics engineer correcting a query that failed
validation or database execution.

Generate exactly one corrected, safe, read-only PostgreSQL query that answers
the original user's question.

Database schema:
{schema}

Database metadata:
{database_metadata}

Original user question:
{question}

Question analysis:
{understanding}

Previous SQL:
{previous_sql}

Failure type:
{failure_type}

Validation or database error:
{error_message}

Correction requirements:

1. Diagnose the supplied failure using the previous SQL and exact error.
2. Preserve the meaning of the original user question.
3. Correct only the parts necessary to produce a valid query.
4. Output exactly one PostgreSQL query.
5. The query must begin with SELECT or WITH.
6. Use only tables and columns present in the supplied schema.
7. Fully qualify warehouse tables as warehouse.table_name.
8. Use only relationships supported by the supplied schema.
9. Never invent tables, columns, values, aliases, or relationships.
10. Never use:

    INSERT
    UPDATE
    DELETE
    DROP
    ALTER
    CREATE
    TRUNCATE
    GRANT
    REVOKE
    COPY
    CALL
    DO
    MERGE

11. Do not query PostgreSQL system schemas or metadata tables.
12. Do not use multiple SQL statements.
13. Do not include comments, markdown fences, or explanatory text.
14. Apply relative date periods using the latest available business date from
    the database metadata, not CURRENT_DATE, when the dataset is historical.
15. Avoid SELECT *.
16. Use explicit JOIN syntax.
17. Ensure every table alias is declared before it is referenced.
18. Ensure every selected non-aggregated column appears in GROUP BY.
19. Use PostgreSQL-compatible functions and syntax.
20. For detailed row-level output, use LIMIT 100 unless the user requested
    another limit.
21. If the schema cannot answer the original question, return:

    SELECT 'QUESTION_CANNOT_BE_ANSWERED_FROM_AVAILABLE_SCHEMA' AS error;

Return only the corrected SQL query.
"""