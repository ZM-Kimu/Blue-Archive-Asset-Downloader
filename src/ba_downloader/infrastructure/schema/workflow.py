from __future__ import annotations

import re
import shutil
from contextlib import suppress
from pathlib import Path
from uuid import uuid4

from ba_downloader.domain.exceptions import OperationCancelledError
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.models.runtime_assets import PreparedRuntimeAssets
from ba_downloader.domain.models.schema import PreparedSchemaSnapshot, SchemaPurpose
from ba_downloader.domain.ports.execution import CancellationPort, NeverCancelled
from ba_downloader.domain.ports.extract import SchemaWorkflowPort
from ba_downloader.domain.ports.http import HttpClientPort
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.infrastructure.schema.flatbuffer.descriptors import (
    FlatBufferEnumDescriptor,
    FlatBufferTypeDescriptor,
)
from ba_downloader.infrastructure.schema.flatbuffer.generator import (
    CompileFlatBufferToPython,
)
from ba_downloader.infrastructure.schema.flatbuffer.parser import FlatBufferCSParser
from ba_downloader.infrastructure.schema.memorypack.generator import (
    CompileMemoryPackToPython,
)
from ba_downloader.infrastructure.schema.memorypack.parser import MemoryPackCSParser
from ba_downloader.infrastructure.schema.memorypack.supplemental import (
    SupplementalMemoryPackFormatterBuilder,
)
from ba_downloader.infrastructure.schema.snapshots import (
    SchemaSnapshot,
    SchemaSnapshotStore,
)
from ba_downloader.infrastructure.storage.workspace_paths import (
    extracted_dumps_root,
    extracted_schema_root,
)
from ba_downloader.infrastructure.tools.dump_backend import (
    BackendFactory,
)


