import re

from lib.console import notice, print
from lib.downloader import FileDownloader
from utils.config import Config
from utils.resource_structure import GLResource, Resource


class GLServer:
    def __init__(self) -> None:
        self.urls = {
            "uptodown": "https://blue-archive-global.en.uptodown.com/android",
            "manifest": "https://api-pub.nexon.com/patch/v1.1/version-check",
        }

    def main(self) -> Resource:
        """Main entry of GLServer."""
        version = Config.version
        if not version:
            notice("Version not specified. Automatically fetching latest...")
            version = Config.version = self.get_latest_version()
        notice(f"Current resource version: {version}")
        server_url = self.get_server_url(version)
        print("Pulling manifest...")
        resources = self.get_resource_manifest(server_url)
        notice(f"Manifest: {resources}.")
        return resources

    def get_latest_version(self) -> str:
        """Fetch the latest version from Uptodown."""
        version_match: re.Match | None = None
        response = FileDownloader(self.urls["uptodown"]).get_response()

        if version_match := re.search(r"(\d+\.\d+\.\d+)", response.text):
            return version_match.group(1)

        if not version_match:
            raise LookupError(
                "Unable to retrieve the version. Configure it manually if possible."
            )
        return ""

    def get_resource_manifest(self, server_url: str) -> Resource:
        """GLServer uses persistent API and allows specifying the version."""
        resources = GLResource()
        try:
            resource_data = FileDownloader(server_url).get_response()

            resources.set_url_link(server_url.rsplit("/", 1)[0] + "/")

            if not (resource := resource_data.json()):
                notice(
                    f"Failed to fetch resource because {resource_data.reason}. Retry may solve the issue.",
                    "error",
                )

            for res in resource.get("resources", []):
                resources.add_resource(
                    res["group"],
                    res["resource_path"],
                    res["resource_size"],
                    res["resource_hash"],
                )

            if not resources:
                raise FileNotFoundError("Cannot pull the manifest.")
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

        server_url = FileDownloader(
            self.urls["manifest"], request_method="post", json=request_body
        ).get_response()

        return server_url.json().get("patch", {}).get("resource_path", "")
