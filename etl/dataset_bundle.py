from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from pathlib import Path
from typing import Any


REQUIRED_RAW_FILES = (
    "olist_customers_dataset.csv",
    "product_category_name_translation.csv",
    "olist_products_dataset.csv",
    "olist_sellers_dataset.csv",
    "olist_orders_dataset.csv",
    "olist_order_items_dataset.csv",
    "olist_order_payments_dataset.csv",
)
MANIFEST_NAME = "manifest.json"
MANIFEST_VERSION = 1
MAX_FILE_BYTES = 100 * 1024 * 1024
MAX_DATASET_BYTES = 300 * 1024 * 1024
_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


class DatasetBundleError(ValueError):
    """Raised when an Olist data bundle violates the release contract."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def build_manifest(raw_directory: Path) -> dict[str, Any]:
    files = []
    total_bytes = 0

    for filename in REQUIRED_RAW_FILES:
        path = raw_directory / filename
        if not path.is_file():
            raise DatasetBundleError(f"Required Olist file is missing: {filename}")

        size = path.stat().st_size
        if size <= 0:
            raise DatasetBundleError(f"Required Olist file is empty: {filename}")
        if size > MAX_FILE_BYTES:
            raise DatasetBundleError(f"Olist file exceeds size limit: {filename}")

        total_bytes += size
        files.append({"name": filename, "bytes": size, "sha256": _sha256(path)})

    if total_bytes > MAX_DATASET_BYTES:
        raise DatasetBundleError("Olist dataset exceeds the total size limit")

    identity = {"manifest_version": MANIFEST_VERSION, "files": files}
    dataset_id = hashlib.sha256(_canonical_json(identity)).hexdigest()
    return {
        **identity,
        "dataset": "olist-brazilian-ecommerce",
        "dataset_id": dataset_id,
        "total_bytes": total_bytes,
    }


def create_bundle(raw_directory: Path, output_path: Path) -> dict[str, Any]:
    """Create a deterministic, checksummed Olist release bundle."""

    manifest = build_manifest(raw_directory)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(f"{output_path.suffix}.tmp")
    temporary_path.unlink(missing_ok=True)

    try:
        with zipfile.ZipFile(
            temporary_path,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as archive:
            manifest_info = zipfile.ZipInfo(MANIFEST_NAME, _ZIP_TIMESTAMP)
            manifest_info.external_attr = 0o644 << 16
            archive.writestr(manifest_info, _canonical_json(manifest))

            for filename in REQUIRED_RAW_FILES:
                member = zipfile.ZipInfo(f"raw/{filename}", _ZIP_TIMESTAMP)
                member.external_attr = 0o644 << 16
                member.compress_type = zipfile.ZIP_DEFLATED
                with (raw_directory / filename).open("rb") as source:
                    with archive.open(member, mode="w", force_zip64=True) as target:
                        shutil.copyfileobj(source, target, length=1024 * 1024)

        temporary_path.replace(output_path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise

    return manifest


def validate_and_extract_bundle(bundle_path: Path, destination: Path) -> dict[str, Any]:
    """Validate an exact bundle manifest and extract only approved CSV files."""

    destination.mkdir(parents=True, exist_ok=True)
    if any(destination.iterdir()):
        raise DatasetBundleError("Extraction destination must be empty")

    created: list[Path] = []
    try:
        with zipfile.ZipFile(bundle_path, mode="r") as archive:
            names = archive.namelist()
            expected_names = [
                MANIFEST_NAME,
                *[f"raw/{name}" for name in REQUIRED_RAW_FILES],
            ]
            if len(names) != len(set(names)) or set(names) != set(expected_names):
                raise DatasetBundleError(
                    "Bundle contains missing, duplicate, or unexpected files"
                )

            manifest = json.loads(archive.read(MANIFEST_NAME))
            if manifest.get("manifest_version") != MANIFEST_VERSION:
                raise DatasetBundleError("Unsupported dataset manifest version")

            file_entries = manifest.get("files")
            if not isinstance(file_entries, list):
                raise DatasetBundleError("Dataset manifest files must be a list")

            entries = {entry.get("name"): entry for entry in file_entries}
            if set(entries) != set(REQUIRED_RAW_FILES):
                raise DatasetBundleError(
                    "Dataset manifest does not list the exact required files"
                )

            identity = {"manifest_version": MANIFEST_VERSION, "files": file_entries}
            expected_id = hashlib.sha256(_canonical_json(identity)).hexdigest()
            if manifest.get("dataset_id") != expected_id:
                raise DatasetBundleError("Dataset manifest ID is invalid")

            total_bytes = 0
            for filename in REQUIRED_RAW_FILES:
                entry = entries[filename]
                declared_size = entry.get("bytes")
                if (
                    not isinstance(declared_size, int)
                    or not 0 < declared_size <= MAX_FILE_BYTES
                ):
                    raise DatasetBundleError(f"Invalid declared size for {filename}")
                total_bytes += declared_size

                target = destination / filename
                digest = hashlib.sha256()
                written = 0
                with archive.open(f"raw/{filename}", mode="r") as source:
                    with target.open("xb") as output:
                        created.append(target)
                        while chunk := source.read(1024 * 1024):
                            written += len(chunk)
                            if written > declared_size or written > MAX_FILE_BYTES:
                                raise DatasetBundleError(
                                    f"Size mismatch for {filename}"
                                )
                            digest.update(chunk)
                            output.write(chunk)

                if written != declared_size or digest.hexdigest() != entry.get(
                    "sha256"
                ):
                    raise DatasetBundleError(f"Checksum mismatch for {filename}")

            if total_bytes > MAX_DATASET_BYTES or total_bytes != manifest.get(
                "total_bytes"
            ):
                raise DatasetBundleError("Dataset total size is invalid")

            return manifest
    except Exception:
        for path in created:
            path.unlink(missing_ok=True)
        raise
