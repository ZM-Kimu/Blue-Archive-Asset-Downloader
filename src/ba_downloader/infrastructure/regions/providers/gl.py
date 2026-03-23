import re
from os import path

from ba_downloader.domain.models.region_catalog import RegionCatalogResult
from ba_downloader.domain.models.resource import GLResource, Resource
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.http import HttpClientPort
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.infrastructure.apk import download_package_file, extract_xapk_file


class GLServer:
    CATALOG_URL = "https://api-pub.nexon.com/patch/v1.1/version-check"
    UPTODOWN_URL = "https://blue-archive-global.en.uptodown.com/android"
    APKPURE_URL = "https://d.apkpure.com/b/XAPK/com.nexon.bluearchive"

    def __init__(self, http_client: HttpClientPort, logger: LoggerPort) -> None:
        self.http_client = http_client
        self.logger = logger

    def apk_extract_folder(self, context: RuntimeContext) -> str:
        return path.join(context.temp_dir, "Data")

    def load_catalog(self, context: RuntimeContext) -> RegionCatalogResult:
        """Main entry of GLServer."""
        version = context.version
        resolved_context = context

        if not version:
            self.logger.warn("Version not specified. Automatically fetching latest...")
            version = self.get_latest_version()
            resolved_context = context.with_updates(version=version)

        apk_url = self.get_apk_url(version)
        self.logger.warn(f"Current resource version: {version}")
        apk_path = download_package_file(
            self.http_client,
            self.logger,
            apk_url,
            resolved_context.temp_dir,
            transport="browser",
        )
        extract_xapk_file(
            apk_path,
            self.apk_extract_folder(resolved_context),
            resolved_context.temp_dir,
        )
        server_url = self.get_server_url(version)
        self.logger.info("Pulling catalog...")
        resources = self.get_resource_catalog(server_url)
        self.logger.warn(f"Catalog: {resources}.")
        return RegionCatalogResult(resources=resources, context=resolved_context)

    def get_apk_url(self, version: str) -> str:
        """Retrieve the link to download the APK."""
        if not version:
            return f"{self.APKPURE_URL}?version=latest"
        return f"{self.APKPURE_URL}?versionCode={version.split('.')[-1]}"

    def get_latest_version(self) -> str:
        """Fetch the latest version from Uptodown."""
        response = self.http_client.request("GET", self.UPTODOWN_URL)

        if version_match := re.search(r"(\d+\.\d+\.\d+)", response.text):
            return version_match.group(1)

        raise LookupError("Unable to retrieve the version.")

    def get_resource_catalog(self, server_url: str) -> Resource:
        """GLServer uses persistent API and allows specifying the version."""
        resources = GLResource()
        try:
            resources.set_url_link(server_url.rsplit("/", 1)[0] + "/")

            resource = self.http_client.request("GET", server_url).json()

            for res in resource.get("resources", []):
                resources.add_resource(
                    res["group"],
                    res["resource_path"],
                    res["resource_size"],
                    res["resource_hash"],
                )

            if not resources:
                self.logger.warn(
                    "The catalog is incomplete, and some resource types may fail to be retrieved.",
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

        server_url = self.http_client.request(
            "POST",
            self.CATALOG_URL,
            json=request_body,
        ).json()
        return server_url.get("patch", {}).get("resource_path", "")

