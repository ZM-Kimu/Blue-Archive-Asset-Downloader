from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from os import path
from zipfile import BadZipFile

from ba_downloader.infrastructure.extraction.table.archive_classifier import (
    TableArchiveKind,
    TableArchiveRoute,
    classify_table_archive,
)
from ba_downloader.infrastructure.extraction.table.archive_support import (
    LEGACY_JP_EXCEL_STALE_WARNING_PREFIX,
    TableArchiveServices,
)
from ba_downloader.infrastructure.extraction.table.legacy_gl_archives import (
    GlLegacyArchiveExtractor,
)
from ba_downloader.infrastructure.extraction.table.memorypack_archives import (
    MemoryPackStageArchiveExtractor,
)
from ba_downloader.infrastructure.extraction.table.models import (
    CANCELLED_EXTRACTION_MESSAGE,
    ProgressCallback,
)
from ba_downloader.infrastructure.extraction.table.nested_archives import (
    NestedZipPatchArchiveExtractor,
)
from ba_downloader.infrastructure.extraction.table.raw_archives import (
    RawArchiveExporter,
)
from ba_downloader.infrastructure.extraction.table.standard_archives import (
    StandardZipArchiveExtractor,
)

ArchiveHandler = Callable[
    [
        str,
        TableArchiveRoute,
        list[str],
        Callable[[], bool] | None,
        ProgressCallback | None,
        Mapping[str, str],
    ],
    None,
]

GROUND_GRID_SCHEMA_NAME = "GroundGridFlat.bytes"
GROUND_NODE_LAYER_SCHEMA_NAME = "GroundNodeLayerFlat.bytes"
ArchiveClassifier = Callable[[str], TableArchiveRoute]


@dataclass(frozen=True, slots=True)
class TableArchiveRegistry:
    classifier: ArchiveClassifier
    enabled_kinds: frozenset[TableArchiveKind]


