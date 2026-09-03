import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_s3_import import main  # noqa: E402


def _environment() -> dict[str, str]:
    return {
        "DATASET_BUCKET": "production-nl2sql-datasets-123456789012",
        "DATASET_OBJECT_KEY": "releases/abc/olist.zip",
        "DATASET_OBJECT_VERSION": "version+one/with=safe_chars",
        "DATASET_BUNDLE_SHA256": "a" * 64,
        "DATASET_ID": "b" * 64,
    }


def test_import_downloads_by_version_and_uses_argument_arrays() -> None:
    environment = _environment()

    def fake_run(arguments: list[str], **kwargs: object) -> None:
        if arguments[:3] == ["aws", "s3api", "get-object"]:
            Path(arguments[-1]).write_bytes(b"verified bundle")

    import hashlib

    environment["DATASET_BUNDLE_SHA256"] = hashlib.sha256(
        b"verified bundle"
    ).hexdigest()
    with (
        patch.dict(os.environ, environment, clear=True),
        patch("scripts.run_s3_import.subprocess.run", side_effect=fake_run) as run,
    ):
        assert main() == 0

    download = run.call_args_list[0].args[0]
    importer = run.call_args_list[1].args[0]
    assert download[:3] == ["aws", "s3api", "get-object"]
    assert (
        download[download.index("--version-id") + 1]
        == environment["DATASET_OBJECT_VERSION"]
    )
    assert importer[:3] == [sys.executable, "-m", "scripts.import_olist_bundle"]
    assert all(invocation.kwargs["check"] for invocation in run.call_args_list)


def test_import_rejects_unsafe_object_key_before_download() -> None:
    environment = _environment()
    environment["DATASET_OBJECT_KEY"] = "releases/../private.zip"
    with (
        patch.dict(os.environ, environment, clear=True),
        patch("scripts.run_s3_import.subprocess.run") as run,
        pytest.raises(ValueError, match="OBJECT_KEY"),
    ):
        main()
    run.assert_not_called()


def test_import_rejects_download_with_wrong_archive_hash() -> None:
    environment = _environment()

    def fake_download(arguments: list[str], **kwargs: object) -> None:
        Path(arguments[-1]).write_bytes(b"wrong bundle")

    with (
        patch.dict(os.environ, environment, clear=True),
        patch("scripts.run_s3_import.subprocess.run", side_effect=fake_download) as run,
        pytest.raises(ValueError, match="does not match"),
    ):
        main()
    assert run.call_count == 1
