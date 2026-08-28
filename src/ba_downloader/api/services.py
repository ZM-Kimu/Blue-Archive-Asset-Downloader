from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from threading import Event

from ba_downloader.api.files import FileRegistry
from ba_downloader.api.jobs import JobManager, JobRecord
from ba_downloader.api.models import (
    ContextCreateRequest,
    context_view,
    effective_context_view,
)
from ba_downloader.api.state import ApiContext, ContextRegistry
from ba_downloader.bootstrap.region_gateways import DEFAULT_REGION_GATEWAY_REGISTRY
from ba_downloader.domain.models.asset import AssetCollection
from ba_downloader.domain.models.character import CharacterIndex
from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.domain.models.workspace import WorkspaceLayout


@dataclass(slots=True)
class ApiServices:
    contexts: ContextRegistry
    jobs: JobManager
    files: FileRegistry
    instance_id: str
    port: int
    shutdown_callback: Callable[[], None] | None = None
    catalog_loader: (
        Callable[[ExecutionContext], tuple[ExecutionContext, AssetCollection]] | None
    ) = None
    character_index_loader: Callable[[ExecutionContext], CharacterIndex] | None = None
    character_index_searcher: (
        Callable[[CharacterIndex, list[str]], list[str]] | None
    ) = None
    shutdown_event: Event = field(default_factory=Event)

    def context_from_request(self, request: ContextCreateRequest) -> ExecutionContext:
        definition = DEFAULT_REGION_GATEWAY_REGISTRY.resolve(request.region)
        workspace = WorkspaceLayout.create(
            request.workspace, request.region, request.platform
        )
        key = request.sqlcipher_key.get_secret_value().strip()
        if not definition.descriptor.settings_policy.retain_sqlcipher_key_hex:
            key = ""
        return ExecutionContext(
            region=request.region,
            platform=request.platform,
            workspace=workspace,
            proxy_url=request.proxy.get_secret_value(),
            max_retries=request.retries,
            sqlcipher_key=key,
        )

    def job_view(self, job: JobRecord) -> dict[str, object]:
        result = job.view()
        result["effective_context"] = (
            effective_context_view(job.effective_context, job.context_id)
            if job.effective_context is not None
            else None
        )
        return result

    def require_catalog(self, context_id: str) -> tuple[ApiContext, AssetCollection]:
        item = self.contexts.get(context_id)
        catalog = (
            item.catalog if item.catalog is not None else self.jobs.catalog(context_id)
        )
        if catalog is not None:
            return item, catalog
        if self.catalog_loader is None:
            raise RuntimeError("Catalog loading is unavailable.")
        context, catalog = self.catalog_loader(item.context)
        return self.contexts.freeze(context_id, context, catalog), catalog

    def load_character_index(self, context_id: str) -> CharacterIndex:
        if self.character_index_loader is None:
            raise RuntimeError("Character index loading is unavailable.")
        return self.character_index_loader(self.contexts.get(context_id).context)

    def search_character_index(
        self, index: CharacterIndex, terms: list[str]
    ) -> list[str]:
        if self.character_index_searcher is None:
            raise RuntimeError("Character index search is unavailable.")
        return self.character_index_searcher(index, terms)

    @staticmethod
    def context_view(item: ApiContext) -> dict[str, object]:
        return context_view(item)
