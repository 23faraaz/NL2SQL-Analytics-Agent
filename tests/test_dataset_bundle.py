import json
import zipfile
from pathlib import Path

import pytest

from etl.dataset_bundle import (
    MANIFEST_NAME,
    REQUIRED_RAW_FILES,
    DatasetBundleError,
    create_bundle,
    validate_and_extract_bundle,
)


def _write_raw_files(directory: Path) -> None:
    directory.mkdir()
    for index, filename in enumerate(REQUIRED_RAW_FILES):
        (directory / filename).write_text(f"column\nvalue-{index}\n", encoding="utf-8")


def test_bundle_round_trip_is_checksummed_and_deterministic(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    _write_raw_files(raw)
    first = tmp_path / "first.zip"
    second = tmp_path / "second.zip"

    first_manifest = create_bundle(raw, first)
    second_manifest = create_bundle(raw, second)
    extracted = tmp_path / "extracted"
    validated = validate_and_extract_bundle(first, extracted)

    assert first.read_bytes() == second.read_bytes()
    assert validated["dataset_id"] == first_manifest["dataset_id"]
    assert second_manifest["dataset_id"] == first_manifest["dataset_id"]
    for filename in REQUIRED_RAW_FILES:
        assert (extracted / filename).read_bytes() == (raw / filename).read_bytes()


def test_bundle_rejects_unexpected_member(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    _write_raw_files(raw)
    bundle = tmp_path / "olist.zip"
    create_bundle(raw, bundle)

    with zipfile.ZipFile(bundle, mode="a") as archive:
        archive.writestr("raw/unexpected.csv", "secret\n")

    with pytest.raises(DatasetBundleError, match="unexpected"):
        validate_and_extract_bundle(bundle, tmp_path / "extracted")


def test_bundle_rejects_manifest_tampering(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    _write_raw_files(raw)
    bundle = tmp_path / "olist.zip"
    create_bundle(raw, bundle)

    with zipfile.ZipFile(bundle, mode="r") as source:
        members = {name: source.read(name) for name in source.namelist()}
    manifest = json.loads(members[MANIFEST_NAME])
    manifest["files"][0]["sha256"] = "0" * 64

    with zipfile.ZipFile(bundle, mode="w") as target:
        for name, content in members.items():
            target.writestr(
                name,
                json.dumps(manifest).encode() if name == MANIFEST_NAME else content,
            )

    with pytest.raises(DatasetBundleError, match="manifest ID"):
        validate_and_extract_bundle(bundle, tmp_path / "extracted")
