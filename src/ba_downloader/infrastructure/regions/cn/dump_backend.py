from __future__ import annotations

import shutil
from pathlib import Path
from typing import ClassVar

from ba_downloader.domain.exceptions import (
    OperationCancelledError,
    ProcessExecutionError,
)
from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.domain.models.runtime_assets import PreparedRuntimeAssets
from ba_downloader.domain.ports.execution import CancellationPort, NeverCancelled
from ba_downloader.domain.ports.http import HttpClientPort
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.domain.ports.process import ProcessCommand, ProcessRunnerPort
from ba_downloader.domain.ports.progress import (
    ProgressMeasure,
    ProgressReporterFactoryPort,
    ProgressReporterPort,
    ProgressState,
)
from ba_downloader.infrastructure.progress import NullProgressReporterFactory
from ba_downloader.infrastructure.tools.cn_metadata_recovery import (
    CnMetadataRecoveryError,
    CnMetadataRecoveryPipeline,
)
from ba_downloader.infrastructure.tools.dump_backend import (
    EXPORTER_TEMPLATE_DIR,
    Cpp2IlDumpCsBackend,
    Cpp2ILSourceResolver,
)

CN_METADATA_RECOVERY_SHIM_TEMPLATE_PATH = (
    EXPORTER_TEMPLATE_DIR / "dumpcs_exporter.CnMetadataRecoveryInputShim.cs"
)


class CnMetadataRecoveryDumpError(RuntimeError):
    """Raised when the CN metadata recovery dump backend fails."""


