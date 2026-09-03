from __future__ import annotations

import hashlib
import hmac
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
OBJECT_KEY_PATTERN = re.compile(r"^releases/[A-Za-z0-9._/-]+$")


def required_environment(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise ValueError(f"{name} is required")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    bucket = required_environment("DATASET_BUCKET")
    object_key = required_environment("DATASET_OBJECT_KEY")
    object_version = required_environment("DATASET_OBJECT_VERSION")
    expected_archive_hash = required_environment("DATASET_BUNDLE_SHA256")
    dataset_id = required_environment("DATASET_ID")

    if not OBJECT_KEY_PATTERN.fullmatch(object_key) or ".." in object_key:
        raise ValueError("DATASET_OBJECT_KEY is invalid")
    if not SHA256_PATTERN.fullmatch(expected_archive_hash):
        raise ValueError("DATASET_BUNDLE_SHA256 must be a lowercase SHA-256")
    if not SHA256_PATTERN.fullmatch(dataset_id):
        raise ValueError("DATASET_ID must be a lowercase SHA-256")

    with tempfile.TemporaryDirectory(prefix="olist-download-") as workspace:
        bundle = Path(workspace) / "olist.zip"
        subprocess.run(
            [
                "aws",
                "s3api",
                "get-object",
                "--bucket",
                bucket,
                "--key",
                object_key,
                "--version-id",
                object_version,
                str(bundle),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        actual_archive_hash = sha256_file(bundle)
        if not hmac.compare_digest(actual_archive_hash, expected_archive_hash):
            raise ValueError("Downloaded bundle SHA-256 does not match approval input")

        subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.import_olist_bundle",
                "--bundle",
                str(bundle),
                "--dataset-id",
                dataset_id,
                "--source-version",
                object_version,
            ],
            check=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
