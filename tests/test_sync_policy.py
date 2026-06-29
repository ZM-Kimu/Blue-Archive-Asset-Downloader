from ba_downloader.application.use_cases.sync_policy import (
    SyncExtractionMode,
    resolve_sync_workflow_policy,
)
from ba_downloader.domain.models.runtime import RuntimeContext


def _context(region: str) -> RuntimeContext:
    return RuntimeContext(
        region=region,  # type: ignore[arg-type]
        threads=1,
        version="1.0.0",
        raw_dir="RawData",
        extract_dir="Extracted",
        temp_dir="Temp",
        extract_while_download=False,
        resource_type=("bundle",),
        proxy_url="",
        max_retries=1,
        search=(),
        advanced_search=(),
        work_dir=".",
    )


def test_sync_policy_uses_direct_extract_for_gl() -> None:
    policy = resolve_sync_workflow_policy(_context("gl"))

    assert policy.prepares_schema is True
    assert policy.requires_schema_preparation is True
    assert policy.extraction_mode is SyncExtractionMode.direct


def test_sync_policy_uses_post_download_extract_for_cn_and_jp() -> None:
    for region in ("cn", "jp"):
        policy = resolve_sync_workflow_policy(_context(region))

        assert policy.prepares_schema is True
        assert policy.requires_schema_preparation is True
        assert policy.extraction_mode is SyncExtractionMode.post_download
