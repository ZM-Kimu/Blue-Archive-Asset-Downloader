from enum import StrEnum
from pathlib import PurePosixPath


class BundleHandler(StrEnum):
    assetripper = "assetripper"
    unitypy = "unitypy"


def bundle_member_cache_resource_path(
    archive_path: str,
    member_path: str,
) -> str:
    archive = _safe_relative_parts(archive_path, strip_bundle_root=True)
    member = _safe_relative_parts(member_path, strip_bundle_root=False)
    return PurePosixPath("Bundle", ".members", *archive, *member).as_posix()


def _safe_relative_parts(value: str, *, strip_bundle_root: bool) -> tuple[str, ...]:
    normalized = value.strip().replace("\\", "/")
    parts = tuple(part for part in normalized.split("/") if part and part != ".")
    if strip_bundle_root and parts and parts[0].casefold() == "bundle":
        parts = parts[1:]
    if not parts or any(part == ".." for part in parts):
        raise ValueError("Bundle cache paths must be safe relative paths.")
    return parts
