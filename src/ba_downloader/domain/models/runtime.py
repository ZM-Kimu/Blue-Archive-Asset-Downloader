from __future__ import annotations

from dataclasses import dataclass, replace

from ba_downloader.domain.models.settings import AppSettings


@dataclass(frozen=True, slots=True)
class RuntimeContext:
    region: str
    threads: int
    version: str
    raw_dir: str
    extract_dir: str
    temp_dir: str
    extract_while_download: bool
    resource_type: tuple[str, ...]
    proxy_url: str
    max_retries: int
    search: tuple[str, ...]
    advanced_search: tuple[str, ...]
    work_dir: str

    @classmethod
    def from_settings(cls, settings: AppSettings) -> "RuntimeContext":
        normalized = settings.normalized()
        return cls(
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
        )

    @property
    def proxy(self) -> dict[str, str] | None:
        if not self.proxy_url:
            return None
        return {"http": self.proxy_url, "https": self.proxy_url}

    @property
    def max_threads(self) -> int:
        return max(1, self.threads * 7)

    def with_updates(self, **changes: object) -> "RuntimeContext":
        return replace(self, **changes)