class CnMetadataRecoveryDumpBackend(Cpp2IlDumpCsBackend):
    RECOVERY_FOLDER = "MetadataRecovery"
    FINAL_METADATA_NAME = "global-metadata.standard-v29.dat"
    _RECOVERY_STAGE_LABELS: ClassVar[dict[str, str]] = {
        "parse": "Parsing protected metadata",
        "infer": "Inferring runtime registrations",
        "rebuild": "Rebuilding standard metadata",
        "validate": "Validating recovered metadata",
    }

    def __init__(
        self,
        http_client: HttpClientPort,
        logger: LoggerPort,
        source_resolver: Cpp2ILSourceResolver | None = None,
        *,
        recovery_pipeline: CnMetadataRecoveryPipeline | None = None,
        cancellation: CancellationPort | None = None,
        process_runner: ProcessRunnerPort | None = None,
        progress_factory: ProgressReporterFactoryPort | None = None,
    ) -> None:
        active_cancellation = cancellation or NeverCancelled()
        super().__init__(
            http_client,
            logger,
            source_resolver,
            cancellation=active_cancellation,
            process_runner=process_runner,
        )
        self.recovery_pipeline = recovery_pipeline or CnMetadataRecoveryPipeline(
            cancellation=active_cancellation
        )
        self.progress_factory = progress_factory or NullProgressReporterFactory()

    def dump(
        self,
        context: ExecutionContext,
        output_dir: str,
        runtime_assets: PreparedRuntimeAssets,
    ) -> None:
        metadata_path = runtime_assets.metadata_path
        binary_path = runtime_assets.binary_path
        if not metadata_path.is_file():
            raise FileNotFoundError(
                f"Prepared CN metadata file does not exist: {metadata_path}."
            )
        if not binary_path.is_file():
            raise FileNotFoundError(
                f"Prepared CN runtime binary does not exist: {binary_path}."
            )
        unity_version = self._resolve_unity_version(
            runtime_assets.globalgamemanagers_path
        )
        if not unity_version:
            raise LookupError(
                "Cannot determine Unity version for CN metadata recovery backend. "
                "Set BA_CPP2IL_UNITY_VERSION or ensure the prepared runtime snapshot "
                "contains globalgamemanagers.",
            )

        recovery_dir = runtime_assets.root_dir.parent / self.RECOVERY_FOLDER
        with self.progress_factory.create(
            ProgressState(
                "Package",
                "processing",
                overall=ProgressMeasure(0, 4, "stages"),
                item=self._RECOVERY_STAGE_LABELS["parse"],
            )
        ) as progress:
            try:
                self.logger.info("Starting CN metadata recovery.")
                recovery_result = self.recovery_pipeline.run(
                    protected_metadata=metadata_path.read_bytes(),
                    binary_path=binary_path,
                    progress_callback=lambda stage, completed, total: (
                        self._report_recovery_progress(
                            progress, stage, completed, total
                        )
                    ),
                )
                final_metadata_path = self._write_final_metadata(
                    recovery_dir,
                    recovery_result.standard_v29_metadata,
                )
                progress.update(
                    ProgressState(
                        "Package",
                        "complete",
                        overall=ProgressMeasure(4, 4, "stages"),
                    )
                )
            except OperationCancelledError:
                progress.update(ProgressState("Package", "cancelled"))
                raise
            except CnMetadataRecoveryError as exc:
                progress.update(
                    ProgressState(
                        "Package",
                        "failed",
                        message="CN metadata recovery failed",
                        failures=1,
                    )
                )
                raise CnMetadataRecoveryDumpError(
                    "Failed to recover CN metadata. "
                    f"Step: {exc.step}. Input: {metadata_path}. "
                    f"Binary: {binary_path}. "
                    f"Output: {recovery_dir / self.FINAL_METADATA_NAME}. {exc}"
                ) from exc
            except BaseException:
                progress.update(
                    ProgressState(
                        "Package",
                        "failed",
                        message="CN metadata recovery failed",
                        failures=1,
                    )
                )
                raise
        self.logger.info("Recovered CN metadata successfully.")

        cpp2il_root = self.source_resolver.resolve(context)
        dump_cs_path = Path(output_dir) / "dump.cs"
        formatter_sidecar_path = Path(output_dir) / "memorypack_formatters.json"
        dump_cs_path.parent.mkdir(parents=True, exist_ok=True)

        framework = self._resolve_framework()
        exporter_project = self._ensure_exporter_project(
            context,
            cpp2il_root,
            framework,
            extra_source_templates={
                "CnMetadataRecoveryInputShim.cs": (
                    CN_METADATA_RECOVERY_SHIM_TEMPLATE_PATH
                ),
            },
        )
        try:
            self.process_runner.run(
                ProcessCommand(
                    (
                        "dotnet",
                        "run",
                        "--project",
                        str(exporter_project),
                        "--framework",
                        framework,
                        "--",
                        f"--binary-path={binary_path.resolve()}",
                        f"--metadata-path={final_metadata_path.resolve()}",
                        f"--unity-version={unity_version}",
                        f"--output={dump_cs_path.resolve()}",
                        f"--formatter-output={formatter_sidecar_path.resolve()}",
                        "--enable-cn-metadata-recovery-shim",
                    )
                )
            )
        except ProcessExecutionError as exc:
            raise CnMetadataRecoveryDumpError(
                "Failed to dump CN metadata recovery il2cpp with Cpp2IL backend: "
                f"{exc.stderr.strip() or exc}",
            ) from exc

        self.logger.info("Dumped CN metadata recovery il2cpp binary file successfully.")

    def _report_recovery_progress(
        self,
        progress: ProgressReporterPort,
        stage: str,
        completed: int,
        total: int,
    ) -> None:
        progress.update(
            ProgressState(
                "Package",
                "processing",
                overall=ProgressMeasure(completed, total, "stages"),
                item=self._RECOVERY_STAGE_LABELS.get(stage, stage),
            )
        )

    @classmethod
    def _write_final_metadata(cls, recovery_dir: Path, metadata: bytes) -> Path:
        recovery_dir.mkdir(parents=True, exist_ok=True)
        for child in recovery_dir.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
        final_metadata_path = recovery_dir / cls.FINAL_METADATA_NAME
        final_metadata_path.write_bytes(metadata)
        return final_metadata_path