class SchemaWorkflow(SchemaWorkflowPort):
    DUMP_PATH = "Dumps"
    CHARACTER_INDEX_TARGET_TYPES = (
        "CharacterExcel",
        "LocalizeCharProfileExcel",
        "ScenarioCharacterNameExcel",
    )

    def __init__(
        self,
        http_client: HttpClientPort,
        logger: LoggerPort,
        dumper_backend_factory: BackendFactory | None = None,
        cancellation: CancellationPort | None = None,
        snapshot_store: SchemaSnapshotStore | None = None,
    ) -> None:
        self.http_client = http_client
        self.logger = logger
        self.dumper_backend_factory = dumper_backend_factory
        self.cancellation = cancellation or NeverCancelled()
        self.snapshot_store = snapshot_store or SchemaSnapshotStore(
            cancellation=self.cancellation
        )
        self._staging_root: Path | None = None
        self._staged_context: RuntimeContext | None = None
        self._runtime_assets: PreparedRuntimeAssets | None = None
        self._fingerprint = ""
        self._cached_snapshot: SchemaSnapshot | None = None
        self._purpose = SchemaPurpose.FULL
        self._target_types: tuple[str, ...] = ()

    def dump(
        self,
        context: RuntimeContext,
        runtime_assets: PreparedRuntimeAssets,
        purpose: SchemaPurpose = SchemaPurpose.FULL,
    ) -> None:
        self.cancellation.raise_if_cancelled()
        if self.dumper_backend_factory is None:
            raise ValueError(
                "SchemaWorkflow.dump requires a configured dumper backend factory."
            )
        target_types = (
            self.CHARACTER_INDEX_TARGET_TYPES
            if purpose is SchemaPurpose.CHARACTER_INDEX
            else ()
        )
        self._purpose = purpose
        self._target_types = target_types
        self.snapshot_store.cleanup(context, purpose)
        fingerprint = self.snapshot_store.fingerprint(
            context,
            runtime_assets,
            purpose,
            target_types,
        )
        cached = self.snapshot_store.load(context, fingerprint, purpose)
        if cached is not None:
            self._cached_snapshot = cached
            self._runtime_assets = runtime_assets
            self._fingerprint = fingerprint
            if purpose is SchemaPurpose.FULL:
                self._materialize_snapshot(context, cached)
            return

        staging_root = self.snapshot_store.begin_staging(context, fingerprint, purpose)
        staged_context = context.with_updates(
            extract_dir=str(staging_root), workspace_mode="v3"
        )
        self._staging_root = staging_root
        self._staged_context = staged_context
        self._runtime_assets = runtime_assets
        self._fingerprint = fingerprint
        self._cached_snapshot = None
        (staging_root / "diagnostics").mkdir()
        extract_path = extracted_dumps_root(staged_context)
        backend = self.dumper_backend_factory(
            self.http_client,
            self.logger,
            self.cancellation,
        )
        try:
            backend.dump(
                staged_context,
                str(extract_path.resolve()),
                runtime_assets,
            )
            self.cancellation.raise_if_cancelled()
        except BaseException:
            self._discard_staging()
            raise

    def _validate_generated_python(self, output_dir: Path, label: str) -> None:
        for python_file in sorted(output_dir.rglob("*.py")):
            self.cancellation.raise_if_cancelled()
            try:
                source = python_file.read_text(encoding="utf8")
                compile(source, str(python_file), "exec")
            except (OSError, SyntaxError) as exc:
                raise SyntaxError(
                    f"Generated {label} module is invalid: {python_file}. "
                    f"Compiler details: {exc}"
                ) from exc

    def _generate_memorypack_data(
        self, dump_cs_file_path: str, context: RuntimeContext
    ) -> None:
        memorypack_data_dir = extracted_schema_root(context, "memorypack")
        try:
            self.cancellation.raise_if_cancelled()
            self.logger.info("Generating MemoryPackData schema files...")
            memorypack_parser = MemoryPackCSParser(dump_cs_file_path)
            descriptors = memorypack_parser.parse_types()
            enums = memorypack_parser.parse_enums()
            memorypack_compiler = CompileMemoryPackToPython(
                descriptors,
                str(memorypack_data_dir),
                enums,
            )
            memorypack_compiler.create_schema_files()
            self._validate_generated_python(memorypack_data_dir, "MemoryPackData")
            self.cancellation.raise_if_cancelled()
        except OperationCancelledError:
            raise
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self.logger.warn(f"MemoryPackData generation failed: {exc}")

    def _generate_supplemental_memorypack_formatters(
        self,
        dump_cs_file_path: str,
        context: RuntimeContext,
    ) -> None:
        dumps_dir = extracted_dumps_root(context)
        memorypack_data_dir = extracted_schema_root(context, "memorypack")
        sidecar_path = dumps_dir / "memorypack_formatters.json"
        try:
            self.cancellation.raise_if_cancelled()
            self.logger.info("Building MemoryPack semantic formatter sidecar...")
            SupplementalMemoryPackFormatterBuilder(
                dump_cs_path=dump_cs_file_path,
                memorypack_data_dir=memorypack_data_dir,
                sidecar_path=sidecar_path,
            ).build()
            self.cancellation.raise_if_cancelled()
        except OperationCancelledError:
            raise
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self.logger.warn(
                f"MemoryPack semantic formatter sidecar generation failed: {exc}"
            )

    def compile(
        self,
        context: RuntimeContext,
        purpose: SchemaPurpose = SchemaPurpose.FULL,
    ) -> PreparedSchemaSnapshot | None:
        if purpose is not self._purpose:
            raise ValueError(
                "Schema compile purpose does not match schema dump purpose."
            )
        if self._cached_snapshot is not None:
            prepared = self._prepared_snapshot(self._cached_snapshot)
            self._reset_state()
            return prepared
        compile_context = self._staged_context or context
        try:
            self._compile(compile_context)
            if self._staged_context is not None:
                return self._publish_staging(context)
        except BaseException:
            self._discard_staging()
            raise
        return None

    def _compile(self, context: RuntimeContext) -> None:
        self.cancellation.raise_if_cancelled()
        dump_cs_file_path = str(extracted_dumps_root(context) / "dump.cs")
        flatbuffer_data_dir = extracted_schema_root(context, "flatbuffer")

        self.logger.info("Parsing dump.cs...")
        parser = FlatBufferCSParser(dump_cs_file_path)
        enums = parser.parse_enums()
        descriptors = parser.parse_types()
        if self._purpose is SchemaPurpose.CHARACTER_INDEX:
            descriptors, enums = self._select_flatbuffer_closure(
                descriptors,
                enums,
                self._target_types,
            )
        self.cancellation.raise_if_cancelled()

        self.logger.info("Generating FlatBufferData schema files...")
        compiler = CompileFlatBufferToPython(
            descriptors,
            str(flatbuffer_data_dir),
            enums,
        )
        compiler.create_schema_files()
        self.cancellation.raise_if_cancelled()
        self._validate_generated_python(flatbuffer_data_dir, "FlatBufferData")
        if self._purpose is SchemaPurpose.FULL:
            self._generate_memorypack_data(dump_cs_file_path, context)
            self._generate_supplemental_memorypack_formatters(
                dump_cs_file_path, context
            )
        else:
            Path(dump_cs_file_path).unlink(missing_ok=True)
            with suppress(OSError):
                Path(dump_cs_file_path).parent.rmdir()
        self.cancellation.raise_if_cancelled()

    def _publish_staging(self, context: RuntimeContext) -> PreparedSchemaSnapshot:
        staging_root = self._staging_root
        runtime_assets = self._runtime_assets
        if staging_root is None or runtime_assets is None or not self._fingerprint:
            raise RuntimeError("Schema staging context is missing.")
        snapshot = self.snapshot_store.publish(
            context,
            runtime_assets,
            self._fingerprint,
            staging_root,
            self._purpose,
            self._target_types,
        )
        if self._purpose is SchemaPurpose.FULL:
            self._materialize_snapshot(context, snapshot)
        prepared = self._prepared_snapshot(snapshot)
        self._reset_state()
        return prepared

    def _prepared_snapshot(self, snapshot: SchemaSnapshot) -> PreparedSchemaSnapshot:
        purpose = SchemaPurpose(snapshot.manifest.purpose)
        return PreparedSchemaSnapshot(
            purpose=purpose,
            root_dir=snapshot.root,
            flatbuffer_path=snapshot.root / "schemas" / "flatbuffers",
            memorypack_path=(
                snapshot.root / "schemas" / "memorypack"
                if purpose is SchemaPurpose.FULL
                else None
            ),
            dumps_path=(
                snapshot.root / "dumps" if purpose is SchemaPurpose.FULL else None
            ),
            fingerprint=snapshot.manifest.fingerprint,
        )

    @staticmethod
    def _select_flatbuffer_closure(
        descriptors: list[FlatBufferTypeDescriptor],
        enums: list[FlatBufferEnumDescriptor],
        target_types: tuple[str, ...],
    ) -> tuple[list[FlatBufferTypeDescriptor], list[FlatBufferEnumDescriptor]]:
        descriptor_by_name = {
            name: descriptor
            for descriptor in descriptors
            for name in {
                descriptor.name,
                descriptor.original_name,
                descriptor.full_name,
            }
        }
        enum_by_name = {
            name: enum
            for enum in enums
            for name in {enum.name, enum.original_name, enum.full_name}
        }
        selected_descriptors: dict[str, FlatBufferTypeDescriptor] = {}
        selected_enums: dict[str, FlatBufferEnumDescriptor] = {}
        pending = list(target_types)
        missing = [name for name in target_types if name not in descriptor_by_name]
        if missing:
            raise LookupError(
                "Character-index FlatBuffer targets are missing from dump.cs: "
                + ", ".join(missing)
            )
        while pending:
            name = pending.pop()
            descriptor = descriptor_by_name.get(name)
            if descriptor is None or descriptor.full_name in selected_descriptors:
                continue
            selected_descriptors[descriptor.full_name] = descriptor
            for field in descriptor.fields:
                references = re.findall(r"[A-Za-z_][\w.]*", field.cs_type)
                for reference in references:
                    dependency = descriptor_by_name.get(reference)
                    if dependency is not None:
                        pending.append(dependency.full_name)
                    enum = enum_by_name.get(reference)
                    if enum is not None:
                        selected_enums[enum.full_name] = enum
        return list(selected_descriptors.values()), list(selected_enums.values())

    def _materialize_snapshot(
        self,
        context: RuntimeContext,
        snapshot: SchemaSnapshot,
    ) -> None:
        target_root = Path(context.extract_dir).resolve()
        marker_path = target_root / ".schema-fingerprint.json"
        try:
            if marker_path.read_text(
                encoding="ascii"
            ).strip() == snapshot.manifest.fingerprint and all(
                path.exists()
                for path in (
                    extracted_dumps_root(context),
                    extracted_schema_root(context, "flatbuffer"),
                    extracted_schema_root(context, "memorypack"),
                )
            ):
                return
        except OSError:
            pass
        target_paths = (
            extracted_dumps_root(context),
            extracted_schema_root(context, "flatbuffer"),
            extracted_schema_root(context, "memorypack"),
        )
        sources = (
            snapshot.root / "dumps",
            snapshot.root / "schemas" / "flatbuffers",
            snapshot.root / "schemas" / "memorypack",
        )
        adapter_root = target_root / ".schema-materialize" / uuid4().hex
        prepared_root = adapter_root / "prepared"
        backup_root = adapter_root / "previous"
        for index, source in enumerate(sources):
            shutil.copytree(source, prepared_root / str(index))
        moved: list[tuple[Path, Path]] = []
        try:
            backup_root.mkdir(parents=True)
            for index, target in enumerate(target_paths):
                if not target.exists():
                    continue
                backup = backup_root / str(index)
                target.rename(backup)
                moved.append((target, backup))
            for index, target in enumerate(target_paths):
                target.parent.mkdir(parents=True, exist_ok=True)
                (prepared_root / str(index)).rename(target)
            marker_path.parent.mkdir(parents=True, exist_ok=True)
            temporary_marker = marker_path.with_name(
                f".{marker_path.name}.{uuid4().hex}.tmp"
            )
            temporary_marker.write_text(
                snapshot.manifest.fingerprint + "\n", encoding="ascii"
            )
            temporary_marker.replace(marker_path)
        except BaseException:
            for target in target_paths:
                if target.exists():
                    shutil.rmtree(target, ignore_errors=True)
            for target, backup in reversed(moved):
                if backup.exists():
                    backup.rename(target)
            raise
        finally:
            shutil.rmtree(adapter_root, ignore_errors=True)
            with suppress(OSError):
                adapter_root.parent.rmdir()

    def _discard_staging(self) -> None:
        if self._staging_root is not None:
            self.snapshot_store.discard_staging(self._staging_root)
        self._reset_state()

    def _reset_state(self) -> None:
        self._staging_root = None
        self._staged_context = None
        self._runtime_assets = None
        self._fingerprint = ""
        self._cached_snapshot = None
        self._purpose = SchemaPurpose.FULL
        self._target_types = ()
