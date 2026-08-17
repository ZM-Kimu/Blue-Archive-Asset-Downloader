from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from ba_downloader.api.state import ContextCapacityError, ContextRegistry
from ba_downloader.domain.models.asset import AssetCollection
from ba_downloader.domain.models.asset_filter import AssetFilter
from ba_downloader.domain.models.runtime import RuntimeContext


def _context(tmp_path: Path, *, proxy: str = "") -> RuntimeContext:
    return RuntimeContext(
        "cn",
        30,
        "",
        str(tmp_path / "raw"),
        str(tmp_path / "extracted"),
        str(tmp_path / ".state/temp"),
        ("table",),
        proxy,
        5,
        (),
        (),
        str(tmp_path),
    )


def test_registry_enforces_capacity_and_deduplicates(tmp_path: Path) -> None:
    registry = ContextRegistry(capacity=1, fingerprint_key=b"x" * 32)
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
        fingerprint_key=b"x" * 32,
    )
    first, _ = registry.create(_context(tmp_path))
    now += timedelta(hours=2)
    replacement, _ = registry.create(_context(tmp_path, proxy="http://new"))
    assert replacement.id != first.id


def test_freeze_keeps_command_fields_out_of_immutable_context(tmp_path: Path) -> None:
    registry = ContextRegistry(fingerprint_key=b"x" * 32)
    item, _ = registry.create(_context(tmp_path))

    frozen = registry.freeze(
        item.id,
        item.context.with_updates(
            version="2.0.0",
            threads=99,
            asset_filter=AssetFilter.parse(["path~temporary"]),
        ),
        AssetCollection(),
    )

    assert frozen.context.version == "2.0.0"
    assert frozen.context.threads == item.context.threads
    assert not frozen.context.asset_filter.predicates
