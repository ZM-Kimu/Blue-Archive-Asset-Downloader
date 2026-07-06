from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from ba_downloader.domain.models.region import Region
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.extract import Il2CppDumpBackendPort
from ba_downloader.domain.ports.http import HttpClientPort
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.infrastructure.runtime.assets import RuntimeAssetLocator
from ba_downloader.infrastructure.tools.cn_metadata_recovery import (
    CnMetadataRecoveryError,
    CnMetadataRecoveryPipeline,
)
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
EXPORTER_CN_METADATA_RECOVERY_SHIM_CS_PATH = (
    EXPORTER_TEMPLATE_DIR / "dumpcs_exporter.CnMetadataRecoveryInputShim.cs"
)


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
    ) -> None:
        self.http_client = http_client
        self.logger = logger
        self.commit = commit
        self.archive_url = archive_url
        self.archive_sha256 = archive_sha256
        self.max_archive_files = max_archive_files
        self.max_archive_bytes = max_archive_bytes

    def resolve(self, context: RuntimeContext) -> Path:
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

    def _cache_root(self, context: RuntimeContext) -> Path:
        return (
            Path(context.work_dir)
            / ".ba-downloader"
            / "tools"
            / f"Cpp2IL-{self.commit[:12]}"
        )

    @staticmethod
    def _is_valid_cpp2il_root(root: Path) -> bool:
        return (root / CPP2IL_PROJECT).exists() and (root / LIBCPP2IL_PROJECT).exists()

    def _download_to_cache(self, cache_root: Path, *, max_attempts: int) -> None:
        cache_root.parent.mkdir(parents=True, exist_ok=True)
        archive_path = cache_root.parent / f"cpp2il-{self.commit}.zip"
        extract_dir = cache_root.parent / f"cpp2il-{self.commit}-extract"
        last_error: BaseException | None = None

        for attempt in range(1, max_attempts + 1):
            if extract_dir.exists():
                shutil.rmtree(extract_dir)
            if archive_path.exists():
                archive_path.unlink()

            self.http_client.download_to_file(self.archive_url, str(archive_path))
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
        digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
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
    BINARY_CANDIDATES = ("GameAssembly.dll", "libil2cpp.so")
    METADATA_NAME = "global-metadata.dat"
    UNITY_VERSION_ENV = "BA_CPP2IL_UNITY_VERSION"
    GLOBAL_GAME_MANAGERS = "globalgamemanagers"

    def __init__(
        self,
        http_client: HttpClientPort,
        logger: LoggerPort,
        source_resolver: Cpp2ILSourceResolver | None = None,
    ) -> None:
        self.http_client = http_client
        self.logger = logger
        self.source_resolver = source_resolver or Cpp2ILSourceResolver(
            http_client, logger
        )

    def dump(self, context: RuntimeContext, output_dir: str) -> None:
        base_dir = Path(context.temp_dir)
        locator = RuntimeAssetLocator(base_dir)
        binary_path = locator.find_first(self.BINARY_CANDIDATES)
        metadata_path = locator.find_first((self.METADATA_NAME,))
        if not binary_path or not metadata_path:
            raise FileNotFoundError(
                "Cannot find binary file or global-metadata file for Cpp2IL backend.",
            )

        unity_version = self._resolve_unity_version(base_dir)
        if not unity_version:
            raise LookupError(
                "Cannot determine Unity version for Cpp2IL backend. "
                "Set BA_CPP2IL_UNITY_VERSION or ensure globalgamemanagers exists in temp files.",
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
                    f"--metadata-path={metadata_path.resolve()}",
                    f"--unity-version={unity_version}",
                    f"--output={dump_cs_path.resolve()}",
                    f"--formatter-output={formatter_sidecar_path.resolve()}",
                ],
                capture_output=True,
                check=True,
                text=True,
                encoding="utf8",
            )
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(
                "Failed to dump il2cpp with Cpp2IL backend: "
                f"{exc.stderr.strip() or exc}",
            ) from exc

        self.logger.info("Dumped il2cpp binary file successfully.")

    def _resolve_unity_version(self, temp_dir: Path) -> str:
        import os

        if env_value := os.getenv(self.UNITY_VERSION_ENV, "").strip():
            return env_value

        managers = list(temp_dir.rglob(self.GLOBAL_GAME_MANAGERS))
        for manager_path in managers:
            try:
                raw = manager_path.read_bytes().decode("latin-1", errors="ignore")
            except OSError:
                continue
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
        context: RuntimeContext,
        cpp2il_root: Path,
        target_framework: str,
    ) -> Path:
        export_root = (
            Path(context.work_dir) / ".ba-downloader" / "tools" / EXPORTER_PROJECT_NAME
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
        (export_root / "CnMetadataRecoveryInputShim.cs").write_text(
            _read_exporter_template(EXPORTER_CN_METADATA_RECOVERY_SHIM_CS_PATH),
            encoding="utf8",
        )
        return project_path


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


BackendFactory = Callable[[HttpClientPort, LoggerPort], Il2CppDumpBackendPort]


class DumperBackendRegistry:
    def __init__(self) -> None:
        self._factories: dict[Region, BackendFactory] = {}

    def register(self, region: Region, factory: BackendFactory) -> None:
        self._factories[region] = factory

    def resolve(self, region: Region) -> BackendFactory:
        if region not in self._factories:
            raise KeyError(f"Region '{region}' is not registered.")
        return self._factories[region]


def build_default_dumper_backend_registry() -> DumperBackendRegistry:
    registry = DumperBackendRegistry()
    registry.register(
        "cn",
        lambda http_client, logger: CnMetadataRecoveryDumpBackend(http_client, logger),
    )
    registry.register(
        "gl", lambda http_client, logger: Cpp2IlDumpCsBackend(http_client, logger)
    )
    registry.register(
        "jp", lambda http_client, logger: Cpp2IlDumpCsBackend(http_client, logger)
    )
    return registry


DEFAULT_DUMPER_BACKEND_REGISTRY = build_default_dumper_backend_registry()
