from __future__ import annotations

import json
from collections import OrderedDict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import RLock
from typing import cast
from uuid import uuid4

from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.domain.models.storage import StorageCleanupTarget, StorageScope

PUBLIC_FILE_SCOPES = frozenset({"raw", "extracted", "indexes"})
CLEANUP_SCOPES = frozenset(
    {
        "raw",
        "extracted",
        "indexes",
        "cache",
        "temp",
        "old-snapshots",
        "failed-staging",
        "logs",
    }
)


@dataclass(frozen=True, slots=True)
class FileEntry:
    id: str
    scope: str
    relative_path: str
    name: str
    is_directory: bool
    size: int
    modified_at: str

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "scope": self.scope,
            "relative_path": self.relative_path,
            "name": self.name,
            "is_directory": self.is_directory,
            "size": self.size,
            "modified_at": self.modified_at,
        }


@dataclass(frozen=True, slots=True)
class CleanupPreview:
    token: str
    context_id: str
    expires_at: datetime
    targets: tuple[StorageCleanupTarget, ...]
    total_bytes: int


class FileBoundaryError(ValueError):
    pass


class CleanupPreviewLimitError(RuntimeError):
    pass


class FileRegistry:
    def __init__(self, *, file_limit: int = 100_000, preview_limit: int = 8) -> None:
        self._lock = RLock()
        self._file_limit = file_limit
        self._preview_limit = preview_limit
        self._files: OrderedDict[str, tuple[str, Path, Path]] = OrderedDict()
        self._file_ids: dict[tuple[str, str, str], str] = {}
        self._previews: dict[str, CleanupPreview] = {}

    def roots(self, context: ExecutionContext) -> dict[str, Path]:
        base = Path(context.workspace.base).resolve()
        state = base / ".state"
        return {
            "raw": Path(context.workspace.raw).resolve(),
            "extracted": Path(context.workspace.extracted).resolve(),
            "indexes": base / "indexes",
            "cache": state / "cache",
            "temp": state / "temp",
            "logs": state / "logs",
            "old-snapshots": state,
            "failed-staging": state,
        }

    def list_entries(
        self, context: ExecutionContext, scope: str, relative_path: str = ""
    ) -> list[FileEntry]:
        if scope not in PUBLIC_FILE_SCOPES:
            raise FileBoundaryError(f"Unknown public file scope '{scope}'.")
        root = self.roots(context)[scope]
        directory = self._resolve_within(root, relative_path)
        if not directory.exists():
            return []
        if not directory.is_dir():
            raise FileBoundaryError("Requested path is not a directory.")
        paths = sorted(
            directory.iterdir(),
            key=lambda item: (not item.is_dir(), item.name.casefold()),
        )
        return [self._register(scope, root, path) for path in paths]

    def resolve(self, file_id: str, context: ExecutionContext) -> Path:
        with self._lock:
            try:
                scope, root, path = self._files[file_id]
            except KeyError as exc:
                raise KeyError(f"Unknown file '{file_id}'.") from exc
            if scope not in PUBLIC_FILE_SCOPES or root != self.roots(context)[scope]:
                raise KeyError(f"Unknown file '{file_id}'.")
            self._files.move_to_end(file_id)
        resolved = path.resolve()
        self._ensure_within(root, resolved)
        return resolved

    def metadata(self, file_id: str, context: ExecutionContext) -> FileEntry:
        path = self.resolve(file_id, context)
        with self._lock:
            scope, root, _ = self._files[file_id]
        return self._entry(file_id, scope, root, path)

    def usage(self, context: ExecutionContext) -> dict[str, object]:
        result: dict[str, object] = {}
        for scope in sorted(PUBLIC_FILE_SCOPES):
            root = self.roots(context)[scope]
            size = (
                sum(path.stat().st_size for path in root.rglob("*") if path.is_file())
                if root.is_dir()
                else 0
            )
            result[scope] = {"path": str(root), "bytes": size}
        return result

    def preview_cleanup(
        self, context: ExecutionContext, context_id: str, scopes: Sequence[str]
    ) -> CleanupPreview:
        targets: list[StorageCleanupTarget] = []
        total_bytes = 0
        for scope in scopes:
            if scope not in CLEANUP_SCOPES:
                raise FileBoundaryError(f"Unknown cleanup category '{scope}'.")
            root = self.roots(context)[scope]
            for path in self._cleanup_paths(context, scope, root):
                resolved = path.resolve()
                self._ensure_within(root, resolved)
                if resolved.is_file():
                    total_bytes += resolved.stat().st_size
                targets.append(self._cleanup_target(scope, root, resolved))
        with self._lock:
            self._purge_expired_previews()
            if len(self._previews) >= self._preview_limit:
                raise CleanupPreviewLimitError(
                    "The maximum number of active cleanup previews has been reached."
                )
            preview = CleanupPreview(
                uuid4().hex,
                context_id,
                datetime.now(UTC) + timedelta(minutes=5),
                tuple(targets),
                total_bytes,
            )
            self._previews[preview.token] = preview
        return preview

    def consume_preview(self, token: str, context_id: str) -> CleanupPreview:
        with self._lock:
            self._purge_expired_previews()
            try:
                preview = self._previews.pop(token)
            except KeyError as exc:
                raise KeyError("Unknown cleanup preview token.") from exc
        if preview.context_id != context_id:
            raise FileBoundaryError("Cleanup preview belongs to another context.")
        return preview

    def _cleanup_paths(
        self, context: ExecutionContext, scope: str, root: Path
    ) -> list[Path]:
        if scope == "indexes":
            return self._descendants(root)
        if scope in {"old-snapshots", "failed-staging"}:
            if scope == "failed-staging":
                staging_roots = [
                    path
                    for path in root.rglob("*")
                    if path.is_dir()
                    and (path.name == ".staging" or path.name.endswith(".staging"))
                ]
                return self._expand_roots(staging_roots)
            runtime_store = root / "runtime"
            runtime_roots = (
                [
                    path
                    for path in runtime_store.iterdir()
                    if path.is_dir()
                    and path.name != context.resource_version
                    and (path / "version.json").is_file()
                ]
                if runtime_store.is_dir()
                else []
            )
            schema_store = root / "schema"
            snapshots = schema_store / "snapshots"
            current_schema = self._current_generation(schema_store)
            schema_roots = (
                [
                    path
                    for path in snapshots.iterdir()
                    if path.is_dir() and path.name != current_schema
                ]
                if snapshots.is_dir()
                else []
            )
            return self._expand_roots(runtime_roots + schema_roots)
        if scope == "temp":
            managed = (
                {
                    path
                    for path in root.iterdir()
                    if path.is_dir()
                    and ((path / "version.json").is_file() or path.name == ".staging")
                }
                if root.is_dir()
                else set()
            )
            return [
                path
                for path in self._descendants(root)
                if not any(parent in managed for parent in (path, *path.parents))
            ]
        return self._descendants(root)

    @staticmethod
    def _expand_roots(roots: Sequence[Path]) -> list[Path]:
        paths: list[Path] = []
        for root in roots:
            paths.extend(root.rglob("*"))
            paths.append(root)
        return sorted(paths, key=lambda path: len(path.parts), reverse=True)

    @staticmethod
    def _current_generation(store: Path) -> str | None:
        try:
            data = json.loads((store / "current.json").read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return None
        for key in ("snapshot_id", "generation", "version", "directory"):
            value = data.get(key) if isinstance(data, dict) else None
            if isinstance(value, str):
                return Path(value).name
        return None

    @staticmethod
    def _descendants(root: Path) -> list[Path]:
        return (
            sorted(root.rglob("*"), key=lambda path: len(path.parts), reverse=True)
            if root.is_dir()
            else []
        )

    def _register(self, scope: str, root: Path, path: Path) -> FileEntry:
        resolved = path.resolve()
        self._ensure_within(root, resolved)
        key = (scope, str(root), resolved.relative_to(root).as_posix())
        with self._lock:
            file_id = self._file_ids.get(key)
            if file_id is None:
                file_id = uuid4().hex
                self._file_ids[key] = file_id
                self._files[file_id] = (scope, root, resolved)
                while len(self._files) > self._file_limit:
                    _, (old_scope, old_root, old_path) = self._files.popitem(last=False)
                    self._file_ids.pop(
                        (
                            old_scope,
                            str(old_root),
                            old_path.relative_to(old_root).as_posix(),
                        ),
                        None,
                    )
            else:
                self._files.move_to_end(file_id)
        return self._entry(file_id, scope, root, resolved)

    @staticmethod
    def _resolve_within(root: Path, relative_path: str) -> Path:
        if Path(relative_path).is_absolute():
            raise FileBoundaryError("File path must be relative to its scope.")
        candidate = (root / relative_path).resolve()
        FileRegistry._ensure_within(root, candidate)
        return candidate

    @staticmethod
    def _ensure_within(root: Path, candidate: Path) -> None:
        try:
            candidate.relative_to(root.resolve())
        except ValueError as exc:
            raise FileBoundaryError("File path escapes its configured scope.") from exc

    @staticmethod
    def _cleanup_target(scope: str, root: Path, path: Path) -> StorageCleanupTarget:
        return StorageCleanupTarget(
            cast(StorageScope, scope),
            path.relative_to(root).as_posix(),
            "directory" if path.is_dir() else "file",
        )

    @staticmethod
    def _entry(file_id: str, scope: str, root: Path, path: Path) -> FileEntry:
        stat = path.stat()
        return FileEntry(
            file_id,
            scope,
            path.relative_to(root).as_posix(),
            path.name,
            path.is_dir(),
            stat.st_size if path.is_file() else 0,
            datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
        )

    def _purge_expired_previews(self) -> None:
        now = datetime.now(UTC)
        for token, preview in tuple(self._previews.items()):
            if preview.expires_at <= now:
                self._previews.pop(token, None)
