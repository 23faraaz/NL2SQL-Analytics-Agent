from __future__ import annotations

import argparse
import os
import tempfile
from pathlib import Path

from etl.dataset_bundle import validate_and_extract_bundle


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import one verified Olist dataset")
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--source-version", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    with tempfile.TemporaryDirectory(prefix="olist-import-") as workspace:
        workspace_path = Path(workspace)
        raw_directory = workspace_path / "raw"
        processed_directory = workspace_path / "processed"
        raw_directory.mkdir()
        processed_directory.mkdir()

        os.environ["OLIST_RAW_DATA_DIR"] = str(raw_directory)
        os.environ["OLIST_PROCESSED_DATA_DIR"] = str(processed_directory)

        # Import after setting the isolated paths because the ETL modules read
        # their configuration at module import time.
        from etl.augment.pipeline import run_augmentation_pipeline
        from etl.pipeline import run_transformation_pipeline
        from scripts.load_commerce import load_commerce

        manifest = validate_and_extract_bundle(args.bundle, raw_directory)
        if manifest["dataset_id"] != args.dataset_id:
            raise ValueError("Expected dataset ID does not match the verified bundle")

        run_transformation_pipeline()
        run_augmentation_pipeline()
        load_commerce(
            dataset_id=args.dataset_id,
            source_version=args.source_version,
            require_empty=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
