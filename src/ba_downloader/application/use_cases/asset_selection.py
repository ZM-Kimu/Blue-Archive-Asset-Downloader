from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from ba_downloader.domain.models.asset import AssetCollection
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.domain.ports.relation import RelationBuilderPort
from ba_downloader.domain.services.resource_query import ResourceQueryService

RelationBuilderFactory = Callable[[RuntimeContext], RelationBuilderPort]
EnsureRelationCallback = Callable[
    [RelationBuilderPort, AssetCollection, RuntimeContext],
    None,
]
VERSION_MANAGED_REGIONS = {"cn", "jp"}


class AssetSelectionService:
    def __init__(
        self,
        relation_builder_factory: RelationBuilderFactory,
        logger: LoggerPort,
    ) -> None:
        self.relation_builder_factory = relation_builder_factory
        self.logger = logger

    def filter_search_resources(
        self,
        resources: AssetCollection,
        context: RuntimeContext,
        *,
        ensure_relation: EnsureRelationCallback | None = None,
        require_current_relation: bool = False,
    ) -> AssetCollection:
        if not context.search and not context.advanced_search:
            return resources

        keywords: list[str] = []
        if context.advanced_search:
            relation_builder = self.relation_builder_factory(context)
            if require_current_relation:
                self._require_current_relation(relation_builder, context)
            elif (
                ensure_relation is not None
                and not relation_builder.verify_relation_file(context)
            ):
                ensure_relation(relation_builder, resources, context)
            keywords = relation_builder.search(
                context,
                list(context.advanced_search),
            )

        if context.search:
            keywords = list(context.search)
        elif context.advanced_search and not keywords:
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

    @staticmethod
    def _require_current_relation(
        relation_builder: RelationBuilderPort,
        context: RuntimeContext,
    ) -> None:
        if relation_builder.verify_relation_file(context):
            return

        command_args = AssetSelectionService._format_relation_command_args(context)
        raise LookupError(
            "Character relation file is missing or does not match the current "
            "resource version. Run "
            f"`ba-downloader relation build {command_args}` "
            "or "
            f"`ba-downloader sync {command_args} -as <keyword>` "
            "before using extract --advanced-search."
        )

    @staticmethod
    def _format_relation_command_args(context: RuntimeContext) -> str:
        version_hint = ""
        if context.version and context.region not in VERSION_MANAGED_REGIONS:
            version_hint = f" --version {context.version}"
        return f"--region {context.region}{version_hint}"
