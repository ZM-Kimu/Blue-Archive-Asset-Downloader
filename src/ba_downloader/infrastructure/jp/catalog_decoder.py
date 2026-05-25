from __future__ import annotations

import json
import struct
from collections.abc import Callable, Mapping
from enum import IntEnum
from io import BytesIO
from pathlib import Path
from typing import Any

from ba_downloader.domain.models.asset import BootstrapSession, CatalogSource
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.infrastructure.jp.models import DecodedJPCatalog
from ba_downloader.infrastructure.schema.memorypack.reader import (
    MemoryPackReader,
    MemoryPackSchemaRegistry,
)

NULL_OBJECT_HEADER = 255
NULL_COLLECTION_HEADER = -1


class JPCatalogDecoder:
    class Reader:
        def __init__(self, initial_bytes: bytes) -> None:
            self.io = BytesIO(initial_bytes)

        def _read_exact(self, size: int) -> bytes:
            data = self.io.read(size)
            if len(data) != size:
                raise EOFError("Unexpected end of MemoryPack stream.")
            return data

        def read_int32(self) -> int:
            return struct.unpack("<i", self._read_exact(4))[0]

        def read_int64(self) -> int:
            return struct.unpack("<q", self._read_exact(8))[0]

        def read_uint8(self) -> int:
            return struct.unpack("<B", self._read_exact(1))[0]

        def read_bool(self) -> bool:
            return struct.unpack("<?", self._read_exact(1))[0]

        def read_object_header(self) -> int | None:
            header = self.read_uint8()
            if header == NULL_OBJECT_HEADER:
                return None
            return header

        def read_collection_header(self) -> int | None:
            length = self.read_int32()
            if length == NULL_COLLECTION_HEADER:
                return None
            return length

        def read_string(self) -> str | None:
            length = self.read_collection_header()
            if length is None:
                return None
            if length == 0:
                return ""
            if length > 0:
                return self._read_exact(length * 2).decode("utf-16-le")

            utf8_length = ~length
            self.read_int32()
            return self._read_exact(utf8_length).decode("utf-8")

        def read_array(
            self,
            item_reader: Callable[[JPCatalogDecoder.Reader], Any],
        ) -> list[Any]:
            length = self.read_collection_header()
            if length is None:
                return []
            return [item_reader(self) for _ in range(length)]

        def read_string_map(
            self,
            value_reader: Callable[[JPCatalogDecoder.Reader], dict[str, object]],
        ) -> dict[str, dict[str, object]]:
            length = self.read_collection_header()
            if length is None:
                return {}

            result: dict[str, dict[str, object]] = {}
            for _ in range(length):
                key = self.read_string()
                if key is None:
                    raise ValueError("Encountered null key in MemoryPack map.")
                result[key] = value_reader(self)
            return result

    @classmethod
    def decode(
        cls,
        session: BootstrapSession,
        sources: list[CatalogSource],
        context: RuntimeContext,
    ) -> DecodedJPCatalog:
        _ = session
        memorypack_registry = cls.__load_memorypack_registry(context)
        payload = DecodedJPCatalog(tables=[], media=[], bundles=[])

        for source in sources:
            if source.name == "table":
                table_assets = cls.__try_decode_table_catalog_with_memorypack(
                    source.content,
                    memorypack_registry,
                )
                if table_assets is None:
                    table_assets = cls.__decode_table_catalog(cls.Reader(source.content))
                payload.tables.extend(table_assets)
            elif source.name == "media":
                media_assets = cls.__try_decode_media_catalog_with_memorypack(
                    source.content,
                    memorypack_registry,
                )
                if media_assets is None:
                    media_assets = cls.__decode_media_catalog(cls.Reader(source.content))
                payload.media.extend(media_assets)
            elif source.name == "bundle":
                payload.bundles.extend(cls.__decode_bundle_catalog(source.content))

        return payload

    @classmethod
    def __load_memorypack_registry(
        cls,
        context: RuntimeContext,
    ) -> MemoryPackSchemaRegistry | None:
        memorypack_data_dir = Path(context.extract_dir) / "MemoryPackData"
        if not (
            memorypack_data_dir.is_dir()
            and (memorypack_data_dir / "__init__.py").is_file()
            and (memorypack_data_dir / "_registry.py").is_file()
        ):
            return None

        try:
            return MemoryPackSchemaRegistry.from_directory(memorypack_data_dir)
        except (FileNotFoundError, ImportError, AttributeError, TypeError, ValueError):
            return None

    @classmethod
    def __try_decode_table_catalog_with_memorypack(
        cls,
        raw_data: bytes,
        registry: MemoryPackSchemaRegistry | None,
    ) -> list[dict[str, object]] | None:
        if registry is None:
            return None
        schema_type = registry.resolve_type("TableCatalog")
        if schema_type is None:
            return None

        try:
            catalog = MemoryPackReader(raw_data).read_object(schema_type)
        except (EOFError, KeyError, TypeError, ValueError, AttributeError):
            return None
        if catalog is None:
            return []

        return cls.__table_catalog_to_assets(catalog)

    @classmethod
    def __try_decode_media_catalog_with_memorypack(
        cls,
        raw_data: bytes,
        registry: MemoryPackSchemaRegistry | None,
    ) -> list[dict[str, object]] | None:
        if registry is None:
            return None
        schema_type = registry.resolve_type("Media.Service.MediaCatalog")
        if schema_type is None:
            schema_type = registry.resolve_type("MediaCatalog")
        if schema_type is None:
            return None

        try:
            catalog = MemoryPackReader(raw_data).read_object(schema_type)
        except (EOFError, KeyError, TypeError, ValueError, AttributeError):
            return None
        if catalog is None:
            return []

        return cls.__media_catalog_to_assets(catalog)

    @classmethod
    def __table_catalog_to_assets(cls, catalog: Any) -> list[dict[str, object]]:
        assets: list[dict[str, object]] = []
        table_manifest = cls.__dict_field(catalog, "Table")
        table_pack_manifest = cls.__dict_field(catalog, "TablePack")

        for key, bundle in table_manifest.items():
            asset = cls.__table_bundle_to_dict(bundle)
            asset["key"] = key
            assets.append(asset)

        for key, pack in table_pack_manifest.items():
            asset = cls.__table_patch_pack_to_dict(pack)
            asset["key"] = key
            assets.append(asset)

        return assets

    @classmethod
    def __media_catalog_to_assets(cls, catalog: Any) -> list[dict[str, object]]:
        assets: list[dict[str, object]] = []
        for key, media in cls.__dict_field(catalog, "Table").items():
            asset = cls.__media_to_dict(media)
            asset["key"] = key
            asset["path"] = str(asset["path"]).replace("\\", "/")
            assets.append(asset)
        return assets

    @classmethod
    def __table_bundle_to_dict(cls, bundle: Any) -> dict[str, object]:
        includes = [
            str(item)
            for item in cls.__list_field(bundle, "Includes")
            if item is not None and str(item)
        ]
        return {
            "name": cls.__string_field(bundle, "Name"),
            "size": cls.__int_field(bundle, "Size"),
            "crc": cls.__int_field(bundle, "Crc"),
            "is_in_build": cls.__bool_field(bundle, "isInbuild"),
            "is_changed": cls.__bool_field(bundle, "isChanged"),
            "is_prologue": cls.__bool_field(bundle, "IsPrologue"),
            "is_split_download": cls.__bool_field(bundle, "IsSplitDownload"),
            "includes": includes,
        }

    @classmethod
    def __table_patch_pack_to_dict(cls, pack: Any) -> dict[str, object]:
        bundle_files = [
            cls.__table_bundle_to_dict(bundle)
            for bundle in cls.__list_field(pack, "BundleFiles")
        ]
        return {
            "name": cls.__string_field(pack, "Name"),
            "size": cls.__int_field(pack, "Size"),
            "crc": cls.__int_field(pack, "Crc"),
            "is_in_build": False,
            "is_changed": False,
            "is_prologue": cls.__bool_field(pack, "IsPrologue"),
            "is_split_download": False,
            "includes": [str(bundle["name"]) for bundle in bundle_files],
            "bundle_files": bundle_files,
        }

    @classmethod
    def __media_to_dict(cls, media: Any) -> dict[str, object]:
        return {
            "path": cls.__string_field(media, "Path"),
            "file_name": cls.__string_field(media, "FileName"),
            "type": cls.__enum_or_int_field(media, "MediaType"),
            "bytes": cls.__int_field(media, "Bytes"),
            "crc": cls.__int_field(media, "Crc"),
            "is_prologue": cls.__bool_field(media, "IsPrologue"),
            "is_split_download": cls.__bool_field(media, "IsSplitDownload"),
        }

    @staticmethod
    def __dict_field(source: Any, field_name: str) -> dict[str, Any]:
        value = getattr(source, field_name, None)
        if isinstance(value, dict):
            return value
        return {}

    @staticmethod
    def __list_field(source: Any, field_name: str) -> list[Any]:
        value = getattr(source, field_name, None)
        if isinstance(value, list):
            return value
        return []

    @staticmethod
    def __string_field(source: Any, field_name: str) -> str:
        value = getattr(source, field_name, None)
        return "" if value is None else str(value)

    @staticmethod
    def __int_field(source: Any, field_name: str) -> int:
        value = getattr(source, field_name, 0)
        if value is None:
            return 0
        return int(value)

    @staticmethod
    def __bool_field(source: Any, field_name: str) -> bool:
        return bool(getattr(source, field_name, False))

    @staticmethod
    def __enum_or_int_field(source: Any, field_name: str) -> int:
        value = getattr(source, field_name, 0)
        if isinstance(value, IntEnum):
            return int(value)
        if value is None:
            return 0
        return int(value)

    @classmethod
    def __decode_media_catalog(
        cls,
        data: Reader,
    ) -> list[dict[str, object]]:
        member_count = data.read_object_header()
        if member_count is None or member_count < 1:
            return []

        manifest = data.read_string_map(cls.__decode_media_manifest)
        assets: list[dict[str, object]] = []
        for key, obj in manifest.items():
            path = str(obj["path"]).replace("\\", "/")
            obj["key"] = key
            obj["path"] = path
            assets.append(obj)
        return assets

    @classmethod
    def __decode_table_catalog(
        cls,
        data: Reader,
    ) -> list[dict[str, object]]:
        member_count = data.read_object_header()
        if member_count is None or member_count < 1:
            return []

        manifest = data.read_string_map(cls.__decode_table_manifest)
        if member_count >= 2:
            for key, obj in data.read_string_map(
                cls.__decode_table_pack_manifest
            ).items():
                manifest[key] = obj

        assets: list[dict[str, object]] = []
        for key, obj in manifest.items():
            obj["key"] = key
            assets.append(obj)
        return assets

    @staticmethod
    def __decode_bundle_catalog(raw_data: bytes) -> list[dict[str, object]]:
        payload = json.loads(raw_data)
        assets: list[dict[str, object]] = []
        for section_name in ("FullPatchPacks", "UpdatePacks"):
            packs = payload.get(section_name, [])
            if not isinstance(packs, list):
                continue
            for pack in packs:
                if not isinstance(pack, Mapping):
                    continue
                pack_name = str(pack.get("PackName", "")).strip()
                if not pack_name:
                    continue
                assets.append(
                    {
                        "name": pack_name,
                        "size": int(pack.get("PackSize", 0) or 0),
                        "crc": int(pack.get("Crc", 0) or 0),
                        "bundle_files": [
                            str(bundle.get("Name", "")).strip()
                            for bundle in pack.get("BundleFiles", [])
                            if isinstance(bundle, Mapping) and bundle.get("Name")
                        ],
                        "is_prologue": bool(pack.get("IsPrologue", False)),
                        "is_split_download": bool(pack.get("IsSplitDownload", False)),
                    }
                )
        return assets

    @classmethod
    def __decode_media_manifest(
        cls,
        data: Reader,
    ) -> dict[str, object]:
        member_count = data.read_object_header()
        if member_count is None or member_count < 7:
            raise ValueError("Malformed JP media catalog entry.")

        path = data.read_string() or ""
        file_name = data.read_string() or ""
        size = data.read_int64()
        crc = data.read_int64()
        is_prologue = data.read_bool()
        is_split_download = data.read_bool()
        media_type = data.read_int32()

        return {
            "path": path,
            "file_name": file_name,
            "type": media_type,
            "bytes": size,
            "crc": crc,
            "is_prologue": is_prologue,
            "is_split_download": is_split_download,
        }

    @classmethod
    def __decode_table_manifest(
        cls,
        data: Reader,
    ) -> dict[str, object]:
        member_count = data.read_object_header()
        if member_count is None or member_count < 8:
            raise ValueError("Malformed JP table catalog entry.")

        name = data.read_string() or ""
        size = data.read_int64()
        crc = data.read_int64()
        is_in_build = data.read_bool()
        is_changed = data.read_bool()
        is_prologue = data.read_bool()
        is_split_download = data.read_bool()
        includes = [
            item for item in data.read_array(lambda reader: reader.read_string()) if item
        ]

        return {
            "name": name,
            "size": size,
            "crc": crc,
            "is_in_build": is_in_build,
            "is_changed": is_changed,
            "is_prologue": is_prologue,
            "is_split_download": is_split_download,
            "includes": includes,
        }

    @classmethod
    def __decode_table_pack_manifest(
        cls,
        data: Reader,
    ) -> dict[str, object]:
        member_count = data.read_object_header()
        if member_count is None or member_count < 5:
            raise ValueError("Malformed JP table pack catalog entry.")

        name = data.read_string() or ""
        size = data.read_int64()
        crc = data.read_int64()
        is_prologue = data.read_bool()
        bundle_files = data.read_array(cls.__decode_table_manifest)

        return {
            "name": name,
            "size": size,
            "crc": crc,
            "is_in_build": False,
            "is_changed": False,
            "is_prologue": is_prologue,
            "is_split_download": False,
            "includes": [str(bundle["name"]) for bundle in bundle_files],
            "bundle_files": bundle_files,
        }
