from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path
from typing import Any

from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.infrastructure.extraction.table.models import (
    MalformedTablePayloadError,
    ProcessedTableArtifact,
    TableDecryptError,
    TableProcessingError,
    UnsupportedSchemaError,
)
from ba_downloader.infrastructure.extraction.table.payload_router import (
    TablePayloadRouter,
)
from ba_downloader.infrastructure.schema.common.generated_registry import (
    GeneratedSchemaRegistry,
)
from ba_downloader.infrastructure.schema.crypto import create_key, xor_with_key
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

    def __init__(
        self,
        flatbuffer_data_dir: str,
        logger: LoggerPort,
        *,
        memorypack_data_dir: str | None = None,
        memorypack_formatter_path: str | None = None,
        payload_router: TablePayloadRouter | None = None,
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
        self.payload_router = payload_router or TablePayloadRouter()
        self.lower_schema_registry: dict[str, Any] = {}
        self.flatbuffer_exporter: FlatBufferExporter
        self.memorypack_schema_registry = MemoryPackSchemaRegistry(types={}, enums={})
        self.memorypack_formatter_registry: MemoryPackFormatterRegistry | None = None
        self._memorypack_warning_keys: set[tuple[str, str, str, str, str]] = set()
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
        flatbuffer_schema = self.lower_schema_registry.get(
            file_name.removesuffix(".bytes").lower()
        )
        if flatbuffer_schema is None:
            raise UnsupportedSchemaError(
                f"Unsupported schema for {file_name}: generated FlatBufferData schema is missing."
            )
        return flatbuffer_schema

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
        if file_name.endswith(".json") and (
            json_bytes := self.process_json_file(file_data)
        ):
            return ProcessedTableArtifact(json_bytes, file_name)

        if Path(file_name).suffix.lower() in self.RAW_SIDECAR_ENTRY_SUFFIXES:
            return ProcessedTableArtifact(file_data, file_name)

        if detect_type or file_name.endswith(".bytes"):
            file_dict, normalized_name = self.process_bytes_file(file_name, file_data)
            return ProcessedTableArtifact(
                json.dumps(file_dict, indent=4, ensure_ascii=False).encode("utf8"),
                normalized_name,
            )

        raise UnsupportedSchemaError(
            f"Unsupported entry {file_name} in {archive_name}: no matching table processor."
        )

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
