import shutil
from collections.abc import Callable
from pathlib import Path
from uuid import uuid4
from zipfile import ZipFile

from ba_downloader.domain.exceptions import OperationCancelledError
from ba_downloader.domain.models.asset import AssetType
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.infrastructure.schema.crypto import zip_password
from ba_downloader.infrastructure.storage.workspace_paths import extracted_type_root


class MediaExtractor:
    def __init__(self, context: RuntimeContext) -> None:
        self.context = context

    @property
    def media_extract_folder(self) -> str:
        return str(extracted_type_root(self.context, AssetType.media))

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
            self._publish(staging_dest, extract_dest)
        finally:
            shutil.rmtree(staging_dest, ignore_errors=True)

    @staticmethod
    def _publish(staging_dest: Path, extract_dest: Path) -> None:
        backup_dest = extract_dest.with_name(
            f".{extract_dest.name}.backup-{uuid4().hex}"
        )
        if extract_dest.exists():
            extract_dest.replace(backup_dest)
        try:
            staging_dest.replace(extract_dest)
        except BaseException:
            if backup_dest.exists() and not extract_dest.exists():
                backup_dest.replace(extract_dest)
            raise
        finally:
            shutil.rmtree(backup_dest, ignore_errors=True)
