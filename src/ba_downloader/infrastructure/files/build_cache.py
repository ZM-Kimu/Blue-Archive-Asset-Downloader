from __future__ import annotations

import json
from pathlib import Path

from ba_downloader.infrastructure.files.atomic import write_json_atomic

BUILD_MANIFEST_NAME = "build-manifest.json"
BUILD_MANIFEST_SCHEMA_VERSION = 0


def write_build_manifest(
    root: Path,
    fingerprint: str,
    *,
    required: tuple[str, ...],
) -> None:
    if any(not (root / name).is_file() for name in required):
        raise OSError("Build output is missing required runtime artifacts.")
    write_json_atomic(
        root / BUILD_MANIFEST_NAME,
        {
            "schema_version": BUILD_MANIFEST_SCHEMA_VERSION,
            "fingerprint": fingerprint,
            "required": list(required),
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def validate_build_manifest(
    root: Path,
    fingerprint: str,
    *,
    required: tuple[str, ...],
) -> bool:
    try:
        payload = json.loads((root / BUILD_MANIFEST_NAME).read_text(encoding="utf8"))
    except (OSError, ValueError):
        return False
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != BUILD_MANIFEST_SCHEMA_VERSION
        or payload.get("fingerprint") != fingerprint
        or payload.get("required") != list(required)
    ):
        return False
    return all((root / name).is_file() for name in required)
