from typing import Literal

from ba_downloader.domain.models.settings import AppSettings


class Config:
    threads: int = 20
    version: str = ""
    region: Literal["cn", "gl", "jp"] = "jp"
    raw_dir: str = "JPRawData"
    extract_dir: str = "JPExtracted"
    temp_dir: str = "JPTemp"
    downloading_extract: bool = False
    resource_type: list[str] = ["table", "media", "bundle"]
    search: list[str] = []
    advance_search: list[str] = []
    proxy: dict[str, str] | None = None
    retries: int = 5
    work_dir: str = ""
    max_threads: int = threads * 7


_runtime_settings: AppSettings | None = None


def apply_settings(settings: AppSettings) -> AppSettings:
    normalized = settings.normalized()

    Config.threads = normalized.threads
    Config.version = normalized.version
    Config.region = normalized.region
    Config.raw_dir = normalized.raw_dir
    Config.extract_dir = normalized.extract_dir
    Config.temp_dir = normalized.temp_dir
    Config.downloading_extract = normalized.extract_while_download
    Config.resource_type = list(normalized.resource_type)
    Config.search = list(normalized.search)
    Config.advance_search = list(normalized.advanced_search)
    Config.proxy = (
        {"http": normalized.proxy_url, "https": normalized.proxy_url}
        if normalized.proxy_url
        else None
    )
    Config.retries = normalized.max_retries
    Config.work_dir = normalized.work_dir
    Config.max_threads = max(1, Config.threads * 7)

    global _runtime_settings
    _runtime_settings = normalized
    return normalized


def get_settings() -> AppSettings | None:
    return _runtime_settings
