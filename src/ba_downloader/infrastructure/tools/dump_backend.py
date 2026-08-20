from __future__ import annotations

import re
import shutil
from collections.abc import Callable, Mapping
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from ba_downloader.domain.exceptions import (
    OperationCancelledError,
    ProcessExecutionError,
)
from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.domain.models.runtime_assets import PreparedRuntimeAssets
from ba_downloader.domain.ports.execution import CancellationPort, NeverCancelled
from ba_downloader.domain.ports.extract import Il2CppDumpBackendPort
from ba_downloader.domain.ports.http import HttpClientPort
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.domain.ports.process import ProcessCommand, ProcessRunnerPort
from ba_downloader.infrastructure.files.checksum import calculate_sha256
from ba_downloader.infrastructure.runtime.process import CancellableProcessRunner
from ba_downloader.infrastructure.tools.runtime_probe import (
    get_installed_dotnet_sdk_major_versions,
)

CPP2IL_COMMIT = "6af99f218501529af84202243aedb7089f5307dc"
CPP2IL_ARCHIVE_URL = (
    f"https://github.com/SamboyCoding/Cpp2IL/archive/{CPP2IL_COMMIT}.zip"
)
CPP2IL_ARCHIVE_SHA256 = (
    "968f043b28c53c3bedebe1da8fed432e9ec52deb1d2b19021f3a0964d854d32c"
)
CPP2IL_MAX_ARCHIVE_FILES = 20_000
CPP2IL_MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
CPP2IL_PROJECT = Path("Cpp2IL") / "Cpp2IL.csproj"
LIBCPP2IL_PROJECT = Path("LibCpp2IL") / "LibCpp2IL.csproj"
EXPORTER_PROJECT_NAME = "dumpcs_exporter"
UNITY_VERSION_PATTERN = re.compile(r"(20\d{2}\.\d+\.\d+[a-z]\d+)", re.IGNORECASE)

EXPORTER_TEMPLATE_DIR = Path(__file__).with_name("templates")
EXPORTER_CSPROJ_TEMPLATE_PATH = (
    EXPORTER_TEMPLATE_DIR / "dumpcs_exporter.csproj.template"
)
EXPORTER_PROGRAM_CS_PATH = EXPORTER_TEMPLATE_DIR / "dumpcs_exporter.Program.cs"


def _read_exporter_template(template_path: Path) -> str:
    return template_path.read_text(encoding="utf8")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


