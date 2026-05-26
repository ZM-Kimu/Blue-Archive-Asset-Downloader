import pytest

from ba_downloader.bootstrap.registries import (
    DEFAULT_REGION_REGISTRY,
    RegionRegistry,
)
from ba_downloader.infrastructure.logging.console_logger import NullLogger


def test_default_registry_contains_all_regions() -> None:
    assert DEFAULT_REGION_REGISTRY.resolve("cn").__name__ == "CNRegionProvider"
    assert DEFAULT_REGION_REGISTRY.resolve("gl").__name__ == "GLRegionProvider"
    jp_provider = DEFAULT_REGION_REGISTRY.resolve("jp")(
        http_client=object(),
        logger=NullLogger(),
    )

    assert jp_provider.__class__.__name__ == "JPRegionProvider"


def test_registry_raises_for_unknown_region() -> None:
    registry = RegionRegistry()
    with pytest.raises(KeyError):
        registry.resolve("jp")
