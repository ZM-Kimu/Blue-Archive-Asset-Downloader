from typing import Any, Iterator
from urllib.parse import urljoin


class Resource:
    def __init__(self) -> None:
        # 5 basic classes in Resource. url, path, size, checksum, check_type, addition
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

    def add_resource(self, url: str, data: dict) -> None:
        data["url"] = url
        self.resources.append(data)

    def add_resource_item(self, item: dict) -> None:
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
        check_type: str,
        addition: dict = {},
    ) -> None:
        self.resources.append(
            {
                "url": url,
                "path": path,
                "size": size,
                "checksum": checksum,
                "check_type": check_type,
                "addition": addition,
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
        self.bundle_file = []
        self.media_file = []
        self.table_file = []

    def __bool__(self) -> bool:
        return (
            bool(self.bundle_file) and bool(self.media_file) and bool(self.table_file)
        )

    def __len__(self) -> int:
        return len(self.bundle_file) + len(self.media_file) + len(self.table_file)

    def __str__(self) -> str:
        return f"{len(self.bundle_file)} bundles; {len(self.media_file)} media files; {len(self.table_file)} table files"

    def set_url_link(self, base_url: str, bundle: str, media: str, table: str) -> None:
        self.base_url = base_url
        self.bundle_url = urljoin(self.base_url, bundle)
        self.media_url = urljoin(self.base_url, media)
        self.table_url = urljoin(self.base_url, table)

    def add_bundle_resource(
        self, name: str, size: int, md5: str, is_inbuild: bool
    ) -> None:
        self.bundle_file.append(
            {"name": name, "size": size, "crc": md5, "is_inbuild": is_inbuild}
        )

    def add_media_resource(
        self, url: str, file_path: str, media_type: str, bytes: int, md5: str
    ) -> None:
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
        self.table_file.append(
            {"url": url, "name": name, "size": size, "crc": md5, "includes": includes}
        )

    def to_resource(self) -> Resource:
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


class JPResource:
    def __init__(self) -> None:
        self.base_url = ""
        self.bundle_url = ""
        self.media_url = ""
        self.table_url = ""
        self.bundle_file = []
        self.media_file = []
        self.table_file = []

    def __bool__(self) -> bool:
        return (
            bool(self.bundle_file) and bool(self.media_file) and bool(self.table_file)
        )

    def __len__(self) -> int:
        return len(self.bundle_file) + len(self.media_file) + len(self.table_file)

    def __str__(self) -> str:
        return f"{len(self.bundle_file)} bundles; {len(self.media_file)} media files; {len(self.table_file)} table files"

    def set_url_link(self, base_url: str, bundle: str, media: str, table: str) -> None:
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