class Cpp2ILSourceResolver:
    def __init__(
        self,
        http_client: HttpClientPort,
        logger: LoggerPort,
        commit: str = CPP2IL_COMMIT,
        archive_url: str = CPP2IL_ARCHIVE_URL,
        archive_sha256: str = CPP2IL_ARCHIVE_SHA256,
        max_archive_files: int = CPP2IL_MAX_ARCHIVE_FILES,
        max_archive_bytes: int = CPP2IL_MAX_ARCHIVE_BYTES,
        cancellation: CancellationPort | None = None,
    ) -> None:
        self.http_client = http_client
        self.logger = logger
        self.commit = commit
        self.archive_url = archive_url
        self.archive_sha256 = archive_sha256
        self.max_archive_files = max_archive_files
        self.max_archive_bytes = max_archive_bytes
        self.cancellation = cancellation or NeverCancelled()

    def resolve(self, context: ExecutionContext) -> Path:
        self.cancellation.raise_if_cancelled()
        submodule_root = _repo_root() / "third_party" / "Cpp2IL"
        if self._is_valid_cpp2il_root(submodule_root):
            return submodule_root

        cache_root = self._cache_root(context)
        if self._is_valid_cpp2il_root(cache_root):
            return cache_root

        self.logger.warn(
            "Cpp2IL source is missing. Downloading fallback source package..."
        )
        self._download_to_cache(
            cache_root,
            max_attempts=max(1, context.max_retries + 1),
        )
        if self._is_valid_cpp2il_root(cache_root):
            return cache_root
        raise FileNotFoundError("Unable to resolve a valid Cpp2IL source tree.")

    def _cache_root(self, context: ExecutionContext) -> Path:
        return context.workspace.tools_cache / f"Cpp2IL-{self.commit[:12]}"

    @staticmethod
    def _is_valid_cpp2il_root(root: Path) -> bool:
        return (root / CPP2IL_PROJECT).exists() and (root / LIBCPP2IL_PROJECT).exists()

    def _download_to_cache(self, cache_root: Path, *, max_attempts: int) -> None:
        archive_path = cache_root.parent / f"cpp2il-{self.commit}.zip"
        extract_dir = cache_root.parent / f"cpp2il-{self.commit}-extract"
        try:
            self._download_to_cache_impl(cache_root, max_attempts=max_attempts)
        except OperationCancelledError:
            archive_path.unlink(missing_ok=True)
            shutil.rmtree(extract_dir, ignore_errors=True)
            raise

    def _download_to_cache_impl(
        self,
        cache_root: Path,
        *,
        max_attempts: int,
    ) -> None:
        cache_root.parent.mkdir(parents=True, exist_ok=True)
        archive_path = cache_root.parent / f"cpp2il-{self.commit}.zip"
        extract_dir = cache_root.parent / f"cpp2il-{self.commit}-extract"
        last_error: BaseException | None = None

        for attempt in range(1, max_attempts + 1):
            self.cancellation.raise_if_cancelled()
            if extract_dir.exists():
                shutil.rmtree(extract_dir)
            if archive_path.exists():
                archive_path.unlink()

            self.http_client.download_to_file(self.archive_url, str(archive_path))
            self.cancellation.raise_if_cancelled()
            try:
                self._verify_archive_checksum(archive_path)
                with ZipFile(archive_path, "r") as archive:
                    self._safe_extract_archive(archive, extract_dir)
            except (BadZipFile, ValueError) as exc:
                last_error = exc
                if archive_path.exists():
                    archive_path.unlink()
                if extract_dir.exists():
                    shutil.rmtree(extract_dir)
                if attempt < max_attempts:
                    continue
                raise FileNotFoundError(
                    "Failed to download Cpp2IL source archive. "
                    "Retry the download or initialize the Cpp2IL submodule. "
                    f"Details: {last_error}"
                ) from last_error

            source_root = next(
                (
                    path
                    for path in extract_dir.iterdir()
                    if path.is_dir() and self._is_valid_cpp2il_root(path)
                ),
                None,
            )
            if source_root is None:
                raise FileNotFoundError(
                    "Downloaded Cpp2IL archive does not contain expected project files.",
                )

            if cache_root.exists():
                shutil.rmtree(cache_root)
            shutil.move(str(source_root), str(cache_root))

            if archive_path.exists():
                archive_path.unlink()
            if extract_dir.exists():
                shutil.rmtree(extract_dir)
            return

        if archive_path.exists():
            archive_path.unlink()
        if extract_dir.exists():
            shutil.rmtree(extract_dir)

    def _verify_archive_checksum(self, archive_path: Path) -> None:
        if not self.archive_sha256:
            return
        digest = calculate_sha256(
            archive_path,
            on_chunk=self.cancellation.raise_if_cancelled,
        )
        if digest.lower() != self.archive_sha256.lower():
            raise ValueError(
                "Cpp2IL source archive checksum mismatch: "
                f"expected {self.archive_sha256}, got {digest}."
            )

    def _safe_extract_archive(self, archive: ZipFile, extract_dir: Path) -> None:
        extract_root = extract_dir.resolve()
        total_size = 0
        infos = archive.infolist()
        if len(infos) > self.max_archive_files:
            raise ValueError(f"Cpp2IL source archive has too many files: {len(infos)}.")

        for info in infos:
            self.cancellation.raise_if_cancelled()
            total_size += max(info.file_size, 0)
            if total_size > self.max_archive_bytes:
                raise ValueError(
                    "Cpp2IL source archive exceeds maximum extracted size."
                )
            target_path = (extract_dir / info.filename).resolve()
            try:
                target_path.relative_to(extract_root)
            except ValueError as exc:
                raise ValueError(
                    f"Cpp2IL source archive contains unsafe path: {info.filename}"
                ) from exc

        archive.extractall(extract_dir)