class TableArchiveRouter:
    def __init__(
        self,
        services: TableArchiveServices,
        *,
        classifier: ArchiveClassifier = classify_table_archive,
        registry: TableArchiveRegistry | None = None,
        raw_exporter: RawArchiveExporter | None = None,
    ) -> None:
        self.services = services
        self.classifier = registry.classifier if registry is not None else classifier
        self.raw_exporter = raw_exporter or RawArchiveExporter(services)
        self.standard_extractor = StandardZipArchiveExtractor(services)
        self.gl_legacy_extractor = GlLegacyArchiveExtractor(services)
        self.nested_zip_extractor = NestedZipPatchArchiveExtractor(services)
        self.stage_extractor = MemoryPackStageArchiveExtractor(services)
        handlers: dict[TableArchiveKind, ArchiveHandler] = {
            TableArchiveKind.RHYTHM_BEATMAP: self._extract_raw,
            TableArchiveKind.GROUND_GRID_PATCH: self._extract_ground_grid,
            TableArchiveKind.GROUND_NODE_LAYER_PATCH: self._extract_ground_node_layer,
            TableArchiveKind.GROUND_STAGE_PATCH: self._extract_ground_stage,
            TableArchiveKind.RAW: self._extract_raw,
            TableArchiveKind.GL_GROUND: self._extract_gl_ground,
            TableArchiveKind.GL_NUMERIC_STAGE: self._extract_raw,
            TableArchiveKind.MGS_LOGIC_GROUND: self._extract_mgs_logic_ground,
            TableArchiveKind.STANDARD: self._extract_standard,
        }
        self._handlers = (
            handlers
            if registry is None
            else {
                kind: handler
                for kind, handler in handlers.items()
                if kind in registry.enabled_kinds
            }
        )

    def extract_zip_file(
        self,
        file_name: str,
        *,
        should_stop: Callable[[], bool] | None = None,
        progress_callback: ProgressCallback | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> None:
        archive_name = path.basename(file_name)
        warnings: list[str] = []
        route = self.classifier(archive_name)
        inner_password_names = self._inner_password_names_from_metadata(metadata)
        handler = self._handlers.get(route.kind)
        if handler is None:
            detail = route.info_message or (
                f"archive kind '{route.kind.value}' is disabled by the active table profile"
            )
            self.services.logger.error(f"Failed to process {archive_name}: {detail}")
            return

        try:
            handler(
                file_name,
                route,
                warnings,
                should_stop,
                progress_callback,
                inner_password_names,
            )
        except RuntimeError as exc:
            if str(exc) == CANCELLED_EXTRACTION_MESSAGE:
                raise
            self.services.logger.error(f"Failed to process {archive_name}: {exc}")
            return
        except (BadZipFile, FileNotFoundError, OSError, ValueError) as exc:
            self.services.logger.error(f"Failed to process {archive_name}: {exc}")
            return

        if warnings:
            encrypted_warnings = [
                warning for warning in warnings if "_encrypted" in warning
            ]
            if encrypted_warnings:
                examples = ", ".join(encrypted_warnings[:3])
                self.services.logger.warn(
                    f"Preserved {len(encrypted_warnings)} encrypted entries while "
                    f"extracting {archive_name}: {examples}"
                )
            unsupported_warnings = [
                warning for warning in warnings if "_unsupported" in warning
            ]
            if unsupported_warnings:
                examples = ", ".join(unsupported_warnings[:3])
                self.services.logger.warn(
                    f"Preserved {len(unsupported_warnings)} unsupported entries while "
                    f"extracting {archive_name}: {examples}"
                )
            legacy_excel_warnings = [
                warning
                for warning in warnings
                if warning.startswith(LEGACY_JP_EXCEL_STALE_WARNING_PREFIX)
            ]
            if legacy_excel_warnings:
                examples = ", ".join(
                    warning.removeprefix(LEGACY_JP_EXCEL_STALE_WARNING_PREFIX)
                    for warning in legacy_excel_warnings[:6]
                )
                self.services.logger.warn(
                    f"Skipped {len(legacy_excel_warnings)} stale legacy Excel.zip "
                    "entries; JP semantic table output should come from ExcelDB.db "
                    f"or Const outputs. Examples: {examples}"
                )
            self.services.logger.warn(
                f"Skipped {len(warnings)} entries while extracting {archive_name}."
            )

    def _extract_ground_grid(
        self,
        file_name: str,
        route: TableArchiveRoute,
        warnings: list[str],
        should_stop: Callable[[], bool] | None,
        progress_callback: ProgressCallback | None,
        inner_password_names: Mapping[str, str],
    ) -> None:
        _ = route
        self.nested_zip_extractor.extract(
            file_name,
            schema_name=GROUND_GRID_SCHEMA_NAME,
            warnings=warnings,
            should_stop=should_stop,
            progress_callback=progress_callback,
            inner_password_names=inner_password_names,
        )

    def _extract_ground_node_layer(
        self,
        file_name: str,
        route: TableArchiveRoute,
        warnings: list[str],
        should_stop: Callable[[], bool] | None,
        progress_callback: ProgressCallback | None,
        inner_password_names: Mapping[str, str],
    ) -> None:
        _ = route
        self.nested_zip_extractor.extract(
            file_name,
            schema_name=GROUND_NODE_LAYER_SCHEMA_NAME,
            warnings=warnings,
            should_stop=should_stop,
            progress_callback=progress_callback,
            inner_password_names=inner_password_names,
        )

    def _extract_ground_stage(
        self,
        file_name: str,
        route: TableArchiveRoute,
        warnings: list[str],
        should_stop: Callable[[], bool] | None,
        progress_callback: ProgressCallback | None,
        inner_password_names: Mapping[str, str],
    ) -> None:
        _ = route
        self.stage_extractor.extract(
            file_name,
            warnings=warnings,
            should_stop=should_stop,
            progress_callback=progress_callback,
            inner_password_names=inner_password_names,
        )

    def _extract_raw(
        self,
        file_name: str,
        route: TableArchiveRoute,
        warnings: list[str],
        should_stop: Callable[[], bool] | None,
        progress_callback: ProgressCallback | None,
        inner_password_names: Mapping[str, str],
    ) -> None:
        _ = inner_password_names
        self.raw_exporter.extract(
            file_name,
            warnings=warnings,
            should_stop=should_stop,
            progress_callback=progress_callback,
            info_message=route.info_message,
        )

    def _extract_gl_ground(
        self,
        file_name: str,
        route: TableArchiveRoute,
        warnings: list[str],
        should_stop: Callable[[], bool] | None,
        progress_callback: ProgressCallback | None,
        inner_password_names: Mapping[str, str],
    ) -> None:
        _ = inner_password_names
        self.gl_legacy_extractor.extract_ground(
            file_name,
            schema_name=route.schema_name,
            warnings=warnings,
            should_stop=should_stop,
            progress_callback=progress_callback,
        )

    def _extract_mgs_logic_ground(
        self,
        file_name: str,
        route: TableArchiveRoute,
        warnings: list[str],
        should_stop: Callable[[], bool] | None,
        progress_callback: ProgressCallback | None,
        inner_password_names: Mapping[str, str],
    ) -> None:
        _ = (route, inner_password_names)
        self.gl_legacy_extractor.extract_mgs_logic_ground(
            file_name,
            grid_schema_name=GROUND_GRID_SCHEMA_NAME,
            warnings=warnings,
            should_stop=should_stop,
            progress_callback=progress_callback,
        )

    def _extract_standard(
        self,
        file_name: str,
        route: TableArchiveRoute,
        warnings: list[str],
        should_stop: Callable[[], bool] | None,
        progress_callback: ProgressCallback | None,
        inner_password_names: Mapping[str, str],
    ) -> None:
        _ = (route, inner_password_names)
        self.standard_extractor.extract(
            file_name,
            warnings=warnings,
            should_stop=should_stop,
            progress_callback=progress_callback,
        )

    @staticmethod
    def _inner_password_names_from_metadata(
        metadata: Mapping[str, object] | None,
    ) -> dict[str, str]:
        if metadata is None:
            return {}
        includes = metadata.get("includes")
        if not isinstance(includes, Sequence) or isinstance(includes, (str, bytes)):
            return {}
        result: dict[str, str] = {}
        for item in includes:
            item_basename = path.basename(str(item))
            if item_basename:
                result[item_basename.lower()] = item_basename
        return result
