# Security

## SQL safety model

Two independent layers sit between LLM-generated SQL and the database:

1. **`app/sql_validator.py`** tokenizes (via `sqlparse`, not regex — a regex
   check is trivially bypassed by a comment or string literal) every
   LLM-generated query and rejects anything that is not exactly one
   read-only `SELECT`/`WITH` statement: stacked statements, DDL/DML keywords
   anywhere in the token stream, and `SELECT ... INTO` (which can still
   create and write a table). See `tests/test_sql_validator.py` for the
   full behavioural contract, including the cases a regex-based check would
   get wrong (comments and string literals containing forbidden words must
   *not* cause false rejection).
2. **`app/db.py`** executes every query inside a PostgreSQL read-only
   transaction (`SET SESSION CHARACTERISTICS`-equivalent via
   `connection.set_session(readonly=True)`) with a 10-second statement
   timeout, so even a validator gap would hit a second, independent barrier
   at the database level.

The Customer Analytics MVP (`app/services/customer_service.py`) does not use
the LLM or the validator at all — its SQL is fixed, developer-written, and
never routed through the LLM. It parameterizes every user-supplied value
(`limit`, `customer_id`) via `psycopg2`'s bound-parameter `%s` placeholders,
never string interpolation, and additionally type/range-validates both
before they reach SQL at all.

## Secrets

- Database credentials are read from environment variables only (`.env`,
  gitignored) — never hardcoded, never logged.
- Which LLM provider's credentials are required depends on `LLM_PROVIDER`
  (see `app/llm/factory.py`): `GEMINI_API_KEY`/`GEMINI_MODEL` for the
  default `gemini` provider, `GROQ_API_KEY`/`GROQ_MODEL` for `groq`. An
  unset `LLM_PROVIDER` defaults to `gemini`; an unsupported value fails
  fast rather than silently falling back.
- The active provider's model has no guessed default: the app fails fast
  at startup (`llm.validate_config()`, called from `app/main.py`) rather
  than silently falling back to an unverified model name.
- `.env.example` documents every variable with placeholder, non-secret
  values only.

## Error handling

Raw database and LLM exceptions are never shown directly to the user.
`app/db.py`, `app/llm/` (via the shared `LLMError` in `app/llm/base.py`),
`app/sql_validator.py`, and `app/services/customer_service.py` each expose
a single module-specific exception type (`DatabaseError`, `LLMError`,
`SQLValidationError`, `CustomerServiceError`); `app/main.py` catches these
and renders a clean, user-facing message. This holds regardless of which
LLM provider is configured — `GeminiProvider` and `GroqProvider` both map
every provider-specific exception to `LLMError` before it leaves
`app/llm/`.
