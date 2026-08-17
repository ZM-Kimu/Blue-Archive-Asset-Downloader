from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from ba_downloader.domain.models.asset import AssetCollection
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.models.storage import StorageCleanupTarget
from ba_downloader.domain.ports.execution import ArtifactSinkPort, CancellationPort


class ApplicationOperation(StrEnum):
    sync = "sync"
    download = "download"
    extract = "extract"
    character_index = "character-index"
    catalog_refresh = "catalog-refresh"
    storage_cleanup = "storage-cleanup"


@dataclass(frozen=True, slots=True)
class ApplicationOperationCommand:
    operation: ApplicationOperation
    cleanup_targets: tuple[StorageCleanupTarget, ...] = ()


@dataclass(frozen=True, slots=True)
class ApplicationOperationResult:
    context: RuntimeContext
    artifacts: tuple[tuple[str, str], ...]
    catalog: AssetCollection | None = None
    statistics: tuple[tuple[str, int], ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ApplicationOperationHandlerResult:
    context: RuntimeContext
    catalog: AssetCollection | None = None
    statistics: tuple[tuple[str, int], ...] = ()
    warnings: tuple[str, ...] = ()


class ApplicationOperationHandlerPort(Protocol):
    def execute(
        self,
        command: ApplicationOperationCommand,
    ) -> ApplicationOperationHandlerResult: ...


class ApplicationOperationExecutor:
    def __init__(
        self,
        handler: ApplicationOperationHandlerPort,
        cancellation: CancellationPort,
        artifacts: ArtifactSinkPort,
        context: RuntimeContext,
    ) -> None:
        self._handler = handler
        self._cancellation = cancellation
        self._artifacts = artifacts
        self._context = context

    def execute(
        self,
        command: ApplicationOperationCommand,
    ) -> ApplicationOperationResult:
        self._cancellation.raise_if_cancelled()
        handler_result = self._handler.execute(command)
        self._cancellation.raise_if_cancelled()
        self._record_default_artifacts(command.operation, handler_result.context)
        return ApplicationOperationResult(
            context=handler_result.context,
            artifacts=self._artifacts.snapshot(),
            catalog=handler_result.catalog,
            statistics=handler_result.statistics,
            warnings=handler_result.warnings,
        )

    def _record_default_artifacts(
        self,
        operation: ApplicationOperation,
        context: RuntimeContext,
    ) -> None:
        logical_outputs: dict[ApplicationOperation, tuple[tuple[str, str], ...]] = {
            ApplicationOperation.sync: (
                ("raw", context.raw_dir),
                ("extracted", context.extract_dir),
                ("temporary", context.temp_dir),
            ),
            ApplicationOperation.download: (("raw", context.raw_dir),),
            ApplicationOperation.extract: (("extracted", context.extract_dir),),
            ApplicationOperation.character_index: (
                ("raw", context.raw_dir),
                ("extracted", context.extract_dir),
                ("temporary", context.temp_dir),
            ),
            ApplicationOperation.catalog_refresh: (),
            ApplicationOperation.storage_cleanup: (),
        }
        for kind, value in logical_outputs[operation]:
            path = Path(value)
            if path.exists():
                self._artifacts.record(kind, path)

        for kind, path in (
            ("dump-cs", Path(context.extract_dir, "Dumps", "dump.cs")),
            (
                "memorypack-formatters",
                Path(context.extract_dir, "Dumps", "memorypack_formatters.json"),
            ),
        ):
            if path.is_file():
                self._artifacts.record(kind, path)

        if context.region == "cn" and context.version:
            runtime_root = Path(context.temp_dir)
            if context.workspace_mode == "v3":
                runtime_root = runtime_root.parent / "runtime"
            recovery_metadata = (
                runtime_root
                / context.version
                / "MetadataRecovery"
                / "global-metadata.standard-v29.dat"
            )
            if recovery_metadata.is_file():
                self._artifacts.record("cn-recovery-metadata", recovery_metadata)

        if operation in {
            ApplicationOperation.sync,
            ApplicationOperation.character_index,
        }:
            index_path = Path(context.work_dir, "indexes", "characters.json")
            if index_path.is_file():
                self._artifacts.record("character-index", index_path)
