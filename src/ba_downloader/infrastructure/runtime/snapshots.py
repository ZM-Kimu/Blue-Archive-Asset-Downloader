from __future__ import annotations

import hashlib
import json
import re
import shutil
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from uuid import uuid4

from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.models.runtime_assets import PreparedRuntimeAssets

MANIFEST_NAME = "manifest.json"
MANIFEST_SCHEMA_VERSION = 1
RUNTIME_DIR_NAME = "Runtime"
STAGING_DIR_NAME = ".staging"
VERSION_MANIFEST_NAME = "version.json"
MANAGED_VERSION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class RuntimeSnapshotError(RuntimeError):
    """Raised when a managed runtime snapshot is invalid."""


class RuntimeSnapshotStore:
    def __init__(self, *, retained_versions: int = 2) -> None:
        if retained_versions < 1:
            raise ValueError("retained_versions must be at least 1.")
        self.retained_versions = retained_versions

    def version_root(self, context: RuntimeContext, version: str) -> Path:
        return Path(context.temp_dir) / self._validate_version(version)

    def runtime_dir(self, context: RuntimeContext, version: str) -> Path:
        return self.version_root(context, version) / RUNTIME_DIR_NAME

    def load(
        self,
        context: RuntimeContext,
        version: str,
    ) -> PreparedRuntimeAssets | None:
        runtime_dir = self.runtime_dir(context, version)
        manifest_path = runtime_dir / MANIFEST_NAME
        if not manifest_path.is_file():
            return None
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf8"))
            return self._validate_manifest(context, version, runtime_dir, manifest)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return None

    @contextmanager
    def staging_runtime(
        self,
        context: RuntimeContext,
        version: str,
    ) -> Iterator[Path]:
        with self.staging_directory(
            context,
            version,
            directory_name=RUNTIME_DIR_NAME,
        ) as directory:
            yield directory

    @contextmanager
    def staging_directory(
        self,
        context: RuntimeContext,
        version: str,
        *,
        directory_name: str,
    ) -> Iterator[Path]:
        safe_version = self._validate_version(version)
        staging_root = (
            Path(context.temp_dir) / STAGING_DIR_NAME / f"{safe_version}-{uuid4().hex}"
        )
        directory = staging_root / directory_name
        directory.mkdir(parents=True)
        try:
            yield directory
        finally:
            shutil.rmtree(staging_root, ignore_errors=True)

    def publish_directory(
        self,
        context: RuntimeContext,
        version: str,
        staged_directory: Path,
        *,
        directory_name: str,
    ) -> Path:
        destination = self.version_root(context, version) / directory_name
        destination.parent.mkdir(parents=True, exist_ok=True)
        self._replace_directory(staged_directory, destination)
        self._write_version_manifest(context, version)
        self._prune(context, current_version=version)
        return destination

    def publish(
        self,
        context: RuntimeContext,
        version: str,
        staged_runtime_dir: Path,
        *,
        binary_name: str,
        metadata_name: str,
        globalgamemanagers_name: str | None = None,
        file_roles: Mapping[str, str] | None = None,
    ) -> PreparedRuntimeAssets:
        roles = {
            "binary": binary_name,
            "metadata": metadata_name,
        }
        if globalgamemanagers_name:
            roles["globalgamemanagers"] = globalgamemanagers_name
        if file_roles:
            roles.update(file_roles)

        files = self._build_file_manifest(staged_runtime_dir)
        for role, relative_path in roles.items():
            if relative_path not in files:
                raise RuntimeSnapshotError(
                    f"Runtime snapshot is missing required {role} file "
                    f"'{relative_path}'."
                )

        manifest = {
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "region": context.region,
            "platform": context.platform,
            "release_version": version,
            "roles": roles,
            "files": files,
        }
        (staged_runtime_dir / MANIFEST_NAME).write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf8",
        )

        final_runtime_dir = self.publish_directory(
            context,
            version,
            staged_runtime_dir,
            directory_name=RUNTIME_DIR_NAME,
        )
        prepared = self.load(context, version)
        if prepared is None:
            raise RuntimeSnapshotError(
                f"Published runtime snapshot failed validation: {final_runtime_dir}."
            )
        return prepared

    def _validate_manifest(
        self,
        context: RuntimeContext,
        version: str,
        runtime_dir: Path,
        manifest: object,
    ) -> PreparedRuntimeAssets:
        if not isinstance(manifest, dict):
            raise ValueError("Runtime manifest must be an object.")
        if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
            raise ValueError("Unsupported runtime manifest schema.")
        if manifest.get("region") != context.region:
            raise ValueError("Runtime manifest region does not match.")
        if manifest.get("platform") != context.platform:
            raise ValueError("Runtime manifest platform does not match.")
        if manifest.get("release_version") != version:
            raise ValueError("Runtime manifest release version does not match.")

        roles = manifest.get("roles")
        files = manifest.get("files")
        if not isinstance(roles, dict) or not isinstance(files, dict):
            raise ValueError("Runtime manifest roles or files are invalid.")

        validated_paths: dict[str, Path] = {}
        for relative_path, metadata in files.items():
            if not isinstance(relative_path, str) or not isinstance(metadata, dict):
                raise ValueError("Runtime manifest file entry is invalid.")
            path = self._resolve_relative_path(runtime_dir, relative_path)
            if not path.is_file():
                raise ValueError(f"Runtime snapshot file is missing: {relative_path}.")
            expected_size = metadata.get("size")
            expected_hash = metadata.get("sha256")
            if (
                not isinstance(expected_size, int)
                or isinstance(expected_size, bool)
                or not isinstance(expected_hash, str)
                or re.fullmatch(r"[0-9a-f]{64}", expected_hash) is None
            ):
                raise ValueError(
                    f"Runtime manifest metadata is invalid: {relative_path}."
                )
            if path.stat().st_size != expected_size:
                raise ValueError(f"Runtime snapshot size mismatch: {relative_path}.")
            if self._sha256(path) != expected_hash:
                raise ValueError(f"Runtime snapshot hash mismatch: {relative_path}.")
            validated_paths[relative_path] = path

        def resolve_role(role: str, *, required: bool) -> Path | None:
            relative_path = roles.get(role)
            if relative_path is None and not required:
                return None
            if (
                not isinstance(relative_path, str)
                or relative_path not in validated_paths
            ):
                raise ValueError(f"Runtime manifest role is invalid: {role}.")
            return validated_paths[relative_path]

        binary_path = resolve_role("binary", required=True)
        metadata_path = resolve_role("metadata", required=True)
        assert binary_path is not None
        assert metadata_path is not None
        return PreparedRuntimeAssets(
            version=version,
            root_dir=runtime_dir,
            binary_path=binary_path,
            metadata_path=metadata_path,
            globalgamemanagers_path=resolve_role(
                "globalgamemanagers",
                required=False,
            ),
        )

    def _build_file_manifest(self, runtime_dir: Path) -> dict[str, dict[str, Any]]:
        files: dict[str, dict[str, Any]] = {}
        for path in sorted(runtime_dir.rglob("*")):
            if not path.is_file() or path.name == MANIFEST_NAME:
                continue
            if path.stat().st_size == 0:
                raise RuntimeSnapshotError(
                    f"Runtime snapshot file is empty: {path.name}."
                )
            relative_path = path.relative_to(runtime_dir).as_posix()
            files[relative_path] = {
                "size": path.stat().st_size,
                "sha256": self._sha256(path),
            }
        return files

    def _prune(self, context: RuntimeContext, *, current_version: str) -> None:
        temp_dir = Path(context.temp_dir)
        managed: list[tuple[tuple[tuple[int, int | str], ...], Path]] = []
        if not temp_dir.is_dir():
            return
        for candidate in temp_dir.iterdir():
            if not candidate.is_dir() or candidate.name.startswith("."):
                continue
            manifest_path = candidate / VERSION_MANIFEST_NAME
            if not manifest_path.is_file():
                continue
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf8"))
            except (OSError, json.JSONDecodeError):
                continue
            if (
                not isinstance(manifest, dict)
                or manifest.get("region") != context.region
                or manifest.get("platform") != context.platform
                or manifest.get("release_version") != candidate.name
            ):
                continue
            managed.append((self._version_key(candidate.name), candidate))

        managed.sort(key=lambda item: item[0], reverse=True)
        current_path = temp_dir / current_version
        keep = {current_path}
        for _, path in managed:
            if len(keep) >= self.retained_versions:
                break
            if path == current_path:
                continue
            keep.add(path)
        for _, path in managed:
            if path not in keep:
                shutil.rmtree(path)

    @staticmethod
    def _replace_directory(source: Path, destination: Path) -> None:
        backup = destination.with_name(f".{destination.name}.replaced-{uuid4().hex}")
        had_destination = destination.exists()
        if had_destination:
            destination.replace(backup)
        try:
            source.replace(destination)
        except OSError:
            if had_destination and backup.exists() and not destination.exists():
                backup.replace(destination)
            raise
        else:
            if backup.exists():
                shutil.rmtree(backup)

    def _write_version_manifest(
        self,
        context: RuntimeContext,
        version: str,
    ) -> None:
        manifest_path = self.version_root(context, version) / VERSION_MANIFEST_NAME
        temporary_path = manifest_path.with_name(
            f".{manifest_path.name}.{uuid4().hex}.tmp"
        )
        temporary_path.write_text(
            json.dumps(
                {
                    "schema_version": MANIFEST_SCHEMA_VERSION,
                    "region": context.region,
                    "platform": context.platform,
                    "release_version": version,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf8",
        )
        temporary_path.replace(manifest_path)

    @staticmethod
    def _resolve_relative_path(root: Path, relative_path: str) -> Path:
        candidate = (root / relative_path).resolve()
        try:
            candidate.relative_to(root.resolve())
        except ValueError as exc:
            raise ValueError(
                f"Runtime manifest path escapes snapshot root: {relative_path}."
            ) from exc
        return candidate

    @staticmethod
    def _validate_version(version: str) -> str:
        if not MANAGED_VERSION_PATTERN.fullmatch(version):
            raise ValueError(f"Invalid runtime release version '{version}'.")
        return version

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _version_key(version: str) -> tuple[tuple[int, int | str], ...]:
        return tuple(
            (1, int(part)) if part.isdigit() else (0, part.casefold())
            for part in re.split(r"[._-]", version)
        )
