from __future__ import annotations

import hashlib
import json
import struct
from dataclasses import make_dataclass
from pathlib import Path
from typing import Annotated, Any, cast

from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.infrastructure.extraction.table.models import (
    MalformedTablePayloadError,
    ProcessedTableArtifact,
    TableDecryptError,
    TableProcessingError,
    UnsupportedSchemaError,
)
from ba_downloader.infrastructure.extraction.table.payload_router import (
    FlatBufferTablePayloadRouter,
    TablePayloadRouter,
)
from ba_downloader.infrastructure.schema.common.generated_registry import (
    GeneratedSchemaRegistry,
)
from ba_downloader.infrastructure.schema.crypto import create_key, xor_with_key
from ba_downloader.infrastructure.schema.flatbuffer.descriptors import (
    FlatBufferField,
    FlatBufferTypeMetadata,
)
from ba_downloader.infrastructure.schema.flatbuffer.reader import FlatBufferExporter
from ba_downloader.infrastructure.schema.memorypack.formatters import (
    MemoryPackFormatterRegistry,
)
from ba_downloader.infrastructure.schema.memorypack.reader import (
    MemoryPackReader,
    MemoryPackSchemaRegistry,
)


class TablePayloadCodecAdapter:
    MEMORYPACK_FORMATTER_SIDECAR_NAME = "memorypack_formatters.json"
    RAW_SIDECAR_ENTRY_SUFFIXES = frozenset({".bin", ".txt"})
    COMPACT_JSON_MIN_BYTES = 1_000_000

    def __init__(
        self,
        flatbuffer_data_dir: str,
        logger: LoggerPort,
        *,
        memorypack_data_dir: str | None = None,
        memorypack_formatter_path: str | None = None,
        payload_router: TablePayloadRouter | None = None,
        preserved_archive_entries: frozenset[str] = frozenset(),
    ) -> None:
        self.flatbuffer_data_dir = flatbuffer_data_dir
        self.memorypack_data_dir = memorypack_data_dir or str(
            Path(flatbuffer_data_dir).parent / "MemoryPackData"
        )
        self.memorypack_formatter_path = memorypack_formatter_path or str(
            Path(flatbuffer_data_dir).parent
            / "Dumps"
            / self.MEMORYPACK_FORMATTER_SIDECAR_NAME
        )
        self.logger = logger
        self.payload_router = payload_router or FlatBufferTablePayloadRouter()
        self.preserved_archive_entries = {
            Path(file_name).name.lower() for file_name in preserved_archive_entries
        }
        self.lower_schema_registry: dict[str, Any] = {}
        self.flatbuffer_exporter: FlatBufferExporter
        self.memorypack_schema_registry = MemoryPackSchemaRegistry(types={}, enums={})
        self.memorypack_formatter_registry: MemoryPackFormatterRegistry | None = None
        self._memorypack_warning_keys: set[tuple[str, str, str, str, str]] = set()
        self._synthetic_table_schemas: dict[str, type[Any]] = {}
        self.load_modules()

    def load_modules(self) -> None:
        registry = self.load_flat_buffer_data_registry()
        self.flatbuffer_exporter = FlatBufferExporter(
            registry.types,
            registry.enums,
        )
        self.lower_schema_registry = self.flatbuffer_exporter.lower_type_registry
        self.load_memorypack_data_registry()
        self.load_memorypack_formatter_registry()

    def load_flat_buffer_data_registry(self) -> GeneratedSchemaRegistry:
        try:
            return GeneratedSchemaRegistry.from_directory(
                self.flatbuffer_data_dir,
                type_registry_name="FLATBUFFER_TYPES",
                enum_registry_name="FLATBUFFER_ENUMS",
                package_prefix="ba_downloader_generated_flatbufferdata",
            )
        except FileNotFoundError as exc:
            message = str(exc)
            if "directory does not exist" in message:
                raise FileNotFoundError(
                    f"FlatBufferData directory does not exist: {self.flatbuffer_data_dir}."
                ) from exc
            if "initializer is missing" in message:
                raise FileNotFoundError(
                    "FlatBufferData package initializer is missing: "
                    f"{Path(self.flatbuffer_data_dir) / '__init__.py'}."
                ) from exc
            if "registry is missing" in message:
                raise FileNotFoundError(
                    f"FlatBufferData registry is missing: {Path(self.flatbuffer_data_dir) / '_registry.py'}."
                ) from exc
            raise
        except ImportError as exc:
            raise ImportError(
                f"Unable to create FlatBufferData import spec for {self.flatbuffer_data_dir}."
            ) from exc

    def load_memorypack_data_registry(self) -> None:
        try:
            self.memorypack_schema_registry = MemoryPackSchemaRegistry.from_directory(
                self.memorypack_data_dir,
            )
        except (FileNotFoundError, ImportError, TypeError):
            self.memorypack_schema_registry = MemoryPackSchemaRegistry(
                types={},
                enums={},
            )

    def load_memorypack_formatter_registry(self) -> None:
        sidecar_path = Path(self.memorypack_formatter_path)
        if not sidecar_path.is_file():
            self.memorypack_formatter_registry = None
            return
        try:
            self.memorypack_formatter_registry = MemoryPackFormatterRegistry.from_file(
                sidecar_path,
            )
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            self.memorypack_formatter_registry = None

    def process_bytes_file(
        self, file_name: str, data: bytes
    ) -> tuple[dict[str, Any] | list[Any], str]:
        flatbuffer_schema = self.resolve_flatbuffer_schema(file_name)
        normalized_name = flatbuffer_schema.__name__

        if normalized_name.endswith("Table"):
            encrypted_error: TableProcessingError | None = None
            try:
                return self.dump_encrypted_table(flatbuffer_schema, data)
            except TableProcessingError as exc:
                encrypted_error = exc

            try:
                return self.dump_flatbuffer_payload(flatbuffer_schema, data)
            except TableProcessingError as exc:
                raise MalformedTablePayloadError(
                    f"Malformed flatbuffer payload for {file_name}: "
                    f"encrypted decode failed ({encrypted_error}); raw decode failed ({exc})."
                ) from exc

        return self.dump_flatbuffer_payload(flatbuffer_schema, data)

    def resolve_flatbuffer_schema(self, file_name: str) -> Any:
        schema_key = file_name.removesuffix(".bytes").lower()
        flatbuffer_schema = self.lower_schema_registry.get(schema_key)
        if flatbuffer_schema is None:
            flatbuffer_schema = self.resolve_synthetic_table_schema(schema_key)
        if flatbuffer_schema is None:
            raise UnsupportedSchemaError(
                f"Unsupported schema for {file_name}: generated FlatBufferData schema is missing."
            )
        return flatbuffer_schema

    def resolve_synthetic_table_schema(self, schema_key: str) -> type[Any] | None:
        if schema_key in self._synthetic_table_schemas:
            return self._synthetic_table_schemas[schema_key]
        if not schema_key.endswith("exceltable"):
            return None

        row_key = schema_key.removesuffix("table")
        row_schema = self.lower_schema_registry.get(row_key)
        if row_schema is None:
            return None

        table_name = f"{row_schema.__name__}Table"
        metadata = FlatBufferTypeMetadata(
            name=table_name,
            namespace="Synthetic",
            kind="struct",
            original_name=table_name,
            type_def_index=-1,
            token="",
        )
        field = FlatBufferField(
            index=0,
            cs_type=row_schema.__name__,
            type_name=table_name,
            namespace="Synthetic",
            member_token="",
            original_name="DataList",
            is_vector=True,
        )
        row_list_annotation = list.__class_getitem__(row_schema)
        data_list_annotation = cast(Any, Annotated)[row_list_annotation, field]
        table_schema = make_dataclass(
            table_name,
            [
                (
                    "DataList",
                    data_list_annotation,
                )
            ],
        )
        table_schema.__flatbuffer_type__ = metadata  # type: ignore[attr-defined]
        self._synthetic_table_schemas[schema_key] = table_schema
        return table_schema

    def dump_encrypted_table(
        self, flatbuffer_schema: Any, data: bytes
    ) -> tuple[dict[str, Any] | list[Any], str]:
        try:
            decrypted_data = xor_with_key(flatbuffer_schema.__name__, data)
        except (TypeError, ValueError) as exc:
            raise TableDecryptError(
                f"xor/decrypt failed for {flatbuffer_schema.__name__}: {exc}"
            ) from exc

        try:
            excel_name = flatbuffer_schema.__name__.removesuffix("Table")
            password = create_key(excel_name.removesuffix("Excel"))
            return (
                self.flatbuffer_exporter.export_payload(
                    flatbuffer_schema,
                    decrypted_data,
                    password=password,
                ),
                f"{flatbuffer_schema.__name__}.json",
            )
        except RuntimeError as exc:
            raise TableDecryptError(
                f"xor/decrypt failed for {flatbuffer_schema.__name__}: {exc}"
            ) from exc
        except (
            EOFError,
            TypeError,
            ValueError,
            KeyError,
            IndexError,
            struct.error,
        ) as exc:
            raise TableDecryptError(
                f"xor/decrypt failed for {flatbuffer_schema.__name__}: {exc}"
            ) from exc

    def dump_flatbuffer_payload(
        self,
        flatbuffer_schema: Any,
        data: bytes,
    ) -> tuple[dict[str, Any] | list[Any], str]:
        try:
            return (
                self.flatbuffer_exporter.export_payload(flatbuffer_schema, data),
                f"{flatbuffer_schema.__name__}.json",
            )
        except RuntimeError as exc:
            raise MalformedTablePayloadError(
                f"Malformed flatbuffer payload for {flatbuffer_schema.__name__}: {exc}"
            ) from exc
        except (
            EOFError,
            TypeError,
            ValueError,
            KeyError,
            IndexError,
            struct.error,
        ) as exc:
            raise MalformedTablePayloadError(
                f"Malformed flatbuffer payload for {flatbuffer_schema.__name__}: {exc}"
            ) from exc

    @staticmethod
    def process_json_file(data: bytes) -> bytes:
        try:
            data.decode("utf8")
        except UnicodeDecodeError:
            return b""
        return data

    def process_zip_file(
        self,
        archive_name: str,
        file_name: str,
        file_data: bytes,
        *,
        detect_type: bool = False,
    ) -> ProcessedTableArtifact:
        if Path(file_name).name.lower() in self.preserved_archive_entries:
            return ProcessedTableArtifact(file_data, Path(file_name).name)

        if file_name.endswith(".json") and (
            json_bytes := self.process_json_file(file_data)
        ):
            return ProcessedTableArtifact(json_bytes, file_name)

        if Path(file_name).suffix.lower() in self.RAW_SIDECAR_ENTRY_SUFFIXES:
            return ProcessedTableArtifact(file_data, file_name)

        if detect_type or file_name.endswith(".bytes"):
            file_dict, normalized_name = self.process_bytes_file(file_name, file_data)
            return ProcessedTableArtifact(
                self.dump_json_artifact(
                    file_dict,
                    compact=normalized_name == "GroundGridFlat.json",
                ),
                normalized_name,
            )

        raise UnsupportedSchemaError(
            f"Unsupported entry {file_name} in {archive_name}: no matching table processor."
        )

    def process_memorypack_payload(
        self,
        root_type: str,
        file_data: bytes,
        output_name: str,
        *,
        compact: bool = False,
    ) -> ProcessedTableArtifact:
        if self.memorypack_formatter_registry is None:
            raise UnsupportedSchemaError(
                f"MemoryPack formatter sidecar is missing for {root_type}."
            )
        formatter = self.memorypack_formatter_registry.resolve(root_type)
        if formatter is None or not formatter.is_available:
            raise UnsupportedSchemaError(
                f"MemoryPack formatter layout is unavailable for {root_type}."
            )
        try:
            value = MemoryPackReader(file_data).read_formatter_object(
                root_type,
                self.memorypack_schema_registry,
                self.memorypack_formatter_registry,
            )
        except (EOFError, TypeError, ValueError, struct.error) as exc:
            raise MalformedTablePayloadError(
                f"Malformed MemoryPack payload for {root_type}: {exc}"
            ) from exc
        return ProcessedTableArtifact(
            self.dump_json_artifact(value, compact=compact),
            output_name,
        )

    def dump_json_artifact(
        self,
        value: dict[str, Any] | list[Any],
        *,
        compact: bool = False,
    ) -> bytes:
        compact_json = json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        if compact or len(compact_json.encode("utf8")) >= self.COMPACT_JSON_MIN_BYTES:
            return compact_json.encode("utf8")
        return json.dumps(value, indent=4, ensure_ascii=False).encode("utf8")

    def convert_memorypack_database_value(
        self,
        db_name: str,
        table_name: str,
        column_name: str,
        value: bytes,
        root_type: str,
        *,
        allow_partial: bool,
    ) -> dict[str, Any]:
        if self.memorypack_formatter_registry is not None:
            formatter = self.memorypack_formatter_registry.resolve(root_type)
            if formatter is not None and formatter.is_available:
                try:
                    return MemoryPackReader(value).read_formatter_object(
                        root_type,
                        self.memorypack_schema_registry,
                        self.memorypack_formatter_registry,
                    )
                except (EOFError, TypeError, ValueError, struct.error):
                    pass

        if allow_partial:
            try:
                result = MemoryPackReader(value).read_cn_table_dao_partial(
                    root_type,
                    self.memorypack_schema_registry,
                )
            except (EOFError, TypeError, ValueError, struct.error) as exc:
                message = f"MemoryPack partial decode failed for {root_type}: {exc}"
                self.warn_memorypack_database_value_once(
                    db_name,
                    table_name,
                    column_name,
                    root_type,
                    message,
                )
                return self.memorypack_raw_fallback(value, root_type, error=str(exc))

            return result

        message = f"MemoryPack formatter layout is unavailable for {root_type}."
        self.warn_memorypack_database_value_once(
            db_name,
            table_name,
            column_name,
            root_type,
            message,
        )
        return self.memorypack_raw_fallback(value, root_type)

    def warn_memorypack_database_value_once(
        self,
        db_name: str,
        table_name: str,
        column_name: str,
        root_type: str,
        message: str,
    ) -> None:
        warning_key = (db_name, table_name, column_name, root_type, message)
        if warning_key in self._memorypack_warning_keys:
            return
        self._memorypack_warning_keys.add(warning_key)
        self.logger.warn(
            f"Using raw MemoryPack fallback for bytes field {column_name} "
            f"in {table_name}: {message}"
        )

    @staticmethod
    def memorypack_raw_fallback(
        value: bytes,
        root_type: str,
        *,
        error: str = "MemoryPack formatter layout is unavailable.",
    ) -> dict[str, Any]:
        return {
            "__memorypack_error__": error,
            "__root_type__": root_type,
            "__payload_size__": len(value),
            "__payload_sha256__": hashlib.sha256(value).hexdigest(),
            "__payload_head__": value[:64].hex(),
        }
