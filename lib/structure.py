"""Store some structures."""

from dataclasses import dataclass
from enum import Enum
from typing import Iterator, Literal
from urllib.parse import urljoin


# Database
@dataclass
class DBColumn:
    name: str
    data_type: str


@dataclass
class DBTable:
    name: str
    columns: list[DBColumn]
    data: list[list]


class SQLiteDataType(Enum):
    INTEGER = int
    REAL = float
    NUMERIC = float
    TEXT = str
    BLOB = bytes
    BOOLEAN = bool
    NULL = None


# Compiler
@dataclass
class Property:
    data_type: str
    name: str
    is_list: bool


@dataclass
class StructTable:
    name: str
    properties: list[Property]


@dataclass
class EnumMember:
    name: str
    value: str


@dataclass
class EnumType:
    name: str
    underlying_type: str
    members: list[EnumMember]


@dataclass
class ResourceItem:
    url: str
    path: str
    size: int
    checksum: str
    check_type: Literal["crc", "md5"]
    addition: dict


class Resource_New:
    def __init__(self) -> None:
        # There are 6 basic generic types in Resource: url, path, size, checksum, check_type, and addition.
        self.resources: list[ResourceItem] = []

    def __bool__(self) -> bool:
        return bool(self.resources)

    def __getitem__(self, index: slice | int) -> list[ResourceItem] | ResourceItem:
        if isinstance(index, slice):
            return self.resources[index.start : index.stop : index.step]
        return self.resources[index]

    def __len__(self) -> int:
        return len(self.resources)

    def __iter__(self) -> Iterator[ResourceItem]:
        return iter(self.resources)

    def __repr__(self) -> str:
        size = sum(item.size for item in self.resources)
        return f"{len(self)} items in the manifest, totaling {round(size / (1024**3), 2)}GB"

    def add_resource(self, url: str, data: dict) -> None:
        """Add a dictionary object that conforms to the basic resource structure and modify its URL."""
        data["url"] = url
        self.resources.append(data)

    def add_resource_item(self, item: dict) -> None:
        """Add a dictionary object that conforms to the basic resource structure."""
        for key in ["url", "path", "size", "checksum", "check_type", "addition"]:
            if key not in item.keys():
                return
        self.resources.append(item)

    def add(
        self,
        url: str,
        path: str,
        size: int,
        checksum: str,
        check_type: Literal["crc", "md5"],
        addition: dict | None = None,
    ) -> None:
        """Add resource."""
        self.resources.append(
            {
                "url": url,
                "path": path,
                "size": size,
                "checksum": checksum,
                "check_type": check_type,
                "addition": {} if not addition else addition,
            }
        )

    def sorted_by_size(self, descending: bool = True) -> None:
        """Sort by file size.
        Args:
            descending (bool, optional): Sort with descending order. Defaults to True.
        """
        self.resources.sort(key=lambda x: x["size"], reverse=descending)


class Resource:
    def __init__(self) -> None:
        # There are 6 basic generic types in Resource: url, path, size, checksum, check_type, and addition.
        self.resources: list[dict] = []

    def __bool__(self) -> bool:
        return bool(self.resources)

    def __getitem__(self, index: slice | int) -> list[dict] | dict:
        if isinstance(index, slice):
            return self.resources[index.start : index.stop : index.step]
        return self.resources[index]

    def __len__(self) -> int:
        return len(self.resources)

    def __iter__(self) -> Iterator:
        return iter(self.resources)

    def __repr__(self) -> str:
        size = sum(item["size"] for item in self.resources)
        return f"{len(self)} items in the manifest, totaling {round(size / (1024**3), 2)}GB"

    def add_resource(self, url: str, data: dict) -> None:
        """Add a dictionary object that conforms to the basic resource structure and modify its URL."""
        data["url"] = url
        self.resources.append(data)

    def add_resource_item(self, item: dict) -> None:
        """Add a dictionary object that conforms to the basic resource structure."""
        for key in ["url", "path", "size", "checksum", "check_type", "addition"]:
            if key not in item.keys():
                return
        self.resources.append(item)

    def add(
        self,
        url: str,
        path: str,
        size: int,
        checksum: str,
        check_type: Literal["crc", "md5"],
        addition: dict | None = None,
    ) -> None:
        """Add resource."""
        self.resources.append(
            {
                "url": url,
                "path": path,
                "size": size,
                "checksum": checksum,
                "check_type": check_type,
                "addition": {} if not addition else addition,
            }
        )

    def sorted_by_size(self, descending: bool = True) -> None:
        """Sort by file size.
        Args:
            descending (bool, optional): Sort with descending order. Defaults to True.
        """
        self.resources.sort(key=lambda x: x["size"], reverse=descending)


