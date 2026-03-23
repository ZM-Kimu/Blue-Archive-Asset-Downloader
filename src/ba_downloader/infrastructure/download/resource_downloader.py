from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

from ba_downloader.domain.models.resource import Resource, ResourceItem, ResourceType
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.download import ResourceDownloaderPort
from ba_downloader.domain.ports.http import HttpClientPort
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.infrastructure.extractors.bundle import BundleExtractor
from ba_downloader.infrastructure.extractors.media import MediaExtractor
from ba_downloader.infrastructure.extractors.table import TableExtractor
from ba_downloader.infrastructure.progress.rich_progress import RichProgressReporter
from ba_downloader.shared.crypto.encryption import calculate_crc, calculate_md5


class ResourceDownloader(ResourceDownloaderPort):
    def __init__(self, http_client: HttpClientPort, logger: LoggerPort) -> None:
        self.http_client = http_client
        self.logger = logger
        self._bundle_lock = Lock()

    def verify_and_download(self, resources: Resource, context: RuntimeContext) -> None:
        if not resources:
            return

        Path(context.temp_dir).mkdir(parents=True, exist_ok=True)
        Path(context.raw_dir).mkdir(parents=True, exist_ok=True)
        Path(context.extract_dir).mkdir(parents=True, exist_ok=True)

        resources.sorted_by_size()
        pending = self._verify_resources(resources, context)
        if not pending:
            self.logger.warn("All files have already been downloaded.")
            return

        attempt = 0
        while pending and attempt <= context.max_retries:
            if attempt:
                self.logger.warn(
                    f"Retrying {len(pending)} failed files. Attempt {attempt}/{context.max_retries}."
                )
            pending = self._download_resources(pending, context)
            attempt += 1

        if pending:
            self.logger.error(f"Failed to download {len(pending)} files after retries.")
        else:
            self.logger.warn("All files have been downloaded to your computer.")

    def _verify_resources(
        self,
        resources: Resource,
        context: RuntimeContext,
    ) -> list[ResourceItem]:
        pending: list[ResourceItem] = []
        workers = min(max(context.threads, 1), max(len(resources), 1))
        with RichProgressReporter(len(resources), "Verifying assets...") as progress:
            with ThreadPoolExecutor(max_workers=workers) as executor:
                future_map = {
                    executor.submit(self._verify_resource, resource, context): resource
                    for resource in resources
                }
                for future in as_completed(future_map):
                    resource_item, verified = future.result()
                    progress.set_description(f"Verifying {Path(resource_item.path).name}")
                    progress.advance()
                    if not verified:
                        pending.append(resource_item)
        return pending

    def _download_resources(
        self,
        resources: list[ResourceItem],
        context: RuntimeContext,
    ) -> list[ResourceItem]:
        failed: list[ResourceItem] = []
        workers = min(max(context.threads, 1), max(len(resources), 1))
        with RichProgressReporter(len(resources), "Downloading assets...") as progress:
            with ThreadPoolExecutor(max_workers=workers) as executor:
                future_map = {
                    executor.submit(self._download_resource, resource, context): resource
                    for resource in resources
                }
                for future in as_completed(future_map):
                    resource_item = future_map[future]
                    progress.set_description(f"Downloading {Path(resource_item.path).name}")
                    try:
                        downloaded_item = future.result()
                    except Exception as exc:
                        self.logger.error(f"Failed to download {resource_item.path}: {exc}")
                        failed.append(resource_item)
                        continue

                    progress.advance()
                    if context.extract_while_download:
                        self._extract_resource(downloaded_item, context)
        return failed

    def _verify_resource(
        self,
        resource: ResourceItem,
        context: RuntimeContext,
    ) -> tuple[ResourceItem, bool]:
        asset_path = Path(context.raw_dir) / resource.path
        if not asset_path.exists() or asset_path.stat().st_size != resource.size:
            return resource, False

        if resource.check_type == "crc":
            return resource, calculate_crc(str(asset_path)) == resource.checksum
        if resource.check_type == "md5":
            return resource, calculate_md5(str(asset_path)) == resource.checksum
        return resource, False

    def _download_resource(
        self,
        resource: ResourceItem,
        context: RuntimeContext,
    ) -> ResourceItem:
        asset_path = Path(context.raw_dir) / resource.path
        asset_path.parent.mkdir(parents=True, exist_ok=True)
        self.http_client.download_to_file(resource.url, str(asset_path))
        return resource

    def _extract_resource(self, resource: ResourceItem, context: RuntimeContext) -> None:
        resource_path = str(Path(context.raw_dir) / resource.path)

        if resource.resource_type == ResourceType.bundle:
            with self._bundle_lock:
                BundleExtractor(context, self.logger).extract_bundle(
                    resource_path,
                    BundleExtractor.MAIN_EXTRACT_TYPES,
                )
            return

        if resource.resource_type == ResourceType.media and resource.path.endswith(".zip"):
            MediaExtractor(context).extract_zip(resource_path)
            return

        if resource.resource_type == ResourceType.table:
            TableExtractor.from_context(context, self.logger).extract_table(resource_path)
