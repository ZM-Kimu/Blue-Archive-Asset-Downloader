from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from threading import Lock
from typing import Protocol, cast

from ba_downloader.domain.models.asset import AssetRecord, AssetType
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.infrastructure.extraction.bundle.exporter import BundleExtractor
from ba_downloader.infrastructure.extraction.media.exporter import MediaExtractor
from ba_downloader.infrastructure.extraction.table.extractor import TableExtractor


class _BundleExtractor(Protocol):
    def extract_bundle(
        self,
        res_path: str,
        extract_types: list[str] | None = None,
    ) -> None: ...


class _MediaExtractor(Protocol):
    def extract_zip(self, file_path: str) -> None: ...


class _TableExtractor(Protocol):
    def extract_table(self, file_path: str) -> None: ...


_BundleFactory = Callable[[RuntimeContext, LoggerPort | None], _BundleExtractor]
_MediaFactory = Callable[[RuntimeContext], _MediaExtractor]
_TableFactory = Callable[[RuntimeContext, LoggerPort | None], _TableExtractor]


class ImmediateResourceExtractor:
    """Extract a downloaded resource immediately without coupling download to extractors."""

    def __init__(
        self,
        logger: LoggerPort,
        *,
        bundle_factory: _BundleFactory = BundleExtractor,
        media_factory: _MediaFactory = MediaExtractor,
        table_factory: _TableFactory = TableExtractor.from_context,
    ) -> None:
        self.logger = logger
        self._bundle_factory = bundle_factory
        self._media_factory = media_factory
        self._table_factory = table_factory
        self._bundle_lock = Lock()
        self._extractor_cache: dict[tuple[str, str, str, str], object] = {}

    def __call__(self, resource: AssetRecord, context: RuntimeContext) -> None:
        resource_path = str(Path(context.raw_dir) / resource.path)

        if resource.asset_type is AssetType.bundle:
            with self._bundle_lock:
                self._get_bundle_extractor(context).extract_bundle(
                    resource_path,
                    BundleExtractor.MAIN_EXTRACT_TYPES,
                )
            return

        if resource.asset_type is AssetType.media and resource.path.endswith(".zip"):
            self._get_media_extractor(context).extract_zip(resource_path)
            return

        if resource.asset_type is AssetType.table:
            self._get_table_extractor(context).extract_table(resource_path)

    def _get_bundle_extractor(self, context: RuntimeContext) -> _BundleExtractor:
        cache_key = self._cache_key("bundle", context)
        extractor = self._extractor_cache.get(cache_key)
        if extractor is None:
            extractor = self._bundle_factory(context, self.logger)
            self._extractor_cache[cache_key] = extractor
        return cast(_BundleExtractor, extractor)

    def _get_media_extractor(self, context: RuntimeContext) -> _MediaExtractor:
        cache_key = self._cache_key("media", context)
        extractor = self._extractor_cache.get(cache_key)
        if extractor is None:
            extractor = self._media_factory(context)
            self._extractor_cache[cache_key] = extractor
        return cast(_MediaExtractor, extractor)

    def _get_table_extractor(self, context: RuntimeContext) -> _TableExtractor:
        cache_key = self._cache_key("table", context)
        extractor = self._extractor_cache.get(cache_key)
        if extractor is None:
            extractor = self._table_factory(context, self.logger)
            self._extractor_cache[cache_key] = extractor
        return cast(_TableExtractor, extractor)

    @staticmethod
    def _cache_key(kind: str, context: RuntimeContext) -> tuple[str, str, str, str]:
        return (kind, context.raw_dir, context.extract_dir, context.temp_dir)
