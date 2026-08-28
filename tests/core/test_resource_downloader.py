from __future__ import annotations

import hashlib
from collections import Counter
from pathlib import Path

import pytest

from ba_downloader.domain.models.asset import (
    AssetCollection,
    AssetRecord,
    AssetType,
    ChecksumSpec,
)
from ba_downloader.infrastructure.download import resource_downloader
from ba_downloader.infrastructure.download.resource_downloader import ResourceDownloader


class NoNetworkClient:
    def request(self, *args: object, **kwargs: object) -> object:
        raise AssertionError("Verified local files must not use the network.")

    def download_to_file(self, *args: object, **kwargs: object) -> object:
        raise AssertionError("Verified local files must not be downloaded.")

    def close(self) -> None:
        return None


def test_verification_enumerates_each_existing_parent_once(
    context_factory: object,
    recording_logger: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = context_factory()  # type: ignore[operator]
    first = _record("Bundle/one.bin", b"one")
    second = _record("Bundle/two.bin", b"two")
    for resource, payload in ((first, b"one"), (second, b"two")):
        path = context.workspace.raw_resource_path("bundle", resource.path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    calls: Counter[Path] = Counter()
    real_iterdir = Path.iterdir

    def tracked_iterdir(path: Path):  # type: ignore[no-untyped-def]
        calls[path] += 1
        return real_iterdir(path)

    monkeypatch.setattr(Path, "iterdir", tracked_iterdir)
    downloader = ResourceDownloader(NoNetworkClient(), recording_logger)  # type: ignore[arg-type]

    pending = downloader._verify_resources(
        AssetCollection([first, second]), context, concurrency=2
    )

    parent = context.workspace.raw_bundles
    assert pending == []
    assert calls[parent] == 1


def test_size_mismatch_does_not_hash_file(
    context_factory: object,
    recording_logger: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = context_factory()  # type: ignore[operator]
    resource = _record("Bundle/asset.bin", b"expected")
    path = context.workspace.raw_resource_path("bundle", resource.path)
    path.parent.mkdir(parents=True)
    path.write_bytes(b"short")

    def unexpected_hash(path: str) -> str:
        raise AssertionError(f"Size-mismatched file was hashed: {path}")

    monkeypatch.setattr(resource_downloader, "calculate_md5", unexpected_hash)
    downloader = ResourceDownloader(NoNetworkClient(), recording_logger)  # type: ignore[arg-type]

    assert "size mismatch" in (downloader._get_validation_error(path, resource) or "")


def test_unique_case_only_name_is_canonicalized_before_verification(
    context_factory: object,
    recording_logger: object,
) -> None:
    context = context_factory()  # type: ignore[operator]
    resource = _record("Bundle/Canonical.bin", b"content")
    expected = context.workspace.raw_resource_path("bundle", resource.path)
    expected.parent.mkdir(parents=True)
    existing = expected.with_name("canonical.BIN")
    existing.write_bytes(b"content")
    downloader = ResourceDownloader(NoNetworkClient(), recording_logger)  # type: ignore[arg-type]

    pending = downloader._verify_resources(
        AssetCollection([resource]), context, concurrency=1
    )

    assert pending == []
    assert expected.read_bytes() == b"content"


def _record(path: str, payload: bytes) -> AssetRecord:
    return AssetRecord(
        "https://cdn.example/" + path,
        path,
        len(payload),
        ChecksumSpec("md5", hashlib.md5(payload).hexdigest()),
        AssetType.bundle,
    )
