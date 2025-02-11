import base64
import json
import os
import re
import struct
from io import BytesIO
from os import path
from typing import Any, Literal
from urllib.parse import urljoin

from cloudscraper import create_scraper

from lib.console import ProgressBar, notice, print
from lib.downloader import FileDownloader
from lib.encryption import convert_string, create_key
from lib.structure import JPResource, Resource
from utils.config import Config
from utils.util import UnityUtils, ZipUtils


class JPServer:
    INFO_URL = "https://prod-noticeindex.bluearchiveyostar.com/prod/index.json"
    UPTODOWN_INFO_URL = "https://blue-archive.jp.uptodown.com/android"
    APKPURE_URL = (
        "https://d.apkpure.com/b/XAPK/com.YostarJP.BlueArchive?nc=arm64-v8a&sv=24"
    )
    APK_EXTRACT_FOLDER = path.join(Config.temp_dir, "Data")

    def main(self) -> Resource:
        """Main entry of JPServer."""
        if Config.version:
            notice("Specifying a version is not allowed with JPServer.")

        notice("Automatically fetching latest...")
        version = Config.version = self.get_latest_version()
        notice(f"Current resource version: {version}")

        apk_url = self.get_apk_url(version)
        apk_path = self.download_apk_file(apk_url)
        self.extract_apk_file(apk_path)
        server_url = self.get_server_url()

        print("Pulling catalog...")
        resources = self.get_resource_manifest(server_url)
        notice(f"Catalog: {resources}.")
        return resources

    def download_apk_file(self, apk_url: str) -> str:
        """Download the APK file."""
        print("Download APK to retrieve server URL...")
        if not (
            (
                apk_req := FileDownloader(
                    apk_url,
                    request_method="get",
                    use_cloud_scraper=True,
                )
            )
            and (apk_data := apk_req.get_response(True))
        ):
            raise LookupError("Cannot fetch apk info.")

        apk_path = path.join(
            Config.temp_dir,
            apk_data.headers["Content-Disposition"]
            .rsplit('"', 2)[-2]
            .encode("ISO8859-1")
            .decode(),
        )
        apk_size = int(apk_data.headers.get("Content-Length", 0))

        if path.exists(apk_path) and path.getsize(apk_path) == apk_size:
            return apk_path

        with ProgressBar(apk_size, "Downloading APK...", "B") as bar:
            bar.item_text(apk_path.split("/")[-1])
            FileDownloader(
                apk_url,
                request_method="get",
                enable_progress=True,
                use_cloud_scraper=True,
            ).save_file(apk_path)

        return apk_path

    def extract_apk_file(self, apk_path: str) -> None:
        """Extract the XAPK file."""
        apk_files = ZipUtils.extract_zip(
            apk_path, path.join(Config.temp_dir), keywords=["apk"]
        )

        ZipUtils.extract_zip(
            apk_files, self.APK_EXTRACT_FOLDER, zips_dir=Config.temp_dir
        )

    def get_apk_url(self, version: str) -> str:
        """Retrieve the link to download the APK."""
        return self.APKPURE_URL + f"&versionCode={version.split('.')[-1]}"

    def get_latest_version(self) -> str:
        """Obtain the version number from the notification link."""
        uptodown_version = ""

        if not (info_official := FileDownloader(self.INFO_URL).get_response()):
            raise LookupError("Cannot access info url to get latest version.")

        official_version: str = info_official.json().get("LatestClientVersion", "")

        if not (info_uptodown := FileDownloader(self.UPTODOWN_INFO_URL).get_response()):
            raise LookupError("Cannot access uptodown to get latest version.")

        uptodown_match = re.search(r"(\d+\.\d+\.\d+)", info_uptodown.text)

        if uptodown_match:
            uptodown_version = uptodown_match.group(1)

        if not (official_version or uptodown_version):
            raise LookupError(
                "Unable to retrieve the version. Configure it manually if possible."
            )

        if int(official_version.replace(".", "")) < int(
            uptodown_version.replace(".", "")
        ):
            notice(
                f"The version from uptodown is {uptodown_version}, official is {official_version}. Will use uptodown version."
            )
            return uptodown_version

        return official_version

    def get_resource_manifest(self, server_url: str) -> Resource:
        """JP server use different API for each version, and media and table files are encrypted."""
        resources = JPResource()
        try:
            if not (api := FileDownloader(server_url).get_response()):
                raise LookupError(
                    "Cannot access resource url. Retry may solve this issue."
                )

            base_url = (
                api.json()["ConnectionGroups"][0]["OverrideConnectionGroups"][-1][
                    "AddressablesCatalogUrlRoot"
                ]
                + "/"
            )

            resources.set_url_link(
                base_url, "Android/", "MediaResources/", "TableBundles/"
            )

            if table_data := FileDownloader(
                urljoin(resources.table_url, "TableCatalog.bytes")
            ).get_bytes():
                JPCatalogDecoder.decode_to_manifest(table_data, resources, "table")
            else:
                notice(
                    "Failed to fetch table catalog. Retry may solve this issue.",
                    "error",
                )

            if media_data := FileDownloader(
                urljoin(resources.media_url, "Catalog/MediaCatalog.bytes")
            ).get_bytes():
                JPCatalogDecoder.decode_to_manifest(media_data, resources, "media")
            else:
                notice(
                    "Failed to fetch media catalog. Retry may solve this issue.",
                    "error",
                )

            if (
                bundle_data := FileDownloader(
                    urljoin(resources.bundle_url, "bundleDownloadInfo.json")
                ).get_response()
            ) and bundle_data.headers.get("Content-Type") == "application/json":
                bundle_catalog = bundle_data.json()["BundleFiles"]
                for bundle in bundle_catalog:
                    resources.add_bundle_resource(
                        bundle["Name"],
                        bundle["Size"],
                        bundle["Crc"],
                        bundle["IsPrologue"],
                        bundle["IsSplitDownload"],
                    )
            else:
                notice(
                    "Failed to fetch bundle catalog. Retry may solve this issue.",
                    "error",
                )

            if not resources:
                raise FileNotFoundError("Cannot pull the manifest.")

            return resources.to_resource()

        except Exception as e:
            raise LookupError(
                f"Encountered the following error while attempting to fetch manifest: {e}."
            ) from e

    def __decode_server_url(self, data: bytes) -> str:
        """
        Decodes the server URL from the given data.

        Args:
            data (bytes): Binary data to decode.

        Returns:
            str: Decoded server URL.
        """
        ciphers = {
            "ServerInfoDataUrl": "X04YXBFqd3ZpTg9cKmpvdmpOElwnamB2eE4cXDZqc3ZgTg==",
            "DefaultConnectionGroup": "tSrfb7xhQRKEKtZvrmFjEp4q1G+0YUUSkirOb7NhTxKfKv1vqGFPEoQqym8=",
            "SkipTutorial": "8AOaQvLC5wj3A4RC78L4CNEDmEL6wvsI",
            "Language": "wL4EWsDv8QX5vgRaye/zBQ==",
        }
        b64_data = base64.b64encode(data).decode()
        json_str = convert_string(b64_data, create_key("GameMainConfig"))
        obj = json.loads(json_str)
        encrypted_url = obj[ciphers["ServerInfoDataUrl"]]
        url = convert_string(encrypted_url, create_key("ServerInfoDataUrl"))
        return url

    def get_server_url(self) -> str:
        """Decrypt the server version from the game's binary files."""
        print("Retrieving game info...")
        url = version = ""
        for dir, _, files in os.walk(
            path.join(self.APK_EXTRACT_FOLDER, "assets", "bin", "Data")
        ):
            for file in files:
                if url_obj := UnityUtils.search_unity_pack(
                    path.join(dir, file), ["TextAsset"], ["GameMainConfig"], True
                ):
                    url = self.__decode_server_url(url_obj[0].read().m_Script.encode("utf-8", "surrogateescape"))  # type: ignore
                    notice(f"Get URL successfully: {url}")
                if version_obj := UnityUtils.search_unity_pack(
                    path.join(dir, file), ["PlayerSettings"]
                ):
                    try:
                        version = version_obj[0].read().bundleVersion  # type: ignore
                    except:
                        version = "unavailable"
                    print(f"The apk version is {version}.")

                if url and version:
                    break

        if not url:
            raise LookupError("Cannot find server url from apk.")
        if version and version != Config.version:
            notice("Server version is different with apk version.")
        elif not version:
            notice("Cannot retrieve apk version data.")
        return url


