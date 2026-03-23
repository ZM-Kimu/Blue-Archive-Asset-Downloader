import os
from os import path

from lib.encryption import zip_password
from utils.config import Config
from utils.util import ZipUtils


class MediaExtractor:
    MEDIA_FOLDER = path.join(Config.raw_dir, "Media")
    MEDIA_EXTRACT_FOLDER = path.join(Config.extract_dir, "Media")

    def extract_zip(self, file_path: str) -> None:
        """Extract a single media zip."""
        file_name = path.basename(file_path)
        password = zip_password(file_name.lower())
        extract_dest = path.join(
            self.MEDIA_EXTRACT_FOLDER, file_name.removesuffix(".zip")
        )
        os.makedirs(extract_dest, exist_ok=True)
        ZipUtils.extract_zip(
            file_path, extract_dest, password=password, progress_bar=False
        )
