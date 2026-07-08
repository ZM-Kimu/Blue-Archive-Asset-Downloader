from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.http import HttpClientPort
from ba_downloader.domain.ports.logging import LoggerPort
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
    METADATA_FOLDER = "CN_Metadata"
    RUNTIME_FOLDER = "CN_Runtime"
    RECOVERY_FOLDER = "CN_MetadataRecovery"
    FINAL_METADATA_NAME = "global-metadata.standard-v29.dat"
    BINARY_NAME = "libil2cpp.so"

    def __init__(
        self,
        http_client: HttpClientPort,
        logger: LoggerPort,
        source_resolver: Cpp2ILSourceResolver | None = None,
        *,
        recovery_pipeline: CnMetadataRecoveryPipeline | None = None,
    ) -> None:
        super().__init__(http_client, logger, source_resolver)
        self.recovery_pipeline = recovery_pipeline or CnMetadataRecoveryPipeline()

    def dump(self, context: RuntimeContext, output_dir: str) -> None:
        base_dir = Path(context.temp_dir)
        metadata_path = self._resolve_prepared_metadata_path(base_dir)
        binary_path = self._resolve_prepared_binary_path(base_dir)
        unity_version = self._resolve_unity_version(base_dir)
        if not unity_version:
            raise LookupError(
                "Cannot determine Unity version for CN metadata recovery backend. "
                "Set BA_CPP2IL_UNITY_VERSION or ensure globalgamemanagers exists in temp files.",
            )

        recovery_dir = base_dir / self.RECOVERY_FOLDER
        try:
            recovery_result = self.recovery_pipeline.run(
                protected_metadata=metadata_path.read_bytes(),
                binary_path=binary_path,
            )
        except CnMetadataRecoveryError as exc:
            raise CnMetadataRecoveryDumpError(
                "Failed to recover CN metadata. "
                f"Step: {exc.step}. Input: {metadata_path}. "
                f"Binary: {binary_path}. "
                f"Output: {recovery_dir / self.FINAL_METADATA_NAME}. {exc}"
            ) from exc

        final_metadata_path = self._write_final_metadata(
            recovery_dir,
            recovery_result.standard_v29_metadata,
        )
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
            subprocess.run(
                [
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
                ],
                capture_output=True,
                check=True,
                text=True,
                encoding="utf8",
            )
        except subprocess.CalledProcessError as exc:
            raise CnMetadataRecoveryDumpError(
                "Failed to dump CN metadata recovery il2cpp with Cpp2IL backend: "
                f"{exc.stderr.strip() or exc}",
            ) from exc

        self.logger.info("Dumped CN metadata recovery il2cpp binary file successfully.")

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

    @classmethod
    def _resolve_prepared_metadata_path(cls, temp_dir: Path) -> Path:
        metadata_path = temp_dir / cls.METADATA_FOLDER / cls.METADATA_NAME
        if not metadata_path.is_file():
            raise FileNotFoundError(
                "Cannot find CN metadata recovery metadata file. "
                "Make sure CN runtime asset preparation completed successfully."
            )
        return metadata_path

    @classmethod
    def _resolve_prepared_binary_path(cls, temp_dir: Path) -> Path:
        binary_path = temp_dir / cls.RUNTIME_FOLDER / cls.BINARY_NAME
        if not binary_path.is_file():
            raise FileNotFoundError(
                "Cannot find CN metadata recovery binary file. "
                "Make sure CN runtime asset preparation extracted libil2cpp.so."
            )
        return binary_path
