"""Store some structures."""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterator, Literal, overload
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
class CharacterData:
    character_id: int
    dev_name: str = ""
    full_name_kr: str = ""
    full_name_jp: str = ""
    family_name_jp: str = ""
    family_name_kr: str = ""
    family_name_ruby_jp: str = ""
    personal_name_jp: str = ""
    personal_name_kr: str = ""
    personal_name_ruby_jp: str = ""
    family_name_en: str = ""
    personal_name_en: str = ""
    file_name: set[str] | None = None
    cv: str = ""
    age: int = 0
    height: int = 0
    birthday: str = ""
    illustrator: str = ""
    school_en: str = ""
    club_en: str = ""

    @staticmethod
    def serialize(obj: Any) -> Any:
        """For set type to list."""
        if isinstance(obj, set):
            return list(obj)
        raise TypeError(f"Type {type(obj)} not serializable")


@dataclass
class CharacterRelation:
    version: str
    relations: list[CharacterData]


class ResourceType(Enum):
    table = 0
    media = 1
    bundle = 2


@dataclass
class ResourceItem:
    url: str
    path: str
    size: int
    checksum: str
    check_type: Literal["crc", "md5"]
    resource_type: ResourceType
    addition: dict


class Resource:
    def __init__(self) -> None:
        self.resources: list[ResourceItem] = []

    def __bool__(self) -> bool:
        return bool(self.resources)

    @overload
    def __getitem__(self, index: slice) -> list[ResourceItem]: ...

    @overload
    def __getitem__(self, index: int) -> ResourceItem: ...

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
        return (
            f"{len(self)} items in the catalog, totaling {round(size / (1024**3), 2)}GB"
        )

    def add(
        self,
        url: str,
        path: str,
        size: int,
        checksum: str,
        check_type: Literal["crc", "md5"],
        resource_type: ResourceType,
        addition: dict | None = None,
    ) -> None:
        """Add resource."""
        self.resources.append(
            ResourceItem(
                url,
                path,
                size,
                checksum,
                check_type,
                resource_type,
                addition if addition else {},
            )
        )

    def add_item(self, item: ResourceItem) -> None:
        """Add a ResourceItem instance with data."""
        self.resources.append(item)

    def search_resource(
        self, attr: str, value: Any, exact_match: bool = False
    ) -> "Resource":
        """Retrieve items that contain or match the specified value based on the given key and return the Resource."""
        filtered_res = Resource()
        conditional = lambda x, y: str(x).lower() in str(y).lower()
        if exact_match:
            conditional = lambda x, y: x == y

        _ = [
            filtered_res.add_item(res)  # type: ignore
            for res in self.resources
            if conditional(value, getattr(res, attr))
        ]

        return filtered_res

    def sorted_by_size(self, descending: bool = True) -> None:
        """Sort by file size.

        Args:
            descending (bool, optional): Sort with descending order. Defaults to True.
        """
        self.resources.sort(key=lambda x: x.size, reverse=descending)


