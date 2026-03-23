import os
from os import path

from lib.console import ProgressBar, bar_increase, bar_text
from lib.encryption import zip_password
from utils.config import Config
from utils.util import FileUtils, TaskManager, ZipUtils


class MediaExtractor:
    MEDIA_FOLDER = path.join(Config.raw_dir, "Media")
    MEDIA_EXTRACT_FOLDER = path.join(Config.extract_dir, "Media")

    def extract_zip(self, extract_path: str, file_path: str, file_name: str) -> None:
        """Extract a single media zip."""
        password = zip_password(file_name.lower())
        extract_path = path.join(extract_path, file_name.removesuffix(".zip"))
        os.makedirs(extract_path, exist_ok=True)
        ZipUtils.extract_zip(
            file_path, extract_path, password=password, progress_bar=False
        )
