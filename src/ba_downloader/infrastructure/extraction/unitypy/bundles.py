from __future__ import annotations

import gc
import hashlib
import json
import os
import shutil
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any
from uuid import uuid4

from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.domain.ports.execution import (
    CancellationPort,
    NeverCancelled,
    OperationCancelledError,
)
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.domain.ports.progress import (
    ProgressMeasure,
    ProgressReporterFactoryPort,
    ProgressState,
)
from ba_downloader.infrastructure.extraction.assetripper.dependencies import (
    BundleArchiveInput,
)
from ba_downloader.infrastructure.extraction.bundles import (
    BundleExtractionReport,
    bundle_extraction_lock_path,
)
from ba_downloader.infrastructure.extraction.errors import BundleExtractionError
from ba_downloader.infrastructure.files.atomic import (
    publish_staged_directory,
    recover_replaced_directory,
    write_json_atomic,
)
from ba_downloader.infrastructure.files.checksum import calculate_source_fingerprint
from ba_downloader.infrastructure.files.lock import (
    InterprocessFileLock,
    InterprocessLockBusyError,
)
from ba_downloader.infrastructure.progress import NullProgressReporterFactory

_MANIFEST_SCHEMA_VERSION = 0
_LAYOUT = "unitypy-readable"
_PROFILE = "reduced-primary"
_UNITYPY_VERSION = "1.25.0"
_SUPPORTED_TYPES = frozenset(
    {"Texture2D", "Sprite", "AudioClip", "Font", "TextAsset", "Mesh"}
)
_INVALID_NAME_CHARACTERS = frozenset('<>:"/\\|?*')
_RESERVED_WINDOWS_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{index}" for index in range(1, 10)}
    | {f"LPT{index}" for index in range(1, 10)}
)


@dataclass(frozen=True, slots=True)
class _ObjectIdentity:
    stable_id: str
    archive_id: str
    serialized_file: str
    asset_type: str
    class_id: int
    path_id: int


class _OutputBoundaryError(RuntimeError):
    pass


def unitypy_content_fingerprint() -> str:
    source = Path(__file__).resolve(strict=True)
    return calculate_source_fingerprint(
        source.parent,
        (source,),
        identities=(
            ("profile", _PROFILE),
            ("unitypy", _UNITYPY_VERSION),
        ),
    )


def _load_unitypy_environment(path: Path) -> Any:
    try:
        import UnityPy
    except ImportError as exc:
        raise BundleExtractionError(
            "UnityPy bundle handler could not be loaded; install or repair the "
            "'unitypy' optional dependency before using --bundle-handler unitypy."
        ) from exc

    return UnityPy.load(str(path))


