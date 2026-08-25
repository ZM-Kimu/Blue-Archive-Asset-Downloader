from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Iterator, Mapping
from contextlib import contextmanager, suppress
from dataclasses import asdict, dataclass
from pathlib import Path
from uuid import uuid4

from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.domain.models.runtime_assets import PreparedRuntimeAssets
from ba_downloader.domain.models.schema import SchemaPurpose
from ba_downloader.domain.ports.execution import CancellationPort, NeverCancelled
from ba_downloader.infrastructure.files.atomic import write_json_atomic
from ba_downloader.infrastructure.files.checksum import (
    calculate_sha256,
    calculate_source_fingerprint,
)

SCHEMA_MANIFEST_VERSION = 0


def _schema_tool_fingerprints() -> dict[str, str]:
    package_root = Path(__file__).resolve().parents[2]
    schema_root = package_root / "infrastructure" / "schema"
    template = (
        package_root
        / "infrastructure"
        / "tools"
        / "templates"
        / "dumpcs_exporter.Program.cs"
    )
    flatbuffer_sources = tuple((schema_root / "flatbuffer").rglob("*.py"))
    memorypack_sources = (
        *(schema_root / "memorypack").rglob("*.py"),
        template,
    )
    workflow_sources = (schema_root / "workflow.py", Path(__file__).resolve())
    return {
        "flatbuffer_generator": calculate_source_fingerprint(
            package_root,
            flatbuffer_sources,
            identities=(("tool", "flatbuffer-generator"),),
        ),
        "memorypack_generator": calculate_source_fingerprint(
            package_root,
            memorypack_sources,
            identities=(("tool", "memorypack-generator"),),
        ),
        "schema_workflow": calculate_source_fingerprint(
            package_root,
            workflow_sources,
            identities=(("tool", "schema-workflow"),),
        ),
    }


def schema_state_root(context: ExecutionContext) -> Path:
    return context.workspace.schema_state


class SchemaSnapshotError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class SchemaArtifact:
    path: str
    size: int
    sha256: str


@dataclass(frozen=True, slots=True)
class SchemaInput:
    role: str
    path: str
    size: int
    sha256: str


@dataclass(frozen=True, slots=True)
class SchemaSnapshotManifest:
    schema_version: int
    fingerprint: str
    region: str
    platform: str
    runtime_version: str
    status: str
    purpose: str
    target_types: tuple[str, ...]
    inputs: tuple[SchemaInput, ...]
    tool_fingerprints: tuple[tuple[str, str], ...]
    artifacts: tuple[SchemaArtifact, ...]


@dataclass(frozen=True, slots=True)
class SchemaSnapshot:
    root: Path
    manifest: SchemaSnapshotManifest


