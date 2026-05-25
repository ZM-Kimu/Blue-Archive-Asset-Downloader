from collections.abc import Callable
from pathlib import Path
from zipfile import ZipFile

from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.infrastructure.schema.crypto import zip_password


class MediaExtractor:
    def __init__(self, context: RuntimeContext) -> None:
        self.context = context

    @property
    def media_extract_folder(self) -> str:
        return str(Path(self.context.extract_dir) / "Media")

    def extract_zip(
        self,
        file_path: str,
        *,
        should_stop: Callable[[], bool] | None = None,
        progress_callback: Callable[[str], None] | None = None,
    ) -> None:
        """Extract a single media zip."""
        file_name = Path(file_path).name
        password = zip_password(file_name.lower())
        extract_dest = Path(self.media_extract_folder) / file_name.removesuffix(".zip")
        extract_dest.mkdir(parents=True, exist_ok=True)
        with ZipFile(file_path, "r") as media_zip:
            media_zip.setpassword(password)
            members = media_zip.infolist()
            total_members = len(members)
            for index, member in enumerate(members, start=1):
                if should_stop is not None and should_stop():
                    raise RuntimeError("Extraction cancelled by user.")
                media_zip.extract(member, extract_dest, pwd=password)
                if progress_callback is not None:
                    progress_callback(f"{index}/{total_members} members")
