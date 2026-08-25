from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from ba_downloader.api.state import ContextCapacityError, ContextRegistry
from ba_downloader.domain.models.asset import AssetCollection
from ba_downloader.domain.models.execution import ExecutionContext
from support import build_execution_context


def _context(tmp_path: Path, *, proxy: str = "") -> ExecutionContext:
    return build_execution_context(
        tmp_path,
        region="cn",
        version="",
        proxy_url=proxy,
        max_retries=5,
    )


def test_registry_enforces_capacity_and_deduplicates(tmp_path: Path) -> None:
    registry = ContextRegistry(capacity=1)
    first, created = registry.create(_context(tmp_path))
    duplicate, duplicate_created = registry.create(_context(tmp_path))
    assert created is True
    assert duplicate_created is False
    assert duplicate.id == first.id
    with pytest.raises(ContextCapacityError):
        registry.create(_context(tmp_path, proxy="http://different"))


def test_registry_expires_idle_contexts(tmp_path: Path) -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    registry = ContextRegistry(
        capacity=1,
        idle_ttl=timedelta(hours=1),
        clock=lambda: now,
    )
    first, _ = registry.create(_context(tmp_path))
    now += timedelta(hours=2)
    replacement, _ = registry.create(_context(tmp_path, proxy="http://new"))
    assert replacement.id != first.id


def test_freeze_uses_resolved_context(tmp_path: Path) -> None:
    registry = ContextRegistry()
    item, _ = registry.create(_context(tmp_path))

    frozen = registry.freeze(
        item.id,
        item.context.resolve_resource_version("2.0.0"),
        AssetCollection(),
    )

    assert frozen.context.resource_version == "2.0.0"
