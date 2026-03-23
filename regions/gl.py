import re
from os import path

from lib.console import notice, print
from lib.downloader import FileDownloader
from lib.structure import GLResource, Resource
from regions.helper import RegionHelper
from utils.config import Config


class GLServer:
    CATALOG_URL = "https://api-pub.nexon.com/patch/v1.1/version-check"
    UPTODOWN_URL = "https://blue-archive-global.en.uptodown.com/android"
    APKPURE_URL = "https://d.apkpure.com/b/XAPK/com.nexon.bluearchive"
    APK_EXTRACT_FOLDER = path.join(Config.temp_dir, "Data")

    def main(self) -> Resource:
        """Main entry of GLServer."""
        version = Config.version
        apk_url = self.get_apk_url(version)

        if not version:
            notice("Version not specified. Automatically fetching latest...")
            version = Config.version = self.get_latest_version()

        notice(f"Current resource version: {version}")
        apk_path = RegionHelper.download_apk_file(apk_url, Config.temp_dir)
        RegionHelper.extract_xapk_file(
            apk_path, self.APK_EXTRACT_FOLDER, Config.temp_dir
        )
        server_url = self.get_server_url(version)
        print("Pulling catalog...")
        resources = self.get_resource_catalog(server_url)
        notice(f"Catalog: {resources}.")
        return resources

    def get_apk_url(self, version: str) -> str:
        """Retrieve the link to download the APK."""
        return (
            self.APKPURE_URL
            + f"?versionCode={version.split('.')[-1] or '?version=latest'}"
        )

    def get_latest_version(self) -> str:
        """Fetch the latest version from Uptodown."""
        if not (response := FileDownloader(self.UPTODOWN_URL).get_response()):
            raise LookupError("Cannot get latest version number.")

        if version_match := re.search(r"(\d+\.\d+\.\d+)", response.text):
            return version_match.group(1)

        raise LookupError("Unable to retrieve the version.")

    def get_resource_catalog(self, server_url: str) -> Resource:
        """GLServer uses persistent API and allows specifying the version."""
        resources = GLResource()
        try:
            resources.set_url_link(server_url.rsplit("/", 1)[0] + "/")

            if not (
                (resource_data := FileDownloader(server_url).get_response())
                and (resource := resource_data.json())
            ):
                raise LookupError(
                    "Failed to fetch resource catalog. Retry may solve the issue."
                )

            for res in resource.get("resources", []):
                resources.add_resource(
                    res["group"],
                    res["resource_path"],
                    res["resource_size"],
                    res["resource_hash"],
                )

            if not resources:
                notice(
                    "The catalog is incomplete, and some resource types may fail to be retrieved.",
                    "warn",
                )
        except Exception as e:
            raise LookupError(
                f"Encountered the following error while attempting to fetch catalog: {e}."
            ) from e
        return resources.to_resource()

    def get_server_url(self, version: str) -> str:
        """Get server url from game API."""
        request_body = {
            "market_game_id": "com.nexon.bluearchive",
            "market_code": "playstore",
            "curr_build_version": version,
            "curr_build_number": version.split(".")[-1],
        }

        if (
            server_resp := FileDownloader(
                self.CATALOG_URL, request_method="post", json=request_body
            ).get_response()
        ) and (server_url := server_resp.json()):
            return server_url.get("patch", {}).get("resource_path", "")

        return ""
