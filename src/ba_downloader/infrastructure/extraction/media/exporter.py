import shutil
from collections.abc import Callable
from pathlib import Path
from uuid import uuid4
from zipfile import ZipFile

from ba_downloader.domain.exceptions import OperationCancelledError
from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.infrastructure.files.atomic import publish_staged_directory
from ba_downloader.infrastructure.schema.crypto import zip_password


class MediaExtractor:
    def __init__(self, context: ExecutionContext) -> None:
        self.context = context

    @property
    def media_extract_folder(self) -> str:
        return str(self.context.workspace.extracted_media)

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
        extract_dest.parent.mkdir(parents=True, exist_ok=True)
        staging_dest = extract_dest.with_name(
            f".{extract_dest.name}.staging-{uuid4().hex}"
        )
        staging_dest.mkdir()
        try:
            with ZipFile(file_path, "r") as media_zip:
                media_zip.setpassword(password)
                members = media_zip.infolist()
                total_members = len(members)
                for index, member in enumerate(members, start=1):
                    if should_stop is not None and should_stop():
                        raise OperationCancelledError(
                            "Media extraction cancelled by user."
                        )
                    media_zip.extract(member, staging_dest, pwd=password)
                    if progress_callback is not None:
                        progress_callback(f"{index}/{total_members} members")
            publish_staged_directory(staging_dest, extract_dest)
        finally:
            shutil.rmtree(staging_dest, ignore_errors=True)
