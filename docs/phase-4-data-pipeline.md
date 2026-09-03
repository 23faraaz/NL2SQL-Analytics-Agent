# Phase 4: production Olist data pipeline

## Status

Phase 4 is in implementation. The repository has a deterministic release-bundle
contract, a separately scanned importer image, a private versioned S3 release
bucket, and a manually approved one-off ECS import workflow. No dataset is
committed to Git, baked into an image, or uploaded by CI.

The first local bundle has dataset ID
`e6be72bdf15dc4b1b9878b04a0516910b6b7bd59bce807625c98b9f783d0fd48`.
The ID is derived from the ordered file manifest, byte sizes, and SHA-256
checksums; it is not a secret.

## Bundle contract

Create a bundle locally:

```bash
python -m scripts.package_olist \
  --raw-dir data/raw \
  --output data/generated/olist-production.zip
```

The archive is deterministic and contains only:

- `manifest.json`;
- the seven required CSV files below `raw/`.

Validation rejects missing, duplicate, unexpected, empty, oversized, or
checksum-mismatched members. Extraction writes only allowlisted basenames into
an empty destination and removes partial files after failure.

## AWS import architecture

1. A private, encrypted, versioned S3 bucket for dataset releases.
2. A separate immutable ETL/importer image scanned and published by CI.
3. A one-off Fargate task with no public IP.
4. An execution role limited to image pull, logs, and the controlled database
   administration credential used for this initial population.
5. A task role limited to `s3:GetObject` for the selected dataset prefix.
6. A manually dispatched workflow protected by the `production` environment.
7. Dataset-version registration, relationship and row-count validation,
   transactional initial population, and idempotent rerun behavior.

The Streamlit task remains SELECT-only. The importer must not reuse the web
task role or the broad Terraform apply role.

## Production safety rules

- Never execute the legacy loader against production.
- Never use `DROP`, `TRUNCATE`, or destructive schema recreation.
- Never send dataset files through GitHub Actions artifacts or commit them.
- Upload the local bundle directly to the private S3 release prefix.
- Require the operator to provide the expected dataset ID and object version.
- Permit only the first population of empty live commerce tables; refuse all
  replacement or merge attempts until a staging/promotion design is reviewed.
- Load, validate, and register the initial dataset in one database transaction;
  roll back on any failed invariant.
- Record dataset ID, S3 object version and row counts in PostgreSQL, and retain
  the importer image digest, task ARN, commit SHA, operator and timestamps in
  GitHub/AWS execution evidence.
- Refuse a different dataset when production is non-empty until an explicit
  replacement/merge policy is implemented and reviewed.

## Remaining completion gates

Phase 4 is complete only when the Terraform and workflow additions pass CI,
the bundle is uploaded to the private bucket, the approved one-off import task
succeeds, table and relationship checks pass, dashboards display Olist data,
and a repeated run proves idempotency without changing row counts.
