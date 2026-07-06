from __future__ import annotations

from dataclasses import dataclass

from ba_downloader.domain.models.region import Platform, Region
from ba_downloader.domain.models.region_profile import RegionSettingsPolicy

PLATFORM_DISPLAY_NAMES: dict[Platform, str] = {
    "windows": "Windows",
    "android": "Android",
    "ios": "iOS",
}


@dataclass(frozen=True, slots=True)
class RegionDirectoryDefaults:
    raw_dir: str
    extract_dir: str
    temp_dir: str


def normalize_region_directories(
    *,
    region: Region,
    platform: Platform,
    settings_policy: RegionSettingsPolicy,
    raw_dir: str,
    extract_dir: str,
    temp_dir: str,
) -> RegionDirectoryDefaults:
    prefix = (
        f"{region.upper()}_{PLATFORM_DISPLAY_NAMES[platform]}_"
        if settings_policy.include_platform_in_default_dirs
        else f"{region.upper()}_"
    )
    return RegionDirectoryDefaults(
        raw_dir=_prefix_default(raw_dir, "RawData", prefix),
        extract_dir=_prefix_default(extract_dir, "Extracted", prefix),
        temp_dir=_prefix_default(temp_dir, "Temp", prefix),
    )


def _prefix_default(value: str, default_value: str, prefix: str) -> str:
    return f"{prefix}{value}" if value == default_value else value
