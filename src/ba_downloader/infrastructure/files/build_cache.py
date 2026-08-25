from __future__ import annotations

import json
from pathlib import Path

from ba_downloader.infrastructure.files.atomic import write_json_atomic
from ba_downloader.infrastructure.files.checksum import calculate_sha256

BUILD_MANIFEST_NAME = "build-manifest.json"
BUILD_MANIFEST_SCHEMA_VERSION = 0


def write_build_manifest(
    root: Path,
    fingerprint: str,
    *,
    required: tuple[str, ...],
) -> None:
    artifacts = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if relative == BUILD_MANIFEST_NAME:
            continue
        artifacts.append(
            {
                "path": relative,
                "size": path.stat().st_size,
                "sha256": calculate_sha256(path),
            }
        )
    paths = {item["path"] for item in artifacts}
    if any(name not in paths for name in required):
        raise OSError("Build output is missing required runtime artifacts.")
    write_json_atomic(
        root / BUILD_MANIFEST_NAME,
        {
            "schema_version": BUILD_MANIFEST_SCHEMA_VERSION,
            "fingerprint": fingerprint,
            "required": list(required),
            "artifacts": artifacts,
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
        or not isinstance(payload.get("artifacts"), list)
    ):
        return False

    recorded: set[str] = set()
    for item in payload["artifacts"]:
        if not isinstance(item, dict):
            return False
        relative = item.get("path")
        size = item.get("size")
        checksum = item.get("sha256")
        if (
            not isinstance(relative, str)
            or not relative
            or relative in recorded
            or not isinstance(size, int)
            or isinstance(size, bool)
            or size < 0
            or not isinstance(checksum, str)
            or len(checksum) != 64
        ):
            return False
        candidate = (root / Path(relative)).resolve(strict=False)
        try:
            candidate.relative_to(root.resolve(strict=True))
        except (OSError, ValueError):
            return False
        try:
            if (
                not candidate.is_file()
                or candidate.stat().st_size != size
                or calculate_sha256(candidate) != checksum
            ):
                return False
        except OSError:
            return False
        recorded.add(relative)

    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.relative_to(root).as_posix() != BUILD_MANIFEST_NAME
    }
    return recorded == actual and all(name in recorded for name in required)
