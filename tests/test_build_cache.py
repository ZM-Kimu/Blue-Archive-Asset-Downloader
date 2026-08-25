from __future__ import annotations

import json
from pathlib import Path

import pytest

from ba_downloader.infrastructure.files.build_cache import (
    BUILD_MANIFEST_NAME,
    validate_build_manifest,
    write_build_manifest,
)


def _build_output(tmp_path: Path) -> tuple[Path, tuple[str, ...]]:
    root = tmp_path / "build"
    root.mkdir()
    (root / "Tool.dll").write_bytes(b"assembly")
    (root / "Tool.deps.json").write_text("{}", encoding="utf8")
    return root, ("Tool.dll", "Tool.deps.json")


def test_build_manifest_validates_complete_content_addressed_output(
    tmp_path: Path,
) -> None:
    root, required = _build_output(tmp_path)
    write_build_manifest(root, "a" * 64, required=required)

    assert validate_build_manifest(root, "a" * 64, required=required)
    payload = json.loads((root / BUILD_MANIFEST_NAME).read_text(encoding="utf8"))
    assert payload["schema_version"] == 0


@pytest.mark.parametrize("damage", ["missing", "schema"])
def test_build_manifest_rejects_incomplete_or_nonzero_cache(
    tmp_path: Path,
    damage: str,
) -> None:
    root, required = _build_output(tmp_path)
    write_build_manifest(root, "a" * 64, required=required)

    if damage == "missing":
        (root / "Tool.deps.json").unlink()
    else:
        manifest = root / BUILD_MANIFEST_NAME
        payload = json.loads(manifest.read_text(encoding="utf8"))
        payload["schema_version"] = 1
        manifest.write_text(json.dumps(payload), encoding="utf8")

    assert not validate_build_manifest(root, "a" * 64, required=required)


def test_build_manifest_does_not_rehash_or_inventory_outputs(tmp_path: Path) -> None:
    root, required = _build_output(tmp_path)
    write_build_manifest(root, "a" * 64, required=required)

    (root / "Tool.dll").write_bytes(b"changed!")
    (root / "unexpected.bin").write_bytes(b"unexpected")

    assert validate_build_manifest(root, "a" * 64, required=required)
