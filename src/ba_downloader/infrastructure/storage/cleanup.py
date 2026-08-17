import json
from pathlib import Path

from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.models.storage import StorageCleanupTarget


class StorageBoundaryError(ValueError):
    pass


class BoundedStorageCleanup:
    def delete(
        self,
        context: RuntimeContext,
        target: StorageCleanupTarget,
    ) -> Path:
        root = self._roots(context)[target.scope]
        candidate = (root / target.relative_path).resolve()
        self._ensure_within(root, candidate)
        self._validate_category(context, root, candidate, target.scope)
        if target.expected_type == "file":
            if not candidate.is_file():
                raise StorageBoundaryError("Cleanup target is no longer a file.")
            candidate.unlink()
        else:
            if not candidate.is_dir():
                raise StorageBoundaryError("Cleanup target is no longer a directory.")
            candidate.rmdir()
        return candidate

    @staticmethod
    def _roots(context: RuntimeContext) -> dict[str, Path]:
        base = Path(context.work_dir).resolve()
        state = base / ".state"
        return {
            "raw": Path(context.raw_dir).resolve(),
            "extracted": Path(context.extract_dir).resolve(),
            "indexes": base / "indexes",
            "cache": state / "cache",
            "temp": state / "temp",
            "logs": state / "logs",
            "old-snapshots": state,
            "failed-staging": state,
        }

    @staticmethod
    def _validate_category(
        context: RuntimeContext, root: Path, candidate: Path, scope: str
    ) -> None:
        relative = candidate.relative_to(root.resolve())
        if scope == "failed-staging" and not any(
            part.endswith(".staging") for part in relative.parts
        ):
            raise StorageBoundaryError("Cleanup target is not failed staging.")
        if scope != "old-snapshots" or len(relative.parts) < 2:
            return
        if relative.parts[0] == "runtime":
            if relative.parts[1] == context.version:
                raise StorageBoundaryError(
                    "Current runtime snapshot cannot be deleted."
                )
            return
        if relative.parts[:2] != ("schema", "snapshots") or len(relative.parts) < 3:
            raise StorageBoundaryError("Cleanup target is not an old snapshot.")
        store = root / "schema"
        try:
            data = json.loads((store / "current.json").read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            data = {}
        current_values = {
            Path(value).name
            for key in ("snapshot_id", "generation", "version", "directory")
            if isinstance((value := data.get(key)), str)
        }
        if relative.parts[2] in current_values:
            raise StorageBoundaryError("Current snapshot cannot be deleted.")

    @staticmethod
    def _ensure_within(root: Path, candidate: Path) -> None:
        try:
            candidate.relative_to(root.resolve())
        except ValueError as exc:
            raise StorageBoundaryError(
                "Cleanup target escapes its configured scope."
            ) from exc
