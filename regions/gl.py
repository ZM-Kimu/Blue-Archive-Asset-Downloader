import re

from lib.console import notice, print
from lib.downloader import FileDownloader
from lib.structure import GLResource, Resource
from utils.config import Config


class GLServer:
    UPTODOWN_URL = "https://blue-archive-global.en.uptodown.com/android"
    MANIFEST_URL = "https://api-pub.nexon.com/patch/v1.1/version-check"

    def main(self) -> Resource:
        """Main entry of GLServer."""
        version = Config.version
        if not version:
            notice("Version not specified. Automatically fetching latest...")
            version = Config.version = self.get_latest_version()
        notice(f"Current resource version: {version}")
        server_url = self.get_server_url(version)
        print("Pulling catalog...")
        resources = self.get_resource_manifest(server_url)
        notice(f"Catalog: {resources}.")
        return resources

    def get_latest_version(self) -> str:
        """Fetch the latest version from Uptodown."""
        if not (response := FileDownloader(self.UPTODOWN_URL).get_response()):
            raise LookupError("Cannot fetch resource catalog.")

        if version_match := re.search(r"(\d+\.\d+\.\d+)", response.text):
            return version_match.group(1)

        raise LookupError("Unable to retrieve the version.")

    def get_resource_manifest(self, server_url: str) -> Resource:
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
                f"Encountered the following error while attempting to fetch manifest: {e}."
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
                self.MANIFEST_URL, request_method="post", json=request_body
            ).get_response()
        ) and (server_url := server_resp.json()):
            return server_url.get("patch", {}).get("resource_path", "")

        return ""
