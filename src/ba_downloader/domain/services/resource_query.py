from __future__ import annotations

from ba_downloader.domain.models.asset import AssetCollection
from ba_downloader.domain.models.asset_type_selection import (
    ALL_RESOURCE_TYPES,
    ResourceTypeSelection,
)
from ba_downloader.domain.models.execution import ExecutionContext


class ResourceQueryService:
    @staticmethod
    def filter_type(
        resource: AssetCollection,
        resource_type: ResourceTypeSelection | list[str] | tuple[str, ...],
    ) -> AssetCollection:
        selection = (
            resource_type
            if isinstance(resource_type, ResourceTypeSelection)
            else ResourceTypeSelection.from_values(resource_type)
        )
        if selection.types == ALL_RESOURCE_TYPES:
            return resource

        filtered = AssetCollection()
        for item in resource:
            if selection.contains(item.asset_type):
                filtered.add_item(item)

        return filtered

    @staticmethod
    def filter_existing(
        resources: AssetCollection,
        context: ExecutionContext,
    ) -> AssetCollection:
        filtered = AssetCollection()
        seen_paths: set[str] = set()
        for resource in resources:
            if resource.path in seen_paths:
                continue
            if context.workspace.raw_resource_path(
                resource.asset_type.value,
                resource.path,
            ).is_file():
                filtered.add_item(resource)
                seen_paths.add(resource.path)
        return filtered
