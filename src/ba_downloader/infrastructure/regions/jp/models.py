from __future__ import annotations

from ba_downloader.domain.models.region import Platform

JP_PLATFORM_PATCH_SEGMENTS: dict[Platform, str] = {
    "windows": "Windows",
    "android": "Android",
    "ios": "iOS",
}


def resolve_jp_patch_pack_dir(platform: Platform) -> str:
    segment = JP_PLATFORM_PATCH_SEGMENTS[platform]
    return f"{segment}_PatchPack"
