from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from ba_downloader.bootstrap.region_gateways import (
    DEFAULT_REGION_GATEWAY_REGISTRY,
    RegionGatewayRegistry,
)
from ba_downloader.domain.models.region import Region


def test_default_region_gateway_registry_resolves_immutable_descriptors() -> None:
    definitions = tuple(
        DEFAULT_REGION_GATEWAY_REGISTRY.resolve(region) for region in ("cn", "gl", "jp")
    )

    assert {definition.descriptor.region for definition in definitions} == {
        "cn",
        "gl",
        "jp",
    }
    assert all(
        definition.descriptor.capabilities.supports_sync for definition in definitions
    )
    with pytest.raises(FrozenInstanceError):
        definitions[0].descriptor.region = "jp"  # type: ignore[misc]


def test_region_gateway_definition_groups_factories_by_responsibility() -> None:
    definition = DEFAULT_REGION_GATEWAY_REGISTRY.resolve("jp")

    assert callable(definition.catalog.provider)
    assert callable(definition.runtime.asset_preparer)
    assert callable(definition.runtime.dump_backend)
    assert callable(definition.tables.extraction_profile)
    assert callable(definition.tables.extraction_prerequisite)
    assert callable(definition.character_index.source_profile)
    assert callable(definition.character_index.composition_profile)
    assert callable(definition.catalog_metadata.policy)


def test_region_gateway_registry_lazily_caches_definitions() -> None:
    registry = RegionGatewayRegistry()
    calls = 0

    def build_definition():
        nonlocal calls
        calls += 1
        return DEFAULT_REGION_GATEWAY_REGISTRY.resolve("cn")

    registry.register_factory("cn", build_definition)

    assert registry.resolve("cn") is registry.resolve("cn")
    assert calls == 1


def test_region_gateway_registry_rejects_mismatched_factory_region() -> None:
    registry = RegionGatewayRegistry()
    registry.register_factory(
        "cn", lambda: DEFAULT_REGION_GATEWAY_REGISTRY.resolve("jp")
    )

    with pytest.raises(ValueError, match=r"registered for 'cn'.*returned 'jp'"):
        registry.resolve("cn")


def test_region_gateway_registry_rejects_unknown_region() -> None:
    registry = RegionGatewayRegistry()

    with pytest.raises(KeyError, match="Region 'gl' is not registered"):
        registry.resolve("gl")


def test_region_type_covers_all_registered_regions() -> None:
    registered: tuple[Region, ...] = ("cn", "gl", "jp")

    assert all(DEFAULT_REGION_GATEWAY_REGISTRY.resolve(region) for region in registered)
