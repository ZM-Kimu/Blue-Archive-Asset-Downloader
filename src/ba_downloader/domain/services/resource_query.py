from __future__ import annotations

from pathlib import Path

from ba_downloader.domain.models.asset import AssetCollection, AssetRecord
from ba_downloader.domain.models.asset_type_selection import (
    ALL_RESOURCE_TYPES,
    ResourceTypeSelection,
)
from ba_downloader.domain.models.runtime import RuntimeContext


class ResourceQueryService:
    @staticmethod
    def filter_type(
        resource: AssetCollection,
        resource_type: list[str] | tuple[str, ...],
    ) -> AssetCollection:
        selection = ResourceTypeSelection.from_values(resource_type)
        if selection.types == ALL_RESOURCE_TYPES:
            return resource

        filtered = AssetCollection()
        for item in resource:
            if selection.contains(item.asset_type):
                filtered.add_item(item)

        return filtered

    @staticmethod
    def search_name(
        resource: AssetCollection,
        keywords: list[str] | tuple[str, ...],
    ) -> AssetCollection:
        results = AssetCollection()
        matches: list[AssetRecord] = []

        for keyword in keywords:
            matches.extend(resource.search("path", keyword))
            matches.extend(ResourceQueryService._search_bundle_files(resource, keyword))

        for item in {item.path: item for item in matches}.values():
            results.add_item(item)

        return results

    @staticmethod
    def filter_existing(
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

    @staticmethod
    def _search_bundle_files(
        resource: AssetCollection,
        keyword: str,
    ) -> list[AssetRecord]:
        keyword_lower = keyword.lower()
        return [
            item
            for item in resource
            if any(
                keyword_lower in str(bundle_name).lower()
                for bundle_name in item.metadata.get("bundle_files", [])
            )
        ]
