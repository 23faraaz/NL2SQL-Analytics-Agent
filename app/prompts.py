"""
Prompt templates for the 4-step pipeline.

WHY THESE LIVE IN THEIR OWN FILE:
Keeping prompts separate from the API-calling logic in llm.py means you can
iterate on prompt wording without touching request/response handling, and
it makes the prompts easy to point to directly in an interview ("here's
exactly what I send Claude at each step").
"""

QUESTION_UNDERSTANDING_PROMPT = """You are analysing a user's natural-language question about an e-commerce database.

Extract the following as JSON:
- "intent": a short description of what the user wants to know
- "entities": relevant tables/concepts mentioned (e.g. "customers", "orders", "products")
- "time_filter": any time range mentioned, described in plain English (e.g. "last 30 days", "March 2026", null if none)
- "aggregation": whether this needs counting, summing, averaging, etc. (or null)

Database schema:
{schema}

User question: {question}

Respond with ONLY valid JSON, no other text, no markdown code fences."""


SQL_GENERATION_PROMPT = """You are a PostgreSQL expert. Write a single SELECT query to answer the user's question.

Database schema:
{schema}

User question: {question}

Question analysis:
{understanding}

Rules:
- Output ONLY a single valid PostgreSQL SELECT statement, nothing else
- No markdown code fences, no explanation, no comments
- Do not use INSERT, UPDATE, DELETE, DROP, ALTER, or any other write operation
- Use explicit JOINs with clear ON conditions
- Add a sensible LIMIT (e.g. 100) unless the question clearly asks for an aggregate/single value
- Use table aliases for readability on multi-table joins"""


RESULT_EXPLANATION_PROMPT = """You are explaining query results to a non-technical business user.

Original question: {question}

SQL query that was run:
{sql}

Results ({row_count} rows):
{results}

Write a short, plain-English explanation of what these results show, as if
speaking to someone with no SQL knowledge. Mention specific numbers from
the results. Keep it to 2-4 sentences. Do not mention SQL, tables, or
technical database terms."""


FOLLOWUP_SUGGESTIONS_PROMPT = """Based on this question and its results, suggest 3 related follow-up
questions the user might want to ask next about this e-commerce data.

Original question: {question}

Results summary: {results_summary}

Database schema (for context on what's possible to ask):
{schema}

Respond with ONLY a JSON array of 3 short question strings, no other text,
no markdown code fences. Example format:
["Question one?", "Question two?", "Question three?"]"""