class CNResource:
    def __init__(self) -> None:
        self.base_url = ""
        self.bundle_url = ""
        self.media_url = ""
        self.table_url = ""
        self.bundle_file: list[dict] = []
        self.media_file: list[dict] = []
        self.table_file: list[dict] = []

    def __bool__(self) -> bool:
        return (
            bool(self.bundle_file) and bool(self.media_file) and bool(self.table_file)
        )

    def __len__(self) -> int:
        return len(self.bundle_file) + len(self.media_file) + len(self.table_file)

    def set_url_link(self, base_url: str, bundle: str, media: str, table: str) -> None:
        """Set the URL link, and the base URL must end with a '/'."""
        self.base_url = base_url
        self.bundle_url = urljoin(self.base_url, bundle)
        self.media_url = urljoin(self.base_url, media)
        self.table_url = urljoin(self.base_url, table)

    def add_bundle_resource(
        self, name: str, size: int, md5: str, is_prologue: bool, is_split_download: bool
    ) -> None:
        """Add bundle resource."""
        self.bundle_file.append(
            {
                "name": name,
                "size": size,
                "crc": md5,
                "is_prologue": is_prologue,
                "is_split_download": is_split_download,
            }
        )

    def add_media_resource(
        self, url: str, file_path: str, media_type: str, bytes: int, md5: str
    ) -> None:
        """Add media resource."""
        self.media_file.append(
            {
                "url": url,
                "path": file_path,
                "media_type": media_type,
                "bytes": bytes,
                "crc": md5,
            }
        )

    def add_table_resource(
        self, url: str, name: str, size: int, md5: str, includes: list
    ) -> None:
        """Add table resource."""
        self.table_file.append(
            {"url": url, "name": name, "size": size, "crc": md5, "includes": includes}
        )

    def to_resource(self) -> Resource:
        """Convert custom structures to generic structures."""
        resource = Resource()

        for bundle in self.bundle_file:
            resource.add(
                urljoin(self.bundle_url, bundle["name"]),
                urljoin("Bundle/", bundle["name"]),
                bundle["size"],
                bundle["crc"],
                "md5",
            )

        for media in self.media_file:
            resource.add(
                urljoin(self.media_url, media["url"]),
                urljoin("Media/", media["path"]),
                media["bytes"],
                media["crc"],
                "md5",
                {"media_type": media["media_type"]},
            )

        for table in self.table_file:
            resource.add(
                urljoin(self.table_url, table["url"]),
                urljoin("Table/", table["name"]),
                table["size"],
                table["crc"],
                "md5",
                {"includes": table["includes"]},
            )

        return resource


class GLResource:
    def __init__(self) -> None:
        self.base_url = ""
        self.resource_file: list[dict] = []

    def __bool__(self) -> bool:
        return bool(self.resource_file)

    def __len__(self) -> int:
        return len(self.resource_file)

    def set_url_link(self, base_url: str) -> None:
        """Set the URL link, and the base URL must end with a '/'."""
        self.base_url = base_url

    def add_resource(
        self,
        group: str,
        resource_path: str,
        resource_size: int,
        resource_hash: str,
    ) -> None:
        """Add resource."""
        self.resource_file.append(
            {
                "group": group,
                "resource_path": resource_path,
                "resource_size": resource_size,
                "resource_hash": resource_hash,
            }
        )

    def to_resource(self) -> Resource:
        """Convert custom structures to generic structures."""
        resource = Resource()

        for res in self.resource_file:
            resource.add(
                urljoin(self.base_url, res["resource_path"]),
                res["resource_path"],
                res["resource_size"],
                res["resource_hash"],
                "md5",
            )

        return resource


class JPResource:
    def __init__(self) -> None:
        self.base_url = ""
        self.bundle_url = ""
        self.media_url = ""
        self.table_url = ""
        self.bundle_file: list[dict] = []
        self.media_file: list[dict] = []
        self.table_file: list[dict] = []

    def __bool__(self) -> bool:
        return bool(self.bundle_file) or bool(self.media_file) or bool(self.table_file)

    def __len__(self) -> int:
        return len(self.bundle_file) + len(self.media_file) + len(self.table_file)

    def set_url_link(self, base_url: str, bundle: str, media: str, table: str) -> None:
        """Set the URL link, and the base URL must end with a '/'."""
        self.base_url = base_url
        self.bundle_url = urljoin(self.base_url, bundle)
        self.media_url = urljoin(self.base_url, media)
        self.table_url = urljoin(self.base_url, table)

    def add_bundle_resource(
        self,
        name: str,
        size: int,
        crc: int,
        is_prologue: bool,
        is_split_download: bool,
    ) -> None:
        """Add bundle resource."""
        self.bundle_file.append(
            {
                "name": name,
                "size": size,
                "crc": crc,
                "is_prologue": is_prologue,
                "is_split_download": is_split_download,
            }
        )

    def add_media_resource(
        self,
        key: str,
        path: str,
        file_name: str,
        media_type: str,
        bytes: int,
        crc: int,
        is_prologue: bool,
        is_split_download: bool,
    ) -> None:
        """Add media resource."""
        self.media_file.append(
            {
                "key": key,
                "path": path,
                "file_name": file_name,
                "media_type": media_type,
                "bytes": bytes,
                "crc": crc,
                "is_prologue": is_prologue,
                "is_split_download": is_split_download,
            }
        )

    def add_table_resource(
        self,
        key: str,
        name: str,
        size: int,
        crc: int,
        is_in_build: bool,
        is_changed: bool,
        is_prologue: bool,
        is_split_download: bool,
        includes: list,
    ) -> None:
        """Add table resource."""
        self.table_file.append(
            {
                "key": key,
                "name": name,
                "size": size,
                "crc": crc,
                "is_in_build": is_in_build,
                "is_changed": is_changed,
                "is_prologue": is_prologue,
                "is_split_download": is_split_download,
                "includes": includes,
            }
        )

    def to_resource(self) -> Resource:
        """Convert custom structures to generic structures."""
        resource = Resource()

        for bundle in self.bundle_file:
            resource.add(
                urljoin(self.bundle_url, bundle["name"]),
                urljoin("Bundle/", bundle["name"]),
                bundle["size"],
                bundle["crc"],
                "crc",
            )

        for media in self.media_file:
            resource.add(
                urljoin(self.media_url, media["path"]),
                urljoin("Media/", media["path"]),
                media["bytes"],
                media["crc"],
                "crc",
                {"media_type": media["media_type"]},
            )

        for table in self.table_file:
            resource.add(
                urljoin(self.table_url, table["name"]),
                urljoin("Table/", table["name"]),
                table["size"],
                table["crc"],
                "crc",
                {"includes": table["includes"]},
            )

        return resource