class SchemaSnapshotStore:
    def __init__(
        self,
        *,
        retained_snapshots: int = 2,
        tool_fingerprints: Mapping[str, str] | None = None,
        cancellation: CancellationPort | None = None,
    ) -> None:
        if retained_snapshots < 1:
            raise ValueError("retained_snapshots must be at least 1.")
        self.retained_snapshots = retained_snapshots
        self.tool_fingerprints = tuple(
            sorted((tool_fingerprints or _schema_tool_fingerprints()).items())
        )
        self.cancellation = cancellation or NeverCancelled()

    def state_root(self, context: ExecutionContext) -> Path:
        return schema_state_root(context)

    def snapshots_root(
        self,
        context: ExecutionContext,
        purpose: SchemaPurpose = SchemaPurpose.FULL,
    ) -> Path:
        return self.state_root(context) / purpose.value / "snapshots"

    def staging_root(
        self,
        context: ExecutionContext,
        purpose: SchemaPurpose = SchemaPurpose.FULL,
    ) -> Path:
        return self.state_root(context) / purpose.value / ".staging"

    def current_pointer(
        self,
        context: ExecutionContext,
        purpose: SchemaPurpose = SchemaPurpose.FULL,
    ) -> Path:
        return self.state_root(context) / purpose.value / "current.json"

    def fingerprint(
        self,
        context: ExecutionContext,
        runtime: PreparedRuntimeAssets,
        purpose: SchemaPurpose = SchemaPurpose.FULL,
        target_types: tuple[str, ...] = (),
    ) -> str:
        inputs = self._runtime_inputs(runtime)
        payload = {
            "schema_version": SCHEMA_MANIFEST_VERSION,
            "region": context.region,
            "platform": context.platform,
            "runtime_version": runtime.version,
            "inputs": [asdict(item) for item in inputs],
            "tool_fingerprints": dict(self.tool_fingerprints),
            "purpose": purpose.value,
            "target_types": sorted(target_types),
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()

    @contextmanager
    def staging(
        self,
        context: ExecutionContext,
        fingerprint: str,
        purpose: SchemaPurpose = SchemaPurpose.FULL,
    ) -> Iterator[Path]:
        root = self.begin_staging(context, fingerprint, purpose)
        try:
            yield root
        finally:
            self.discard_staging(root)

    def begin_staging(
        self,
        context: ExecutionContext,
        fingerprint: str,
        purpose: SchemaPurpose = SchemaPurpose.FULL,
    ) -> Path:
        root = self.staging_root(context, purpose) / f"{fingerprint}-{uuid4().hex}"
        root.mkdir(parents=True, exist_ok=False)
        return root

    @staticmethod
    def discard_staging(root: Path) -> None:
        shutil.rmtree(root, ignore_errors=True)
        with suppress(OSError):
            root.parent.rmdir()

    def publish(
        self,
        context: ExecutionContext,
        runtime: PreparedRuntimeAssets,
        fingerprint: str,
        staging: Path,
        purpose: SchemaPurpose = SchemaPurpose.FULL,
        target_types: tuple[str, ...] = (),
    ) -> SchemaSnapshot:
        self.cancellation.raise_if_cancelled()
        if fingerprint != self.fingerprint(context, runtime, purpose, target_types):
            raise SchemaSnapshotError("Schema snapshot fingerprint is stale.")
        artifacts = self._artifact_manifest(staging)
        required = {"schemas/flatbuffers", "diagnostics"}
        if purpose is SchemaPurpose.FULL:
            required.update({"dumps/dump.cs", "schemas/memorypack"})
        paths = {item.path for item in artifacts}
        directories = {
            path.relative_to(staging).as_posix()
            for path in staging.rglob("*")
            if path.is_dir()
        }
        if not required.issubset(paths | directories):
            raise SchemaSnapshotError(
                "Schema generation did not produce a complete snapshot."
            )
        manifest = SchemaSnapshotManifest(
            schema_version=SCHEMA_MANIFEST_VERSION,
            fingerprint=fingerprint,
            region=context.region,
            platform=context.platform,
            runtime_version=runtime.version,
            status="complete",
            purpose=purpose.value,
            target_types=tuple(sorted(target_types)),
            inputs=self._runtime_inputs(runtime),
            tool_fingerprints=self.tool_fingerprints,
            artifacts=artifacts,
        )
        self._write_manifest(staging / "manifest.json", manifest)
        destination = self.snapshots_root(context, purpose) / fingerprint
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            shutil.rmtree(staging, ignore_errors=True)
        else:
            staging.replace(destination)
        write_json_atomic(
            self.current_pointer(context, purpose),
            {
                "schema_version": SCHEMA_MANIFEST_VERSION,
                "snapshot_id": fingerprint,
                "purpose": purpose.value,
            },
            indent=2,
            sort_keys=True,
        )
        self._prune(context, fingerprint, purpose)
        return SchemaSnapshot(destination, manifest)

    def load(
        self,
        context: ExecutionContext,
        fingerprint: str,
        purpose: SchemaPurpose = SchemaPurpose.FULL,
    ) -> SchemaSnapshot | None:
        root = self.snapshots_root(context, purpose) / fingerprint
        try:
            payload = json.loads((root / "manifest.json").read_text(encoding="utf8"))
            manifest = self._parse_manifest(payload)
            if (
                manifest.fingerprint != fingerprint
                or manifest.schema_version != SCHEMA_MANIFEST_VERSION
                or manifest.region != context.region
                or manifest.platform != context.platform
                or manifest.status != "complete"
                or manifest.purpose != purpose.value
            ):
                return None
            for artifact in manifest.artifacts:
                self.cancellation.raise_if_cancelled()
                path = self._resolve(root, artifact.path)
                if (
                    not path.is_file()
                    or path.stat().st_size != artifact.size
                    or calculate_sha256(
                        path,
                        on_chunk=self.cancellation.raise_if_cancelled,
                    )
                    != artifact.sha256
                ):
                    return None
            return SchemaSnapshot(root, manifest)
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            return None

    def cleanup(
        self,
        context: ExecutionContext,
        purpose: SchemaPurpose = SchemaPurpose.FULL,
    ) -> None:
        shutil.rmtree(self.staging_root(context, purpose), ignore_errors=True)
        current = ""
        try:
            payload = json.loads(
                self.current_pointer(context, purpose).read_text(encoding="utf8")
            )
            if isinstance(payload.get("snapshot_id"), str):
                current = payload["snapshot_id"]
        except (
            OSError,
            KeyError,
            TypeError,
            AttributeError,
            json.JSONDecodeError,
        ):
            pass
        self._prune(context, current, purpose)

    def _runtime_inputs(
        self,
        runtime: PreparedRuntimeAssets,
    ) -> tuple[SchemaInput, ...]:
        candidates = (
            ("binary", runtime.binary_path),
            ("metadata", runtime.metadata_path),
            ("globalgamemanagers", runtime.globalgamemanagers_path),
        )
        result: list[SchemaInput] = []
        for role, path in candidates:
            if path is None:
                continue
            self.cancellation.raise_if_cancelled()
            if not path.is_file():
                raise SchemaSnapshotError(f"Schema input is missing: {role}.")
            recorded = runtime.file_fingerprints.get(path.name)
            if (
                isinstance(recorded, dict)
                and recorded.get("size") == path.stat().st_size
                and isinstance(recorded.get("sha256"), str)
            ):
                result.append(
                    SchemaInput(
                        role,
                        path.name,
                        path.stat().st_size,
                        str(recorded["sha256"]),
                    )
                )
                continue
            result.append(
                SchemaInput(
                    role,
                    path.name,
                    path.stat().st_size,
                    calculate_sha256(
                        path,
                        on_chunk=self.cancellation.raise_if_cancelled,
                    ),
                )
            )
        return tuple(result)

    def _artifact_manifest(self, root: Path) -> tuple[SchemaArtifact, ...]:
        result: list[SchemaArtifact] = []
        for path in sorted(root.rglob("*")):
            self.cancellation.raise_if_cancelled()
            if not path.is_file() or path.name == "manifest.json":
                continue
            relative = path.relative_to(root).as_posix()
            result.append(
                SchemaArtifact(
                    relative,
                    path.stat().st_size,
                    calculate_sha256(
                        path,
                        on_chunk=self.cancellation.raise_if_cancelled,
                    ),
                )
            )
        return tuple(result)

    def _prune(
        self,
        context: ExecutionContext,
        current: str,
        purpose: SchemaPurpose = SchemaPurpose.FULL,
    ) -> None:
        root = self.snapshots_root(context, purpose)
        if not root.is_dir():
            return
        candidates = sorted(
            (path for path in root.iterdir() if path.is_dir()),
            key=lambda path: path.stat().st_mtime_ns,
            reverse=True,
        )
        keep: set[Path] = set()
        current_path = root / current
        if current_path.is_dir():
            keep.add(current_path)
        for path in candidates:
            if len(keep) >= self.retained_snapshots:
                break
            keep.add(path)
        for path in candidates:
            if path not in keep:
                shutil.rmtree(path)

    @staticmethod
    def _parse_manifest(payload: object) -> SchemaSnapshotManifest:
        if not isinstance(payload, dict):
            raise ValueError("Schema snapshot manifest must be an object.")
        inputs = tuple(SchemaInput(**item) for item in payload["inputs"])
        artifacts = tuple(SchemaArtifact(**item) for item in payload["artifacts"])
        tool_fingerprints = tuple(
            sorted(
                (str(key), str(value))
                for key, value in payload["tool_fingerprints"].items()
            )
        )
        return SchemaSnapshotManifest(
            schema_version=int(payload["schema_version"]),
            fingerprint=str(payload["fingerprint"]),
            region=str(payload["region"]),
            platform=str(payload["platform"]),
            runtime_version=str(payload["runtime_version"]),
            status=str(payload["status"]),
            purpose=str(payload["purpose"]),
            target_types=tuple(str(item) for item in payload["target_types"]),
            inputs=inputs,
            tool_fingerprints=tool_fingerprints,
            artifacts=artifacts,
        )

    @staticmethod
    def _write_manifest(path: Path, manifest: SchemaSnapshotManifest) -> None:
        payload = asdict(manifest)
        payload["tool_fingerprints"] = dict(manifest.tool_fingerprints)
        write_json_atomic(path, payload, indent=2, sort_keys=True)

    @staticmethod
    def _resolve(root: Path, relative: str) -> Path:
        path = (root / relative).resolve()
        try:
            path.relative_to(root.resolve())
        except ValueError as exc:
            raise ValueError(
                f"Schema artifact escapes snapshot root: {relative}."
            ) from exc
        return path
