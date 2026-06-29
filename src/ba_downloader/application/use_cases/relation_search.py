from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ba_downloader.domain.models.asset import AssetCollection
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.download import ResourceDownloaderPort
from ba_downloader.domain.ports.extract import SchemaPreparationPort
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.domain.ports.relation import RelationBuilderPort

RelationBuilderFactory = Callable[[RuntimeContext], RelationBuilderPort]
VERSION_MANAGED_REGIONS = {"cn", "jp"}


@dataclass(frozen=True, slots=True)
class RelationSearchResult:
    keywords: list[str]
    schema_prepared: bool


class RelationSearchService:
    def __init__(
        self,
        relation_builder_factory: RelationBuilderFactory,
        logger: LoggerPort,
    ) -> None:
        self.relation_builder_factory = relation_builder_factory
        self.logger = logger

    def resolve_sync_keywords(
        self,
        resources: AssetCollection,
        context: RuntimeContext,
        *,
        schema_preparation: SchemaPreparationPort,
        downloader: ResourceDownloaderPort,
        schema_prepared: bool,
    ) -> RelationSearchResult:
        if not context.advanced_search:
            return RelationSearchResult([], schema_prepared)

        self.logger.info("Preparing for advanced search...")
        relation_builder = self.relation_builder_factory(context)
        active_schema_prepared = schema_prepared
        if not relation_builder.verify_relation_file(context):
            if not active_schema_prepared:
                schema_preparation.prepare(context)
                active_schema_prepared = True
            excel_resource = relation_builder.get_excel_resources(resources)
            downloader.verify_and_download(excel_resource, context)
            relation_builder.build(context)

        return RelationSearchResult(
            relation_builder.search(context, list(context.advanced_search)),
            active_schema_prepared,
        )

    def resolve_existing_keywords(self, context: RuntimeContext) -> list[str]:
        if not context.advanced_search:
            return []

        relation_builder = self.relation_builder_factory(context)
        self._require_current_relation(relation_builder, context)
        return relation_builder.search(context, list(context.advanced_search))

    @staticmethod
    def _require_current_relation(
        relation_builder: RelationBuilderPort,
        context: RuntimeContext,
    ) -> None:
        if relation_builder.verify_relation_file(context):
            return

        command_args = RelationSearchService._format_relation_command_args(context)
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
