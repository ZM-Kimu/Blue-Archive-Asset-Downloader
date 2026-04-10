from __future__ import annotations

import re
import shutil
import subprocess
import threading
from collections.abc import Callable
from pathlib import Path
from typing import TextIO
from zipfile import ZipFile

from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.extract import Il2CppDumpBackendPort
from ba_downloader.domain.ports.http import HttpClientPort
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.domain.ports.region import Region
from ba_downloader.infrastructure.tools.il2cpp_dumper import IL2CppDumper
from ba_downloader.infrastructure.tools.runtime_probe import (
    get_installed_dotnet_sdk_major_versions,
)

CPP2IL_COMMIT = "10db0e546fab83ec67380046f1088b62c7b38ea5"
CPP2IL_ARCHIVE_URL = (
    f"https://github.com/SamboyCoding/Cpp2IL/archive/{CPP2IL_COMMIT}.zip"
)
CPP2IL_PROJECT = Path("Cpp2IL") / "Cpp2IL.csproj"
LIBCPP2IL_PROJECT = Path("LibCpp2IL") / "LibCpp2IL.csproj"
EXPORTER_PROJECT_NAME = "dumpcs_exporter"
UNITY_VERSION_PATTERN = re.compile(r"(20\d{2}\.\d+\.\d+[a-z]\d+)", re.IGNORECASE)
CN_EXPORTER_STAGE_PATTERN = re.compile(r"^\[[#\.]+\]\s+\[\d+/\d+\]\s+.+$")
CN_EXPORTER_LOOP_PATTERN = re.compile(
    r"^\s+.+\s+\[[#\.]+\]\s+\d{1,3}%\s+\(\d+/\d+,\s+.+\)$"
)

EXPORTER_TEMPLATE_DIR = Path(__file__).with_name("templates")
EXPORTER_CSPROJ_TEMPLATE_PATH = (
    EXPORTER_TEMPLATE_DIR / "dumpcs_exporter.csproj.template"
)
EXPORTER_PROGRAM_CS_PATH = EXPORTER_TEMPLATE_DIR / "dumpcs_exporter.Program.cs"
CN_METADATA_EXPORTER_PROJECT = (
    Path("third_party") / "cn_metadata_exporter" / "cn_metadata_exporter.csproj"
)


def _read_exporter_template(template_path: Path) -> str:
    return template_path.read_text(encoding="utf8")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _find_first_match(base_dir: Path, file_names: tuple[str, ...]) -> Path | None:
    for file_name in file_names:
        matches = list(base_dir.rglob(file_name))
        if matches:
            return matches[0]
    return None


class _StreamingProcessResult:
    def __init__(self, returncode: int, stdout: str, stderr: str) -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _classify_cn_exporter_stderr_line(line: str) -> str:
    if CN_EXPORTER_LOOP_PATTERN.match(line):
        return "suppress"
    if CN_EXPORTER_STAGE_PATTERN.match(line):
        return "info"
    return "warn"


def _forward_process_stream(
    stream: TextIO | None,
    logger: LoggerPort,
    collector: list[str],
    *,
    is_stderr: bool = False,
) -> None:
    if stream is None:
        return

    try:
        for raw_line in iter(stream.readline, ""):
            line = raw_line.rstrip("\r\n")
            if not line:
                continue
            if not is_stderr:
                collector.append(line)
                logger.info(line)
                continue

            classification = _classify_cn_exporter_stderr_line(line)
            if classification == "suppress":
                continue
            collector.append(line)
            if classification == "info":
                logger.info(line)
            else:
                logger.warn(line)
    finally:
        stream.close()


def _run_streaming_process(
    command: list[str],
    logger: LoggerPort,
) -> _StreamingProcessResult:
    with subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf8",
        errors="replace",
        bufsize=1,
    ) as process:
        stdout_lines: list[str] = []
        stderr_lines: list[str] = []
        threads = [
            threading.Thread(
                target=_forward_process_stream,
                args=(process.stdout, logger, stdout_lines),
            ),
            threading.Thread(
                target=_forward_process_stream,
                args=(process.stderr, logger, stderr_lines),
                kwargs={"is_stderr": True},
            ),
        ]
        for thread in threads:
            thread.start()

        returncode = process.wait()

        for thread in threads:
            thread.join()

        return _StreamingProcessResult(
            returncode=returncode,
            stdout="\n".join(stdout_lines),
            stderr="\n".join(stderr_lines),
        )


