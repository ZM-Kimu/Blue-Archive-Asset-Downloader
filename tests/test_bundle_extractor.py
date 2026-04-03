from __future__ import annotations

from pathlib import Path
from queue import Empty

from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.infrastructure.extractors.bundle import BundleExtractor


class FakeQueue:
    def __init__(self, items: list[str]) -> None:
        self._items = list(items)

    def get(self, timeout: float | None = None) -> str:
        _ = timeout
        if not self._items:
            raise Empty
        return self._items.pop(0)


def _build_context(tmp_path: Path) -> RuntimeContext:
    return RuntimeContext(
        region="jp",
        threads=4,
        version="1.0.0",
        raw_dir=str(tmp_path / "Raw"),
        extract_dir=str(tmp_path / "Extracted"),
        temp_dir=str(tmp_path / "Temp"),
        extract_while_download=False,
        resource_type=("bundle",),
        proxy_url="",
        max_retries=1,
        search=(),
        advanced_search=(),
        work_dir=str(tmp_path),
    )


def test_bundle_worker_consumes_queue_without_empty_check(
    monkeypatch,
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path)
    processed: list[str] = []

    def fake_extract_bundle(self, bundle_path: str, extract_types):  # type: ignore[no-untyped-def]
        _ = (self, extract_types)
        processed.append(bundle_path)

    monkeypatch.setattr(BundleExtractor, "extract_bundle", fake_extract_bundle)

    queue = FakeQueue(["one.bundle", "two.bundle"])
    BundleExtractor.multiprocess_extract_worker(queue, context, None)

    assert processed == ["one.bundle", "two.bundle"]