I8: str = "b"
I32: str = "i"
I64: str = "q"
BOOL: str = "?"


class JPCatalogDecoder:

    class Reader:
        def __init__(self, initial_bytes) -> None:
            self.io = BytesIO(initial_bytes)

        def read(self, fmt: str) -> Any:
            """Use struct read bytes by giving a format char."""
            return struct.unpack(fmt, self.io.read(struct.calcsize(fmt)))[0]

        def read_string(self) -> str:
            """Read string."""
            return self.io.read(self.read(I32)).decode(
                encoding="utf-8", errors="replace"
            )

        def read_table_includes(self) -> list[str]:
            """Read talbe inculdes."""
            size = self.read(I32)
            if size == -1:
                return []
            self.read(I32)
            includes = []
            for i in range(size):
                includes.append(self.read_string())
                if i != size - 1:
                    self.read(I32)
            return includes

    @staticmethod
    def decode_to_manifest(
        raw_data: bytes, container: JPResource, type: Literal["table", "media"]
    ) -> dict[str, object]:
        """Used to decode bytes file to readable data structure. Data will return decoded and add to container.

        Args:
            raw_data (bytes): Binary data.
            container (JPResource): Container to storage manifest.
            type (Literal[&quot;table&quot;, &quot;media&quot;]): Data type.

        Returns:
            dict([str, object]): Manifest list.
        """
        data = JPCatalogDecoder.Reader(raw_data)

        manifest: dict[str, object] = {}

        data.read(I8)
        item_num = data.read(I32)

        for _ in range(item_num):
            if type == "media":
                key, obj = JPCatalogDecoder.__decode_media_manifest(data, container)
            else:
                key, obj = JPCatalogDecoder.__decode_table_manifest(data, container)
            manifest[key] = obj
        return manifest

    @classmethod
    def __decode_media_manifest(
        cls, data: Reader, container: JPResource
    ) -> tuple[str, dict[str, object]]:
        data.read(I32)
        key = data.read_string()
        data.read(I8)
        data.read(I32)
        path = data.read_string()
        data.read(I32)
        file_name = data.read_string()
        bytes = data.read(I64)
        crc = data.read(I64)
        is_prologue = data.read(BOOL)
        is_split_download = data.read(BOOL)
        media_type = data.read(I32)

        path = path.replace("\\", "/")
        container.add_media_resource(
            key, path, file_name, media_type, bytes, crc, is_prologue, is_split_download
        )

        return key, {
            "path": path,
            "file_name": file_name,
            "type": media_type,
            "bytes": bytes,
            "crc": crc,
            "is_prologue": is_prologue,
            "is_split_download": is_split_download,
        }

    @classmethod
    def __decode_table_manifest(
        cls, data: Reader, container: JPResource
    ) -> tuple[str, dict[str, object]]:
        data.read(I32)
        key = data.read_string()
        data.read(I8)
        data.read(I32)
        name = data.read_string()
        size = data.read(I64)
        crc = data.read(I64)
        is_in_build = data.read(BOOL)
        is_changed = data.read(BOOL)
        is_prologue = data.read(BOOL)
        is_split_download = data.read(BOOL)
        includes = data.read_table_includes()

        container.add_table_resource(
            key,
            name,
            size,
            crc,
            is_in_build,
            is_changed,
            is_prologue,
            is_split_download,
            includes,
        )

        return key, {
            "name": name,
            "size": size,
            "crc": crc,
            "is_in_build": is_in_build,
            "is_changed": is_changed,
            "is_prologue": is_prologue,
            "is_split_download": is_split_download,
            "includes": includes,
        }
