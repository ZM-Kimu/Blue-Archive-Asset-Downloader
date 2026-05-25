from __future__ import annotations

from dataclasses import dataclass
from os import getcwd
from typing import cast

from ba_downloader.domain.models.region import Platform, Region
from ba_downloader.domain.models.runtime import RuntimeContext

PLATFORM_DISPLAY_NAMES: dict[Platform, str] = {
    "windows": "Windows",
    "android": "Android",
    "ios": "iOS",
}


@dataclass(frozen=True, slots=True)
class AppSettings:
    region: Region
    threads: int = 20
    version: str = ""
    raw_dir: str = "RawData"
    extract_dir: str = "Extracted"
    temp_dir: str = "Temp"
    extract_while_download: bool = False
    resource_type: tuple[str, ...] = ("all",)
    proxy_url: str = ""
    max_retries: int = 5
    search: tuple[str, ...] = ()
    advanced_search: tuple[str, ...] = ()
    work_dir: str = ""
    platform: Platform = "android"
    platform_explicit: bool = False

    def normalized(self) -> AppSettings:
        region = cast(Region, self.region.lower())
        platform = cast(Platform, self.platform.lower())
        raw_dir = self.raw_dir
        extract_dir = self.extract_dir
        temp_dir = self.temp_dir

        if region == "jp":
            platform_prefix = f"{region.upper()}_{PLATFORM_DISPLAY_NAMES[platform]}_"
            if raw_dir == "RawData":
                raw_dir = f"{platform_prefix}{raw_dir}"
            if extract_dir == "Extracted":
                extract_dir = f"{platform_prefix}{extract_dir}"
            if temp_dir == "Temp":
                temp_dir = f"{platform_prefix}{temp_dir}"
        else:
            region_prefix = f"{region.upper()}_"
            if raw_dir == "RawData":
                raw_dir = f"{region_prefix}{raw_dir}"
            if extract_dir == "Extracted":
                extract_dir = f"{region_prefix}{extract_dir}"
            if temp_dir == "Temp":
                temp_dir = f"{region_prefix}{temp_dir}"

        resource_type = tuple(r.lower() for r in self.resource_type)
        if not resource_type or "all" in resource_type:
            resource_type = ("table", "media", "bundle")

        return AppSettings(
            region=region,
            threads=max(1, self.threads),
            version=self.version,
            raw_dir=raw_dir,
            extract_dir=extract_dir,
            temp_dir=temp_dir,
            extract_while_download=self.extract_while_download,
            resource_type=resource_type,
            proxy_url=self.proxy_url,
            max_retries=max(0, self.max_retries),
            search=tuple(self.search),
            advanced_search=tuple(self.advanced_search),
            work_dir=self.work_dir or getcwd(),
            platform=platform,
            platform_explicit=self.platform_explicit,
        )

    def to_runtime_context(self) -> RuntimeContext:
        normalized = self.normalized()
        return RuntimeContext(
            region=normalized.region,
            threads=normalized.threads,
            version=normalized.version,
            raw_dir=normalized.raw_dir,
            extract_dir=normalized.extract_dir,
            temp_dir=normalized.temp_dir,
            extract_while_download=normalized.extract_while_download,
            resource_type=normalized.resource_type,
            proxy_url=normalized.proxy_url,
            max_retries=normalized.max_retries,
            search=normalized.search,
            advanced_search=normalized.advanced_search,
            work_dir=normalized.work_dir,
            platform=normalized.platform,
            platform_explicit=normalized.platform_explicit,
        )
