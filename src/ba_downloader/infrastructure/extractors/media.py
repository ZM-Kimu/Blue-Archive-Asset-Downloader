from pathlib import Path
from zipfile import ZipFile

from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.shared.crypto.encryption import zip_password


class MediaExtractor:
    def __init__(self, context: RuntimeContext) -> None:
        self.context = context

    @property
    def media_extract_folder(self) -> str:
        return str(Path(self.context.extract_dir) / "Media")

    def extract_zip(self, file_path: str) -> None:
        """Extract a single media zip."""
        file_name = Path(file_path).name
        password = zip_password(file_name.lower())
        extract_dest = Path(self.media_extract_folder) / file_name.removesuffix(".zip")
        extract_dest.mkdir(parents=True, exist_ok=True)
        with ZipFile(file_path, "r") as media_zip:
            media_zip.setpassword(password)
            media_zip.extractall(extract_dest)