class CNResource:
    def __init__(self) -> None:
        self.base_url = ""
        self.bundle_url = ""
        self.media_url = ""
        self.table_url = ""
        self.bundle_files: list[dict] = []
        self.media_files: list[dict] = []
        self.table_files: list[dict] = []

    def __bool__(self) -> bool:
        return (
            bool(self.bundle_files)
            and bool(self.media_files)
            and bool(self.table_files)
        )

    def __len__(self) -> int:
        return len(self.bundle_files) + len(self.media_files) + len(self.table_files)

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
        self.bundle_files.append(
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
        self.media_files.append(
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
        self.table_files.append(
            {"url": url, "name": name, "size": size, "crc": md5, "includes": includes}
        )

    def to_resource(self) -> Resource:
        """Convert custom structures to generic structures."""
        resource = Resource()

        for bundle in self.bundle_files:
            resource.add(
                urljoin(self.bundle_url, bundle["name"]),
                urljoin("Bundle/", bundle["name"]),
                bundle["size"],
                bundle["crc"],
                "md5",
                ResourceType.bundle,
            )

        for media in self.media_files:
            resource.add(
                urljoin(self.media_url, media["url"]),
                urljoin("Media/", media["path"]),
                media["bytes"],
                media["crc"],
                "md5",
                ResourceType.media,
                {"media_type": media["media_type"]},
            )

        for table in self.table_files:
            resource.add(
                urljoin(self.table_url, table["url"]),
                urljoin("Table/", table["name"]),
                table["size"],
                table["crc"],
                "md5",
                ResourceType.table,
                {"includes": table["includes"]},
            )

        return resource


class GLResource:
    def __init__(self) -> None:
        self.base_url = ""
        self.bundle_files: list[dict] = []
        self.media_files: list[dict] = []
        self.table_files: list[dict] = []

    def __bool__(self) -> bool:
        return (
            bool(self.bundle_files)
            and bool(self.media_files)
            and bool(self.table_files)
        )

    def __len__(self) -> int:
        return len(self.bundle_files) + len(self.media_files) + len(self.table_files)

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
        if "TableBundles" in resource_path:
            pure_path = "Table" + resource_path.split("TableBundles", 1)[-1]
            self.table_files.append(
                {
                    "url": urljoin(self.base_url, resource_path),
                    "path": pure_path,
                    "size": resource_size,
                    "checksum": resource_hash,
                    "group": group,
                }
            )

        elif "MediaResources" in resource_path:
            pure_path = "Media" + resource_path.split("MediaResources", 1)[-1]
            self.table_files.append(
                {
                    "url": urljoin(self.base_url, resource_path),
                    "path": pure_path,
                    "size": resource_size,
                    "checksum": resource_hash,
                    "group": group,
                }
            )
        elif resource_path.endswith(".bundle"):
            pure_path = "Bundle/" + resource_path.split("/")[-1]
            self.table_files.append(
                {
                    "url": urljoin(self.base_url, resource_path),
                    "path": pure_path,
                    "size": resource_size,
                    "checksum": resource_hash,
                    "group": group,
                }
            )

    def to_resource(self) -> Resource:
        """Convert custom structures to generic structures."""
        resource = Resource()

        for table in self.table_files:
            resource.add(
                table["url"],
                table["path"],
                table["size"],
                table["checksum"],
                "md5",
                ResourceType.table,
            )
        for media in self.media_files:
            resource.add(
                media["url"],
                media["path"],
                media["size"],
                media["checksum"],
                "md5",
                ResourceType.media,
            )
        for bundle in self.bundle_files:
            resource.add(
                bundle["url"],
                bundle["path"],
                bundle["size"],
                bundle["checksum"],
                "md5",
                ResourceType.bundle,
            )

        return resource


class JPResource:
    def __init__(self) -> None:
        self.base_url = ""
        self.bundle_url = ""
        self.media_url = ""
        self.table_url = ""
        self.bundle_files: list[dict] = []
        self.media_files: list[dict] = []
        self.table_files: list[dict] = []

    def __bool__(self) -> bool:
        return (
            bool(self.bundle_files) or bool(self.media_files) or bool(self.table_files)
        )

    def __len__(self) -> int:
        return len(self.bundle_files) + len(self.media_files) + len(self.table_files)

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
        self.bundle_files.append(
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
        self.media_files.append(
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
        self.table_files.append(
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

        for bundle in self.bundle_files:
            resource.add(
                urljoin(self.bundle_url, bundle["name"]),
                urljoin("Bundle/", bundle["name"]),
                bundle["size"],
                bundle["crc"],
                "crc",
                ResourceType.bundle,
            )

        for media in self.media_files:
            resource.add(
                urljoin(self.media_url, media["path"]),
                urljoin("Media/", media["path"]),
                media["bytes"],
                media["crc"],
                "crc",
                ResourceType.media,
                {"media_type": media["media_type"]},
            )

        for table in self.table_files:
            resource.add(
                urljoin(self.table_url, table["name"]),
                urljoin("Table/", table["name"]),
                table["size"],
                table["crc"],
                "crc",
                ResourceType.table,
                {"includes": table["includes"]},
            )

        return resource
