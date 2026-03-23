import pytest

from ba_downloader.infrastructure.regions.registry import DEFAULT_REGION_REGISTRY, RegionRegistry


def test_default_registry_contains_all_regions() -> None:
    assert DEFAULT_REGION_REGISTRY.resolve("cn").__class__.__name__ == "CNServer"
    assert DEFAULT_REGION_REGISTRY.resolve("gl").__class__.__name__ == "GLServer"
    assert DEFAULT_REGION_REGISTRY.resolve("jp").__class__.__name__ == "JPServer"


def test_registry_raises_for_unknown_region() -> None:
    registry = RegionRegistry()
    with pytest.raises(KeyError):
        registry.resolve("jp")