class UnityPyBundleWorkflow:
    def __init__(
        self,
        logger: LoggerPort,
        *,
        progress_factory: ProgressReporterFactoryPort | None = None,
        cancellation: CancellationPort | None = None,
        environment_loader: Callable[[Path], Any] = _load_unitypy_environment,
    ) -> None:
        self._logger = logger
        self._progress_factory = progress_factory or NullProgressReporterFactory()
        self._cancellation = cancellation or NeverCancelled()
        self._environment_loader = environment_loader

    def run(
        self,
        context: ExecutionContext,
        inputs: Sequence[Path | BundleArchiveInput],
        *,
        concurrency: int,
        filtered: bool = False,
    ) -> BundleExtractionReport:
        if concurrency <= 0:
            raise ValueError("Bundle extraction concurrency must be positive.")
        try:
            with InterprocessFileLock(
                bundle_extraction_lock_path(context),
                operation="bundle extraction",
            ):
                return self._run_locked(context, inputs, filtered=filtered)
        except InterprocessLockBusyError as exc:
            raise BundleExtractionError(str(exc)) from exc
        except BundleExtractionError:
            raise
        except (MemoryError, OSError, RuntimeError, TypeError, ValueError) as exc:
            raise BundleExtractionError(
                f"UnityPy bundle extraction could not continue: {exc}"
            ) from exc

    def _run_locked(
        self,
        context: ExecutionContext,
        inputs: Sequence[Path | BundleArchiveInput],
        *,
        filtered: bool,
    ) -> BundleExtractionReport:
        self._cancellation.raise_if_cancelled()
        archives = self._normalize_inputs(context, inputs)
        if not archives:
            return BundleExtractionReport()

        output_root = context.workspace.extracted_bundles
        output_root.parent.mkdir(parents=True, exist_ok=True)
        recover_replaced_directory(output_root)
        self._cleanup_staging(output_root)
        manifest_path = output_root / "manifest.json"
        old_manifest = self._load_manifest(manifest_path, context)
        run_fingerprint = self._run_fingerprint(archives)
        warm_report = self._load_warm_report(
            output_root,
            old_manifest,
            run_fingerprint,
        )
        if warm_report is not None:
            return warm_report

        job_root = output_root.parent / f".bundles-unitypy-staging-{uuid4().hex}"
        staged_assets = job_root / "Assets"
        staged_assets.mkdir(parents=True)
        compatible_old = (
            old_manifest.get("layout") == _LAYOUT
            and old_manifest.get("_replace_incompatible_output") is not True
        )
        merge_old = filtered and compatible_old
        old_assets = self._manifest_assets(old_manifest) if merge_old else {}
        claimed = self._claimed_paths(old_assets)
        assets: dict[str, dict[str, object]] = {}
        processed_ids: set[str] = set()
        failures: list[dict[str, object]] = []
        archive_failures = 0
        successful_archives = 0

        initial = ProgressState(
            "Bundles",
            "extracting",
            overall=ProgressMeasure(0, len(archives), "archives"),
        )
        try:
            with self._progress_factory.create(initial) as progress:
                for archive_index, archive in enumerate(archives):
                    self._cancellation.raise_if_cancelled()
                    progress.update(
                        ProgressState(
                            "Bundles",
                            "extracting",
                            overall=ProgressMeasure(
                                archive_index,
                                len(archives),
                                "archives",
                            ),
                            item=archive.archive_id,
                            failures=len(failures),
                        )
                    )
                    archive_succeeded = False
                    environment: Any | None = None
                    descriptors: list[Any] = []
                    obj: Any | None = None
                    try:
                        environment = self._environment_loader(archive.path)
                        descriptors = self._ordered_objects(environment)
                        for object_index, obj in enumerate(descriptors, start=1):
                            self._cancellation.raise_if_cancelled()
                            asset_type = self._asset_type_name(obj)
                            progress.update(
                                ProgressState(
                                    "Bundles",
                                    "extracting",
                                    overall=ProgressMeasure(
                                        archive_index,
                                        len(archives),
                                        "archives",
                                    ),
                                    current=ProgressMeasure(
                                        object_index,
                                        len(descriptors),
                                        "objects",
                                    ),
                                    item=(
                                        f"{archive.archive_id} · {asset_type}"
                                        if asset_type
                                        else archive.archive_id
                                    ),
                                    failures=len(failures),
                                )
                            )
                            if asset_type not in _SUPPORTED_TYPES:
                                continue
                            identity = self._identity(archive.archive_id, obj)
                            if identity.stable_id in processed_ids:
                                existing = assets.get(identity.stable_id)
                                if existing is not None:
                                    self._validate_reused_identity(existing, identity)
                                continue
                            self._release_previous_paths(
                                identity.stable_id,
                                old_assets,
                                claimed,
                            )
                            try:
                                record = self._export_object(
                                    staged_assets,
                                    obj,
                                    identity,
                                    claimed,
                                )
                            except _OutputBoundaryError:
                                raise
                            except MemoryError:
                                raise
                            except Exception as exc:
                                self._restore_previous_paths(
                                    identity.stable_id,
                                    old_assets,
                                    claimed,
                                )
                                failures.append(
                                    self._failure_record(identity, exc, "object")
                                )
                                continue
                            processed_ids.add(identity.stable_id)
                            if record is not None:
                                assets[identity.stable_id] = record
                        archive_succeeded = True
                    except (OperationCancelledError, _OutputBoundaryError, MemoryError):
                        raise
                    except Exception as exc:
                        failures.append(
                            {
                                "scope": "archive",
                                "archive_id": archive.archive_id,
                                "error": self._format_exception(exc),
                            }
                        )
                    finally:
                        obj = None
                        descriptors.clear()
                        environment = None
                        gc.collect()
                    if archive_succeeded:
                        successful_archives += 1
                    else:
                        archive_failures += 1

                if successful_archives == 0:
                    raise BundleExtractionError(
                        "UnityPy could not load any requested bundle archives; "
                        "existing output was left unchanged."
                    )
                if failures and not assets and not old_assets:
                    raise BundleExtractionError(
                        "UnityPy produced no verified bundle output after extraction "
                        "failures; existing output was left unchanged."
                    )

                progress.update(
                    ProgressState(
                        "Bundles",
                        "validating",
                        overall=ProgressMeasure(
                            len(archives), len(archives), "archives"
                        ),
                        failures=len(failures),
                    )
                )
                merged_assets = self._prepare_publish_tree(
                    output_root,
                    job_root,
                    staged_assets,
                    old_assets,
                    assets,
                    processed_ids,
                    merge_old=merge_old,
                )
                manifest_assets = self._merged_manifest_assets(
                    old_assets,
                    assets,
                    processed_ids,
                    merge_old=merge_old,
                )
                manifest = self._build_manifest(
                    context,
                    archives,
                    manifest_assets,
                    failures,
                    run_fingerprint,
                )
                self._validate_staged_inventory(merged_assets, manifest_assets)
                progress.update(
                    ProgressState(
                        "Bundles",
                        "publishing",
                        overall=ProgressMeasure(
                            len(archives), len(archives), "archives"
                        ),
                        failures=len(failures),
                    )
                )
                self._publish(output_root, merged_assets, manifest)
                progress.update(
                    ProgressState(
                        "Bundles",
                        "complete",
                        overall=ProgressMeasure(
                            len(archives), len(archives), "archives"
                        ),
                        failures=len(failures),
                    )
                )
        finally:
            if job_root.exists():
                shutil.rmtree(job_root, ignore_errors=True)

        warnings: tuple[str, ...] = ()
        if failures:
            warning = (
                "[BUNDLE_EXTRACTION_PARTIAL] UnityPy published reduced bundle "
                f"output with {archive_failures} archive failures and "
                f"{len(failures) - archive_failures} object failures."
            )
            self._logger.warn(warning)
            warnings = (warning,)
        return BundleExtractionReport(
            warnings=warnings,
            total_batches=len(archives),
            succeeded_batches=successful_archives,
            failed_batches=archive_failures,
        )

    @staticmethod
    def _ordered_objects(environment: Any) -> list[Any]:
        objects = list(environment.objects)
        return sorted(objects, key=UnityPyBundleWorkflow._object_sort_key)

    @staticmethod
    def _object_sort_key(obj: Any) -> tuple[str, int, int]:
        serialized_file = str(getattr(getattr(obj, "assets_file", None), "name", ""))
        class_id = UnityPyBundleWorkflow._class_id(obj)
        path_id = int(getattr(obj, "path_id", 0))
        return (serialized_file.casefold(), class_id, path_id)

    @staticmethod
    def _asset_type_name(obj: Any) -> str:
        return str(getattr(getattr(obj, "type", None), "name", ""))

    @staticmethod
    def _class_id(obj: Any) -> int:
        raw = getattr(getattr(obj, "type", None), "value", 0)
        return int(raw)

    @classmethod
    def _identity(cls, archive_id: str, obj: Any) -> _ObjectIdentity:
        serialized_file = str(getattr(getattr(obj, "assets_file", None), "name", ""))
        asset_type = cls._asset_type_name(obj)
        class_id = cls._class_id(obj)
        path_id = int(getattr(obj, "path_id", 0))
        stable_id = cls._stable_id(
            archive_id,
            serialized_file,
            class_id,
            path_id,
        )
        return _ObjectIdentity(
            stable_id,
            archive_id,
            serialized_file,
            asset_type,
            class_id,
            path_id,
        )

    @staticmethod
    def _stable_id(
        archive_id: str,
        serialized_file: str,
        class_id: int,
        path_id: int,
    ) -> str:
        payload = json.dumps(
            [archive_id, serialized_file, class_id, path_id],
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf8")
        return hashlib.sha256(payload).hexdigest()

    def _export_object(
        self,
        assets_root: Path,
        obj: Any,
        identity: _ObjectIdentity,
        claimed: set[str],
    ) -> dict[str, object] | None:
        data = obj.read()
        raw_name = str(getattr(data, "m_Name", "") or identity.stable_id[:16])
        name = self._sanitize_name(raw_name, identity.stable_id[:16])
        outputs: list[tuple[str, bytes | str | Any]] = []
        if identity.asset_type in {"Texture2D", "Sprite"}:
            outputs.append((f"{name}.png", data.image))
        elif identity.asset_type == "AudioClip":
            for sample_name, sample in sorted(
                data.samples.items(), key=lambda item: str(item[0]).casefold()
            ):
                outputs.append(
                    (
                        self._sanitize_name(str(sample_name), identity.stable_id[:16]),
                        bytes(sample),
                    )
                )
        elif identity.asset_type == "Font":
            font_data = self._coerce_bytes(data.m_FontData)
            if not font_data:
                return None
            extension = ".otf" if font_data[:4] == b"OTTO" else ".ttf"
            outputs.append((f"{name}{extension}", font_data))
        elif identity.asset_type == "TextAsset":
            script = data.m_Script
            content = (
                bytes(script)
                if isinstance(script, (bytes, bytearray, memoryview))
                else str(script).encode("utf8", "surrogateescape")
            )
            outputs.append((name, content))
        elif identity.asset_type == "Mesh":
            mesh = data.export()
            if not isinstance(mesh, str) or not mesh:
                raise ValueError("UnityPy returned empty OBJ mesh data.")
            outputs.append((f"{name}.obj", mesh))

        if not outputs:
            if identity.asset_type == "AudioClip":
                return None
            raise ValueError("UnityPy returned no exportable content for the object.")

        files: list[dict[str, object]] = []
        allocated: list[tuple[str, Path]] = []
        try:
            for file_name, output_content in outputs:
                desired = PurePosixPath(
                    "Assets", identity.asset_type, file_name
                ).as_posix()
                relative = self._allocate_path(desired, claimed)
                claimed.add(relative.casefold())
                destination = self._asset_child(assets_root, relative)
                allocated.append((relative, destination))
                destination.parent.mkdir(parents=True, exist_ok=True)
                if hasattr(output_content, "save"):
                    output_content.save(str(destination))
                elif isinstance(output_content, str):
                    destination.write_text(
                        output_content,
                        encoding="utf8",
                        newline="",
                    )
                else:
                    destination.write_bytes(self._coerce_bytes(output_content))
                stat = destination.stat()
                if stat.st_size == 0 and identity.asset_type != "TextAsset":
                    raise ValueError("UnityPy produced an empty output file.")
                files.append(
                    {
                        "path": relative,
                        "size": stat.st_size,
                        "mtime_ns": stat.st_mtime_ns,
                    }
                )
        except BaseException:
            for relative, destination in allocated:
                destination.unlink(missing_ok=True)
                claimed.discard(relative.casefold())
            raise
        return {
            "stable_id": identity.stable_id,
            "type": identity.asset_type,
            "archive_id": identity.archive_id,
            "serialized_file": identity.serialized_file,
            "class_id": identity.class_id,
            "path_id": identity.path_id,
            "files": files,
        }

    @staticmethod
    def _coerce_bytes(value: Any) -> bytes:
        if isinstance(value, bytes):
            return value
        if isinstance(value, bytearray):
            return bytes(value)
        if isinstance(value, memoryview):
            return value.tobytes()
        if isinstance(value, list):
            return bytes(value)
        raise TypeError(
            f"UnityPy returned unsupported binary data: {type(value).__name__}"
        )

    @staticmethod
    def _sanitize_name(value: str, fallback: str) -> str:
        sanitized = "".join(
            "_"
            if character in _INVALID_NAME_CHARACTERS or ord(character) < 32
            else character
            for character in value
        ).strip(" .")
        if not sanitized:
            sanitized = fallback
        if sanitized.split(".", 1)[0].upper() in _RESERVED_WINDOWS_NAMES:
            sanitized = f"_{sanitized}"
        if len(sanitized) > 180:
            suffix = Path(sanitized).suffix
            limit = 180 - len(suffix)
            sanitized = f"{sanitized[:limit]}{suffix}"
        return sanitized

    @staticmethod
    def _allocate_path(desired: str, claimed: set[str]) -> str:
        if desired.casefold() not in claimed:
            return desired
        path = PurePosixPath(desired)
        counter = 0
        while True:
            candidate = path.with_name(f"{path.stem}_{counter}{path.suffix}").as_posix()
            if candidate.casefold() not in claimed:
                return candidate
            counter += 1

    @staticmethod
    def _safe_child(root: Path, relative: str) -> Path:
        pure = PurePosixPath(relative)
        if (
            not relative
            or pure.is_absolute()
            or any(part in {"", ".", ".."} for part in pure.parts)
            or any("\\" in part or ":" in part or "\0" in part for part in pure.parts)
        ):
            raise _OutputBoundaryError("UnityPy output path is unsafe.")
        resolved_root = root.resolve(strict=False)
        candidate = resolved_root.joinpath(*pure.parts).resolve(strict=False)
        if not candidate.is_relative_to(resolved_root):
            raise _OutputBoundaryError("UnityPy output escaped its staging root.")
        return candidate

    @classmethod
    def _asset_child(cls, assets_root: Path, relative: str) -> Path:
        parts = PurePosixPath(relative).parts
        if len(parts) < 2 or parts[0].casefold() != "assets":
            raise _OutputBoundaryError("UnityPy output is outside the Assets layout.")
        return cls._safe_child(
            assets_root,
            PurePosixPath(*parts[1:]).as_posix(),
        )

    @staticmethod
    def _validate_reused_identity(
        record: dict[str, object],
        identity: _ObjectIdentity,
    ) -> None:
        expected = (
            identity.archive_id,
            identity.serialized_file,
            identity.class_id,
            identity.path_id,
        )
        actual = (
            record.get("archive_id"),
            record.get("serialized_file"),
            record.get("class_id"),
            record.get("path_id"),
        )
        if actual != expected:
            raise _OutputBoundaryError("UnityPy stable asset identity collided.")

    @staticmethod
    def _failure_record(
        identity: _ObjectIdentity,
        exc: Exception,
        scope: str,
    ) -> dict[str, object]:
        return {
            "scope": scope,
            "stable_id": identity.stable_id,
            "archive_id": identity.archive_id,
            "serialized_file": identity.serialized_file,
            "class_id": identity.class_id,
            "path_id": identity.path_id,
            "error": UnityPyBundleWorkflow._format_exception(exc),
        }

    @staticmethod
    def _format_exception(exc: Exception) -> str:
        detail = str(exc).strip()
        return f"{type(exc).__name__}: {detail}" if detail else type(exc).__name__

    @staticmethod
    def _normalize_inputs(
        context: ExecutionContext,
        inputs: Sequence[Path | BundleArchiveInput],
    ) -> tuple[BundleArchiveInput, ...]:
        raw_root = context.workspace.raw_bundles.resolve(strict=False)
        archives: list[BundleArchiveInput] = []
        identifiers: set[str] = set()
        for item in inputs:
            if isinstance(item, BundleArchiveInput):
                resolved = item.path.resolve(strict=True)
                archive_id = item.archive_id
                checksum = item.checksum
            else:
                resolved = item.resolve(strict=True)
                checksum = None
                try:
                    archive_id = resolved.relative_to(raw_root).as_posix()
                except ValueError:
                    archive_id = resolved.name
            if archive_id.casefold() in identifiers:
                raise ValueError(f"Duplicate bundle archive identifier: {archive_id}")
            identifiers.add(archive_id.casefold())
            archives.append(
                BundleArchiveInput.from_path(
                    resolved,
                    archive_id=archive_id,
                    checksum=checksum,
                )
            )
        return tuple(sorted(archives, key=lambda item: item.archive_id.casefold()))

    def _run_fingerprint(self, archives: Sequence[BundleArchiveInput]) -> str:
        payload = {
            "content": unitypy_content_fingerprint(),
            "inputs": [
                {
                    "archive_id": archive.archive_id,
                    "size": archive.size,
                    "mtime_ns": archive.mtime_ns,
                    "checksum": (
                        {
                            "algorithm": archive.checksum.algorithm,
                            "value": archive.checksum.value,
                        }
                        if archive.checksum is not None
                        else None
                    ),
                }
                for archive in archives
            ],
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    @staticmethod
    def _empty_manifest(context: ExecutionContext) -> dict[str, object]:
        return {
            "schema_version": _MANIFEST_SCHEMA_VERSION,
            "layout": _LAYOUT,
            "region": context.region,
            "platform": context.platform,
            "resource_version": context.resource_version,
            "profile": _PROFILE,
            "content_fingerprint": unitypy_content_fingerprint(),
            "run_fingerprint": "",
            "status": "partial",
            "assets": {},
            "failures": [],
        }

    def _load_manifest(
        self,
        path: Path,
        context: ExecutionContext,
    ) -> dict[str, object]:
        if not path.exists():
            return self._empty_manifest(context)
        try:
            payload = json.loads(path.read_text(encoding="utf8"))
        except (OSError, ValueError) as exc:
            raise BundleExtractionError(
                "The bundle manifest is unreadable or corrupted; existing output "
                "was left unchanged."
            ) from exc
        if not isinstance(payload, dict):
            raise BundleExtractionError(
                "The bundle manifest is invalid; existing output was left unchanged."
            )
        if (
            payload.get("schema_version") != _MANIFEST_SCHEMA_VERSION
            or payload.get("layout") != _LAYOUT
        ):
            manifest = self._empty_manifest(context)
            manifest["_replace_incompatible_output"] = True
            return manifest
        if (
            payload.get("region") != context.region
            or payload.get("platform") != context.platform
            or not isinstance(payload.get("assets"), dict)
            or not isinstance(payload.get("failures"), list)
        ):
            raise BundleExtractionError(
                "The UnityPy bundle manifest has an invalid structure; existing "
                "output was left unchanged."
            )
        declared_paths: set[str] = set()
        for stable_id, record in self._manifest_assets(payload).items():
            if not self._valid_asset_record(stable_id, record):
                raise BundleExtractionError(
                    "The UnityPy bundle manifest contains an invalid asset record; "
                    "existing output was left unchanged."
                )
            for item in self._record_files(record):
                relative = str(item["path"])
                self._safe_child(path.parent, relative)
                path_key = relative.casefold()
                if path_key in declared_paths:
                    raise BundleExtractionError(
                        "The UnityPy bundle manifest assigns one output path to "
                        "multiple assets; existing output was left unchanged."
                    )
                declared_paths.add(path_key)
        return payload

    def _load_warm_report(
        self,
        output_root: Path,
        manifest: dict[str, object],
        run_fingerprint: str,
    ) -> BundleExtractionReport | None:
        if (
            manifest.get("layout") != _LAYOUT
            or manifest.get("profile") != _PROFILE
            or manifest.get("content_fingerprint") != unitypy_content_fingerprint()
            or manifest.get("run_fingerprint") != run_fingerprint
            or manifest.get("status") != "complete"
        ):
            return None
        try:
            self._validate_published_inventory(output_root, manifest)
        except BundleExtractionError:
            return None
        return BundleExtractionReport(total_batches=1, succeeded_batches=1)

    @staticmethod
    def _manifest_assets(
        manifest: dict[str, object],
    ) -> dict[str, dict[str, object]]:
        assets = manifest.get("assets")
        if not isinstance(assets, dict):
            return {}
        return {
            stable_id: record
            for stable_id, record in assets.items()
            if isinstance(stable_id, str) and isinstance(record, dict)
        }

    @staticmethod
    def _valid_asset_record(stable_id: str, record: dict[str, object]) -> bool:
        files = record.get("files")
        archive_id = record.get("archive_id")
        serialized_file = record.get("serialized_file")
        class_id = record.get("class_id")
        path_id = record.get("path_id")
        identity_valid = (
            isinstance(archive_id, str)
            and isinstance(serialized_file, str)
            and isinstance(class_id, int)
            and isinstance(path_id, int)
            and record.get("stable_id") == stable_id
            and record.get("type") in _SUPPORTED_TYPES
            and UnityPyBundleWorkflow._stable_id(
                archive_id,
                serialized_file,
                class_id,
                path_id,
            )
            == stable_id
        )
        return (
            identity_valid
            and isinstance(files, list)
            and all(
                isinstance(item, dict)
                and isinstance(item.get("path"), str)
                and isinstance(item.get("size"), int)
                and item["size"] >= 0
                and isinstance(item.get("mtime_ns"), int)
                for item in files
            )
            and bool(files)
        )

    @staticmethod
    def _record_files(record: dict[str, object]) -> list[dict[str, object]]:
        files = record.get("files")
        if not isinstance(files, list) or not all(
            isinstance(item, dict) for item in files
        ):
            raise _OutputBoundaryError("UnityPy asset file records are invalid.")
        return files

    @staticmethod
    def _claimed_paths(records: dict[str, dict[str, object]]) -> set[str]:
        return {
            str(item["path"]).casefold()
            for record in records.values()
            for item in UnityPyBundleWorkflow._record_files(record)
            if isinstance(item, dict) and isinstance(item.get("path"), str)
        }

    @staticmethod
    def _release_previous_paths(
        stable_id: str,
        old_assets: dict[str, dict[str, object]],
        claimed: set[str],
    ) -> None:
        record = old_assets.get(stable_id)
        if record is None:
            return
        for item in UnityPyBundleWorkflow._record_files(record):
            if isinstance(item, dict) and isinstance(item.get("path"), str):
                claimed.discard(str(item["path"]).casefold())

    @staticmethod
    def _restore_previous_paths(
        stable_id: str,
        old_assets: dict[str, dict[str, object]],
        claimed: set[str],
    ) -> None:
        record = old_assets.get(stable_id)
        if record is None:
            return
        for item in UnityPyBundleWorkflow._record_files(record):
            if isinstance(item, dict) and isinstance(item.get("path"), str):
                claimed.add(str(item["path"]).casefold())

    def _prepare_publish_tree(
        self,
        output_root: Path,
        job_root: Path,
        staged_assets: Path,
        old_assets: dict[str, dict[str, object]],
        new_assets: dict[str, dict[str, object]],
        processed_ids: set[str],
        *,
        merge_old: bool,
    ) -> Path:
        if not merge_old:
            return staged_assets
        self._validate_published_inventory(
            output_root,
            {"assets": old_assets},
        )
        merged = job_root / "MergedAssets"
        merged.mkdir()
        for stable_id, record in sorted(old_assets.items()):
            if stable_id in processed_ids:
                continue
            for item in self._record_files(record):
                assert isinstance(item, dict)
                relative = str(item["path"])
                source = self._safe_child(output_root, relative)
                destination = self._asset_child(merged, relative)
                destination.parent.mkdir(parents=True, exist_ok=True)
                self._link_or_copy(source, destination)
        for record in new_assets.values():
            for item in self._record_files(record):
                assert isinstance(item, dict)
                relative = str(item["path"])
                source = self._asset_child(staged_assets, relative)
                destination = self._asset_child(merged, relative)
                destination.parent.mkdir(parents=True, exist_ok=True)
                source.replace(destination)
        return merged

    @staticmethod
    def _merged_manifest_assets(
        old_assets: dict[str, dict[str, object]],
        new_assets: dict[str, dict[str, object]],
        processed_ids: set[str],
        *,
        merge_old: bool,
    ) -> dict[str, dict[str, object]]:
        if not merge_old:
            return dict(sorted(new_assets.items()))
        preserved = {
            stable_id: record
            for stable_id, record in old_assets.items()
            if stable_id not in processed_ids
        }
        return dict(sorted({**preserved, **new_assets}.items()))

    def _build_manifest(
        self,
        context: ExecutionContext,
        archives: Sequence[BundleArchiveInput],
        assets: dict[str, dict[str, object]],
        failures: list[dict[str, object]],
        run_fingerprint: str,
    ) -> dict[str, object]:
        return {
            "schema_version": _MANIFEST_SCHEMA_VERSION,
            "layout": _LAYOUT,
            "region": context.region,
            "platform": context.platform,
            "resource_version": context.resource_version,
            "profile": _PROFILE,
            "content_fingerprint": unitypy_content_fingerprint(),
            "run_fingerprint": run_fingerprint,
            "status": "complete" if not failures else "partial",
            "inputs": [archive.archive_id for archive in archives],
            "assets": assets,
            "failures": failures,
        }

    def _validate_staged_inventory(
        self,
        assets_root: Path,
        assets: dict[str, dict[str, object]],
    ) -> None:
        declared: set[str] = set()
        for record in assets.values():
            for item in self._record_files(record):
                assert isinstance(item, dict)
                relative = str(item["path"])
                if relative.casefold() in declared:
                    raise _OutputBoundaryError(
                        "UnityPy assigned one output path to multiple assets."
                    )
                declared.add(relative.casefold())
                path = self._asset_child(assets_root, relative)
                stat = path.stat()
                if stat.st_size != item["size"] or stat.st_mtime_ns != item["mtime_ns"]:
                    raise _OutputBoundaryError(
                        "UnityPy staged output metadata changed before publication."
                    )
        actual = {
            PurePosixPath("Assets", path.relative_to(assets_root).as_posix())
            .as_posix()
            .casefold()
            for path in assets_root.rglob("*")
            if path.is_file()
        }
        if actual != declared:
            raise _OutputBoundaryError(
                "UnityPy staged output inventory differs from its manifest."
            )

    def _validate_published_inventory(
        self,
        output_root: Path,
        manifest: dict[str, object],
    ) -> None:
        assets = self._manifest_assets(manifest)
        declared: set[str] = set()
        for record in assets.values():
            for item in self._record_files(record):
                assert isinstance(item, dict)
                relative = str(item["path"])
                path = self._safe_child(output_root, relative)
                try:
                    stat = path.stat()
                except OSError as exc:
                    raise BundleExtractionError(
                        "A published UnityPy bundle asset is missing; existing "
                        "output was left unchanged."
                    ) from exc
                if stat.st_size != item["size"] or stat.st_mtime_ns != item["mtime_ns"]:
                    raise BundleExtractionError(
                        "A published UnityPy bundle asset was modified; existing "
                        "output was left unchanged."
                    )
                declared.add(relative.casefold())
        assets_root = output_root / "Assets"
        actual = (
            {
                path.relative_to(output_root).as_posix().casefold()
                for path in assets_root.rglob("*")
                if path.is_file()
            }
            if assets_root.is_dir()
            else set()
        )
        if actual != declared:
            raise BundleExtractionError(
                "The published UnityPy Assets inventory differs from its manifest; "
                "existing output was left unchanged."
            )

    @staticmethod
    def _link_or_copy(source: Path, destination: Path) -> None:
        try:
            os.link(source, destination)
        except OSError:
            shutil.copy2(source, destination)

    @staticmethod
    def _publish(
        output_root: Path,
        staged_assets: Path,
        manifest: dict[str, object],
    ) -> None:
        publish_root = staged_assets.parent / f".publish-bundles-{uuid4().hex}"
        publish_root.mkdir()
        staged_assets.replace(publish_root / "Assets")
        write_json_atomic(
            publish_root / "manifest.json",
            manifest,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        publish_staged_directory(publish_root, output_root)

    @staticmethod
    def _cleanup_staging(output_root: Path) -> None:
        for path in output_root.parent.glob(".bundles-unitypy-staging-*"):
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