class Cpp2IlDumpCsBackend(Il2CppDumpBackendPort):
    UNITY_VERSION_ENV = "BA_CPP2IL_UNITY_VERSION"

    def __init__(
        self,
        http_client: HttpClientPort,
        logger: LoggerPort,
        source_resolver: Cpp2ILSourceResolver | None = None,
        *,
        cancellation: CancellationPort | None = None,
        process_runner: ProcessRunnerPort | None = None,
    ) -> None:
        self.http_client = http_client
        self.logger = logger
        self.cancellation = cancellation or NeverCancelled()
        self.source_resolver = source_resolver or Cpp2ILSourceResolver(
            http_client,
            logger,
            cancellation=self.cancellation,
        )
        self.process_runner = process_runner or CancellableProcessRunner(
            self.cancellation
        )

    def dump(
        self,
        context: ExecutionContext,
        output_dir: str,
        runtime_assets: PreparedRuntimeAssets,
    ) -> None:
        self.cancellation.raise_if_cancelled()
        binary_path = runtime_assets.binary_path
        metadata_path = runtime_assets.metadata_path
        unity_version = self._resolve_unity_version(
            runtime_assets.globalgamemanagers_path
        )
        if not unity_version:
            raise LookupError(
                "Cannot determine Unity version for Cpp2IL backend. "
                "Set BA_CPP2IL_UNITY_VERSION or ensure the prepared runtime snapshot "
                "contains globalgamemanagers.",
            )

        cpp2il_root = self.source_resolver.resolve(context)
        dump_cs_path = Path(output_dir) / "dump.cs"
        formatter_sidecar_path = Path(output_dir) / "memorypack_formatters.json"
        dump_cs_path.parent.mkdir(parents=True, exist_ok=True)

        framework = self._resolve_framework()
        exporter_project = self._ensure_exporter_project(
            context,
            cpp2il_root,
            framework,
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
                        f"--metadata-path={metadata_path.resolve()}",
                        f"--unity-version={unity_version}",
                        f"--output={dump_cs_path.resolve()}",
                        f"--formatter-output={formatter_sidecar_path.resolve()}",
                    )
                )
            )
        except ProcessExecutionError as exc:
            raise RuntimeError(
                "Failed to dump il2cpp with Cpp2IL backend: "
                f"{exc.stderr.strip() or exc}",
            ) from exc

        self.logger.info("Dumped il2cpp binary file successfully.")

    def _resolve_unity_version(self, managers_path: Path | None) -> str:
        import os

        if env_value := os.getenv(self.UNITY_VERSION_ENV, "").strip():
            return env_value

        if managers_path is not None:
            try:
                raw = managers_path.read_bytes().decode("latin-1", errors="ignore")
            except OSError:
                return ""
            if match := UNITY_VERSION_PATTERN.search(raw):
                return match.group(1)

        return ""

    @staticmethod
    def _resolve_framework() -> str:
        installed = get_installed_dotnet_sdk_major_versions()
        if 10 not in installed:
            raise FileNotFoundError(
                "Error: .NET 10 SDK is required for the Cpp2IL dumper backend.",
            )
        return "net10.0"

    @staticmethod
    def _ensure_exporter_project(
        context: ExecutionContext,
        cpp2il_root: Path,
        target_framework: str,
        extra_source_templates: Mapping[str, Path] | None = None,
    ) -> Path:
        export_root = (
            Path(context.workspace.base)
            / ".ba-downloader"
            / "tools"
            / EXPORTER_PROJECT_NAME
        )
        export_root.mkdir(parents=True, exist_ok=True)

        project_path = export_root / f"{EXPORTER_PROJECT_NAME}.csproj"
        program_path = export_root / "Program.cs"
        libcpp2il_reference = (cpp2il_root / LIBCPP2IL_PROJECT).resolve().as_posix()

        project_path.write_text(
            _read_exporter_template(EXPORTER_CSPROJ_TEMPLATE_PATH).format(
                libcpp2il_reference=libcpp2il_reference,
                target_framework=target_framework,
            ),
            encoding="utf8",
        )
        program_path.write_text(
            _read_exporter_template(EXPORTER_PROGRAM_CS_PATH),
            encoding="utf8",
        )
        for source_name, template_path in (extra_source_templates or {}).items():
            (export_root / source_name).write_text(
                _read_exporter_template(template_path),
                encoding="utf8",
            )
        return project_path


BackendFactory = Callable[
    [HttpClientPort, LoggerPort, CancellationPort],
    Il2CppDumpBackendPort,
]
