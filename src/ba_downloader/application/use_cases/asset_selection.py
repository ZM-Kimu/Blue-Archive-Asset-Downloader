from __future__ import annotations

from pathlib import Path

from ba_downloader.domain.models.asset import AssetCollection
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.domain.services.resource_query import ResourceQueryService


class AssetSelectionService:
    def __init__(self, logger: LoggerPort) -> None:
        self.logger = logger

    def filter_search_resources(
        self,
        resources: AssetCollection,
        context: RuntimeContext,
        *,
        advanced_keywords: list[str] | None = None,
    ) -> AssetCollection:
        if not context.search and not context.advanced_search:
            return resources

        if context.search:
            keywords = list(context.search)
        elif context.advanced_search:
            keywords = advanced_keywords or []
        else:
            keywords = []

        if context.advanced_search and not keywords:
            self.logger.warn(
                "Advanced search found no matching character relation entries."
            )
            return AssetCollection()

        if not keywords:
            return resources
        return ResourceQueryService.search_name(resources, keywords)

    @staticmethod
    def filter_existing_resources(
        resources: AssetCollection,
        context: RuntimeContext,
    ) -> AssetCollection:
        filtered = AssetCollection()
        raw_dir = Path(context.raw_dir)
        seen_paths: set[str] = set()
        for resource in resources:
            if resource.path in seen_paths:
                continue
            if (raw_dir / resource.path).is_file():
                filtered.add_item(resource)
                seen_paths.add(resource.path)
        return filtered
