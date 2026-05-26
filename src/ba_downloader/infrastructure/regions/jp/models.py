from __future__ import annotations

from dataclasses import dataclass

from ba_downloader.domain.models.region import Platform


@dataclass(frozen=True)
class APKPackageInfo:
    version: str
    download_url: str


JP_PLATFORM_PATCH_SEGMENTS: dict[Platform, str] = {
    "windows": "Windows",
    "android": "Android",
    "ios": "iOS",
}


def resolve_jp_patch_pack_dir(platform: Platform) -> str:
    segment = JP_PLATFORM_PATCH_SEGMENTS[platform]
    return f"{segment}_PatchPack"
