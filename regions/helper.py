import os

from lib.console import ProgressBar
from lib.downloader import FileDownloader
from utils.util import ZipUtils


class RegionHelper:

    @staticmethod
    def download_apk_file(apk_url: str, dest_dir: str) -> str:
        """Download the APK file."""
        if not (
            (
                apk_req := FileDownloader(
                    apk_url,
                    request_method="get",
                    enable_progress=True,
                    bypass_cloudflare=True,
                )
            )
            and (apk_data := apk_req.get_response(True))
        ):
            raise LookupError("Cannot fetch apk info.")

        apk_path = os.path.join(
            dest_dir,
            apk_data.headers.get("Content-Disposition", "")
            .rsplit('"', 2)[-2]
            .encode("ISO8859-1")
            .decode(),
        )
        apk_size = int(apk_data.headers.get("Content-Length", 0))

        if os.path.exists(apk_path) and os.path.getsize(apk_path) == apk_size:
            return apk_path

        with ProgressBar(apk_size, "Downloading APK...", "MB", 1048576) as bar:
            bar.item_text(apk_path.split("/")[-1])
            apk_req.save_file(apk_path)

        return apk_path

    @staticmethod
    def extract_xapk_file(apk_path: str, extract_dest: str, temp_dir: str) -> None:
        """Extract the XAPK file."""
        apk_files = ZipUtils.extract_zip(apk_path, temp_dir, keywords=["apk"])

        ZipUtils.extract_zip(apk_files, extract_dest, zips_dir=temp_dir)