class LegacyIl2CppDumperBackend(Il2CppDumpBackendPort):
    IL2CPP_NAME = "libil2cpp.so"
    METADATA_NAME = "global-metadata.dat"

    def __init__(self, http_client: HttpClientPort, logger: LoggerPort) -> None:
        self.http_client = http_client
        self.logger = logger

    def dump(self, context: RuntimeContext, output_dir: str) -> None:
        dumper = IL2CppDumper()
        self.logger.info("Downloading il2cpp-dumper...")
        dumper.get_il2cpp_dumper(self.http_client, context.temp_dir)

        base_dir = Path(context.temp_dir)
        il2cpp_path = _find_first_match(base_dir, (self.IL2CPP_NAME,))
        metadata_path = _find_first_match(base_dir, (self.METADATA_NAME,))
        if not (il2cpp_path and metadata_path):
            raise FileNotFoundError(
                "Cannot find il2cpp binary file or global-metadata file. Make sure they exist.",
            )

        self.logger.info("Trying to dump il2cpp...")
        dumper.dump_il2cpp(
            output_dir,
            str(il2cpp_path.resolve()),
            str(metadata_path.resolve()),
            context.max_retries,
        )
        self.logger.info("Dumped il2cpp binary file successfully.")


class CnMetadataDumpError(RuntimeError):
    """Raised when the CN metadata dump backend fails."""


class CnMetadataDumpBackend(Il2CppDumpBackendPort):
    METADATA_FOLDER = "CN_Metadata"
    METADATA_NAME = "global-metadata.dat"

    def __init__(self, http_client: HttpClientPort, logger: LoggerPort) -> None:
        self.http_client = http_client
        self.logger = logger

    def dump(self, context: RuntimeContext, output_dir: str) -> None:
        _ = self.http_client
        metadata_path = self._resolve_metadata_path(context)
        project_path = self._resolve_project_path()
        dump_cs_path = Path(output_dir) / "dump.cs"
        dump_cs_path.parent.mkdir(parents=True, exist_ok=True)

        self.logger.info("Trying to dump CN metadata...")
        result = _run_streaming_process(
            [
                "dotnet",
                "run",
                "--project",
                str(project_path),
                "-c",
                "Release",
                "--",
                "--metadata",
                str(metadata_path.resolve()),
                "--output",
                str(dump_cs_path.resolve()),
            ],
            self.logger,
        )
        if result.returncode != 0:
            summary = (
                result.stderr.strip()
                or result.stdout.strip()
                or (f"Process exited with code {result.returncode}.")
            )
            raise CnMetadataDumpError(
                "Failed to dump CN metadata with cn_metadata_exporter: " f"{summary}"
            )
        self.logger.info("Dumped CN metadata successfully.")

    @classmethod
    def _resolve_metadata_path(cls, context: RuntimeContext) -> Path:
        metadata_path = Path(context.temp_dir) / cls.METADATA_FOLDER / cls.METADATA_NAME
        if not metadata_path.is_file():
            raise FileNotFoundError(
                "Cannot find CN metadata file. Make sure runtime preparation completed successfully.",
            )
        return metadata_path

    @staticmethod
    def _resolve_project_path() -> Path:
        project_path = (_repo_root() / CN_METADATA_EXPORTER_PROJECT).resolve()
        if not project_path.is_file():
            raise FileNotFoundError(
                f"Cannot find cn_metadata_exporter project: {project_path}.",
            )
        return project_path


