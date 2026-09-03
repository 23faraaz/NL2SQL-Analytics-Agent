CREATE TABLE IF NOT EXISTS public.nl2sql_dataset_imports (
    dataset_id TEXT PRIMARY KEY,
    source_version TEXT NOT NULL,
    imported_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    table_row_counts JSONB NOT NULL,
    CONSTRAINT chk_dataset_id_sha256 CHECK (dataset_id ~ '^[0-9a-f]{64}$')
);

COMMENT ON TABLE public.nl2sql_dataset_imports IS
    'Immutable audit record for successfully promoted production datasets.';
