from collections.abc import Callable

from ba_downloader.domain.models.database import DatabaseSourceIdentity
from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.domain.models.schema import SchemaPurpose
from ba_downloader.domain.ports.catalog_metadata import CatalogMetadataPolicy
from ba_downloader.domain.ports.character_index import CharacterIndexBuilderPort
from ba_downloader.domain.ports.download import ResourceDownloaderPort
from ba_downloader.domain.ports.execution import CancellationPort, NeverCancelled
from ba_downloader.domain.ports.extract import SchemaPreparationPort
from ba_downloader.domain.ports.region import RegionProvider


class BuildCharacterIndexUseCase:
    def __init__(
        self,
        provider: RegionProvider,
        downloader: ResourceDownloaderPort,
        schema_preparation: SchemaPreparationPort,
        character_index_builder_factory: Callable[
            [ExecutionContext], CharacterIndexBuilderPort
        ],
        *,
        cancellation: CancellationPort | None = None,
        catalog_metadata: CatalogMetadataPolicy | None = None,
    ) -> None:
        self.provider = provider
        self.downloader = downloader
        self.schema_preparation = schema_preparation
        self.character_index_builder_factory = character_index_builder_factory
        self.cancellation = cancellation or NeverCancelled()
        self.catalog_metadata = catalog_metadata

    def build(self, context: ExecutionContext, *, concurrency: int) -> ExecutionContext:
        self.cancellation.raise_if_cancelled()
        if not self.provider.get_capabilities().supports_character_index_build:
            raise LookupError(
                f"Character index build is temporarily unavailable for region '{context.region}'."
            )

        index_catalog_loader = getattr(
            self.provider,
            "load_character_index_catalog",
            self.provider.load_catalog,
        )
        catalog = index_catalog_loader(context)
        self.cancellation.raise_if_cancelled()
        active_context = catalog.context
        database_source_identity: DatabaseSourceIdentity | None = None
        if active_context.region == "jp":
            excel_candidates = [
                resource
                for resource in catalog.resources
                if "exceldb" in resource.path.casefold()
                or any(
                    "exceldb" in include.casefold()
                    for include in resource.metadata.get("includes", [])
                    if isinstance(include, str)
                )
            ]
            if len(excel_candidates) != 1:
                raise LookupError(
                    "JP character index catalog must contain exactly one ExcelDB "
                    f"resource; found {len(excel_candidates)}."
                )
            excel_source = excel_candidates[0]
            database_source_identity = DatabaseSourceIdentity(
                region=active_context.region,
                platform=active_context.platform,
                release=active_context.resource_version or "",
                size=excel_source.size,
                checksum=(
                    f"{excel_source.checksum.algorithm}:{excel_source.checksum.value}"
                ),
            )
        if self.catalog_metadata is not None:
            self.catalog_metadata.on_catalog_loaded(
                active_context,
                catalog.resources,
            )
        schema_snapshot = self.schema_preparation.prepare(
            active_context,
            SchemaPurpose.CHARACTER_INDEX,
        )
        self.cancellation.raise_if_cancelled()

        character_index_builder = self.character_index_builder_factory(active_context)
        excel_resources = character_index_builder.get_excel_resources(catalog.resources)
        self.downloader.verify_and_download(
            excel_resources, active_context, concurrency=concurrency
        )
        self.cancellation.raise_if_cancelled()
        character_index_builder.build(
            active_context,
            schema_snapshot=schema_snapshot,
            database_source_identity=database_source_identity,
        )
        self.cancellation.raise_if_cancelled()
        return active_context
