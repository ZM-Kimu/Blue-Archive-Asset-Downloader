import os
import re
from os import path
from urllib.parse import urljoin

from cloudscraper import create_scraper

from resource_extractor import Extractor, JPCatalogDecoder
from utils.config import Config
from utils.console import ProgressBar, notice, print
from utils.downloader import FileDownloader
from utils.resource_structure import JPResource, Resource


class JPServer:
    def __init__(self) -> None:
        self.urls = {
            "info": "https://prod-noticeindex.bluearchiveyostar.com/prod/index.json",
            "uptodown_info": "https://blue-archive.jp.uptodown.com/android",
            "apkpure": "https://d.apkpure.com/b/XAPK/com.YostarJP.BlueArchive?nc=arm64-v8a&sv=24",
        }

    def main(self) -> Resource:
        """Main entry of JPServer."""
        version = Config.version
        if not version:
            notice("Version not specified. Automatically fetching latest...")
            version = Config.version = self.get_latest_version()
        notice(f"Current resource version: {version}")
        apk_url = self.get_apk_url(version)
        apk_path = self.download_apk_file(apk_url)
        self.extract_apk_file(apk_path)
        server_url = self.get_server_url()
        print("Pulling manifest...")
        resources = self.get_resource_manifest(server_url)
        notice(f"Manifest: {resources}.")
        return resources

    def download_apk_file(self, apk_url: str) -> str:
        """Download the APK file."""
        print("Download APK to retrieve server URL...")
        data = create_scraper().get(apk_url, stream=True, proxies=Config.proxy)
        apk_path = path.join(
            Config.temp_dir,
            data.headers["Content-Disposition"]
            .rsplit('"', 2)[-2]
            .encode("ISO8859-1")
            .decode(),
        )
        apk_size = int(data.headers.get("Content-Length", 0))

        if not (path.exists(apk_path) and path.getsize(apk_path) == apk_size):
            with ProgressBar(apk_size, "Downloading APK...", "MB", 1048576) as bar:
                bar.item_text(apk_path.split("/")[-1])
                with open(apk_path, "wb") as apk:
                    for chunck in data.iter_content(chunk_size=4096):
                        apk.write(chunck)
                        bar.increase(len(chunck))
        return apk_path

    def extract_apk_file(self, apk_path: str) -> None:
        "Extract the XAPK file."
        apk_files = Extractor.extract_zip(
            apk_path, path.join(Config.temp_dir), keywords=["apk"]
        )

        Extractor.extract_zip(
            apk_files,
            path.join(Config.temp_dir, "data"),
            keywords=["bin/Data"],
            zip_dir=Config.temp_dir,
        )

    def get_apk_url(self, version: str) -> str:
        """Retrieve the link to download the APK."""
        return self.urls["apkpure"] + f"&versionCode={version.split('.')[-1]}"

    def get_latest_version(self) -> str:
        """Obtain the version number from the notification link."""
        uptodown_version = ""

        info_official = FileDownloader(self.urls["info"]).get_response()

        official_version: str = info_official.json().get("LatestClientVersion", "")

        info_uptodown = FileDownloader(self.urls["uptodown_info"]).get_response()

        uptodown_match = re.search(r"(\d+\.\d+\.\d+)", info_uptodown.text)

        if uptodown_match:
            uptodown_version = uptodown_match.group(1)

        if not (official_version or uptodown_version):
            raise LookupError(
                "Unable to retrieve the version. Configure it manually if possible."
            )

        if (
            official_version
            and uptodown_version
            and official_version != uptodown_version
            and int(uptodown_version.rsplit(".", 1)[-1])
            > int(official_version.rsplit(".", 1)[-1])
        ):
            return uptodown_version

        return official_version

    def get_resource_manifest(self, server_url: str) -> Resource:
        """JP server use different API for each version, and media and table files are encrypted."""
        resources = JPResource()
        try:
            api = FileDownloader(server_url).get_response()

            base_url = (
                api.json()["ConnectionGroups"][0]["OverrideConnectionGroups"][-1][
                    "AddressablesCatalogUrlRoot"
                ]
                + "/"
            )

            resources.set_url_link(
                base_url, "Android/", "MediaResources/", "TableBundles/"
            )

            table_data = FileDownloader(
                urljoin(resources.table_url, "TableCatalog.bytes")
            ).get_response()

            media_data = FileDownloader(
                urljoin(resources.media_url, "MediaCatalog.bytes")
            ).get_response()

            bundle_data = FileDownloader(
                urljoin(resources.bundle_url, "bundleDownloadInfo.json")
            ).get_response()

            if (
                table_data.headers.get("Content-Type") == "binary/octet-stream"
                and media_data.headers.get("Content-Type") == "binary/octet-stream"
            ):
                JPCatalogDecoder.decode_to_manifest(
                    table_data.content, resources, "table"
                )
                JPCatalogDecoder.decode_to_manifest(
                    media_data.content, resources, "media"
                )
            else:
                notice(
                    f"Failed to fetch table or media catalog because table is {table_data.reason} and media is {media_data.reason}. Retry may solve the issue.",
                    "error",
                )

            if bundle_data.headers.get("Content-Type") == "application/json":
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
                    f"Failed to fetch bundle catalog because {bundle_data.reason}. Retry may solve the issue.",
                    "error",
                )

            if not resources:
                raise FileNotFoundError("Cannot pull the manifest.")
        except Exception as e:
            raise LookupError(
                f"Encountered the following error while attempting to fetch manifest: {e}."
            ) from e
        return resources.to_resource()

    def get_server_url(self) -> str:
        """Decrypt the server version from the game's binary files."""
        print("Retrieving game info...")
        url = version = ""
        for dir, _, files in os.walk(
            path.join(Config.temp_dir, "data", "assets", "bin", "Data")
        ):
            for file in files:
                url_obj = Extractor.filter_unity_pack(
                    path.join(dir, file),
                    ["TextAsset"],
                    ["GameMainConfig"],
                    True,
                )
                version_obj = Extractor.filter_unity_pack(
                    path.join(dir, file), ["PlayerSettings"]
                )
                if url_obj:
                    url = Extractor.decode_server_url(url_obj[0].read().script)
                    notice(f"Get URL successfully: {url}")
                if version_obj:
                    ver = re.search(rb"\d+?\.\d+?\.\d+", version_obj[0].get_raw_data())
                    version = ver.group(0).decode() if ver else "unavailable"
                    print(f"The apk version is {version}.")

        if not url:
            raise LookupError("Cannot find server url from apk.")
        if version and version != Config.version:
            notice("Server version is different with apk version.")
        elif not version:
            notice("Cannot retrieve apk version data.", "error")
        return url