class Cpp2ILSourceResolver:
    def __init__(
        self,
        http_client: HttpClientPort,
        logger: LoggerPort,
        commit: str = CPP2IL_COMMIT,
        archive_url: str = CPP2IL_ARCHIVE_URL,
    ) -> None:
        self.http_client = http_client
        self.logger = logger
        self.commit = commit
        self.archive_url = archive_url

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
        self._download_to_cache(cache_root)
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

    def _download_to_cache(self, cache_root: Path) -> None:
        cache_root.parent.mkdir(parents=True, exist_ok=True)
        archive_path = cache_root.parent / f"cpp2il-{self.commit}.zip"
        extract_dir = cache_root.parent / f"cpp2il-{self.commit}-extract"

        if extract_dir.exists():
            shutil.rmtree(extract_dir)
        if archive_path.exists():
            archive_path.unlink()

        self.http_client.download_to_file(self.archive_url, str(archive_path))
        with ZipFile(archive_path, "r") as archive:
            archive.extractall(extract_dir)

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
        binary_path = _find_first_match(base_dir, self.BINARY_CANDIDATES)
        metadata_path = _find_first_match(base_dir, (self.METADATA_NAME,))
        if not binary_path or not metadata_path:
            raise FileNotFoundError(
                "Cannot find binary file or global-metadata file for Cpp2IL backend.",
            )

        unity_version = self._resolve_unity_version(context, base_dir)
        if not unity_version:
            raise LookupError(
                "Cannot determine Unity version for Cpp2IL backend. "
                "Set BA_CPP2IL_UNITY_VERSION or ensure globalgamemanagers exists in temp files.",
            )

        cpp2il_root = self.source_resolver.resolve(context)
        exporter_project = self._ensure_exporter_project(context, cpp2il_root)
        dump_cs_path = Path(output_dir) / "dump.cs"
        dump_cs_path.parent.mkdir(parents=True, exist_ok=True)

        frameworks = self._resolve_framework_order()
        errors: list[str] = []
        for index, framework in enumerate(frameworks):
            if index > 0:
                self.logger.warn(
                    f"Retrying Cpp2IL exporter with framework {framework}.",
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
                    ],
                    capture_output=True,
                    check=True,
                    text=True,
                    encoding="utf8",
                )
                self.logger.info("Dumped il2cpp binary file successfully.")
                return
            except subprocess.CalledProcessError as exc:
                errors.append(exc.stderr.strip() or str(exc))

        raise RuntimeError(
            "Failed to dump il2cpp with Cpp2IL backend: " + " | ".join(errors),
        )

    def _resolve_unity_version(self, context: RuntimeContext, temp_dir: Path) -> str:
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
    def _resolve_framework_order() -> tuple[str, ...]:
        installed = get_installed_dotnet_sdk_major_versions()
        frameworks: list[str] = []
        if 9 in installed:
            frameworks.append("net9.0")
        if 8 in installed:
            frameworks.append("net8.0")
        if not frameworks:
            raise FileNotFoundError(
                "Error: .NET 9 or .NET 8 SDK is required for the Cpp2IL dumper backend.",
            )
        return tuple(frameworks)

    @staticmethod
    def _ensure_exporter_project(context: RuntimeContext, cpp2il_root: Path) -> Path:
        export_root = (
            Path(context.work_dir) / ".ba-downloader" / "tools" / EXPORTER_PROJECT_NAME
        )
        export_root.mkdir(parents=True, exist_ok=True)

        project_path = export_root / f"{EXPORTER_PROJECT_NAME}.csproj"
        program_path = export_root / "Program.cs"
        libcpp2il_reference = (cpp2il_root / LIBCPP2IL_PROJECT).resolve().as_posix()

        project_path.write_text(
            _read_exporter_template(EXPORTER_CSPROJ_TEMPLATE_PATH).format(
                libcpp2il_reference=libcpp2il_reference
            ),
            encoding="utf8",
        )
        program_path.write_text(
            _read_exporter_template(EXPORTER_PROGRAM_CS_PATH),
            encoding="utf8",
        )
        return project_path


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
        "cn", lambda http_client, logger: CnMetadataDumpBackend(http_client, logger)
    )
    registry.register(
        "gl", lambda http_client, logger: LegacyIl2CppDumperBackend(http_client, logger)
    )
    registry.register(
        "jp", lambda http_client, logger: Cpp2IlDumpCsBackend(http_client, logger)
    )
    return registry


DEFAULT_DUMPER_BACKEND_REGISTRY = build_default_dumper_backend_registry()
