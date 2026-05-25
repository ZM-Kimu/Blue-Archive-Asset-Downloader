from __future__ import annotations

from dataclasses import dataclass

from ba_downloader.domain.models.settings import Platform


@dataclass(frozen=True)
class APKPackageInfo:
    version: str
    download_url: str


@dataclass(frozen=True, slots=True)
class DecodedJPCatalog:
    tables: list[dict[str, object]]
    media: list[dict[str, object]]
    bundles: list[dict[str, object]]


JP_PLATFORM_PATCH_SEGMENTS: dict[Platform, str] = {
    "windows": "Windows",
    "android": "Android",
    "ios": "iOS",
}


def resolve_jp_patch_pack_dir(platform: Platform) -> str:
    segment = JP_PLATFORM_PATCH_SEGMENTS[platform]
    return f"{segment}_PatchPack"
