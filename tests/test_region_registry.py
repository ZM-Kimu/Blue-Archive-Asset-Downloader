from pathlib import Path

import pytest

from ba_downloader.bootstrap.region_gateways import (
    DEFAULT_REGION_GATEWAY_REGISTRY,
    RegionGatewayRegistry,
)
from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.domain.ports.execution import NeverCancelled
from ba_downloader.infrastructure.extraction.table.payload_router import (
    TablePayloadCodec,
)
from ba_downloader.infrastructure.logging.console_logger import NullLogger
from support.fixtures import build_execution_context


class DummyHttpClient:
    pass


def _context(region: str) -> ExecutionContext:
    return build_execution_context(
        Path.cwd(),
        region=region,  # type: ignore[arg-type]
        version="1.0.0",
        max_retries=1,
    )


def test_default_region_gateway_registry_resolves_all_regions() -> None:
    profiles = [
        DEFAULT_REGION_GATEWAY_REGISTRY.resolve("cn"),
        DEFAULT_REGION_GATEWAY_REGISTRY.resolve("gl"),
        DEFAULT_REGION_GATEWAY_REGISTRY.resolve("jp"),
    ]

    assert {profile.descriptor.region for profile in profiles} == {"cn", "gl", "jp"}


def test_default_region_gateway_definitions_build_core_factories() -> None:
    logger = NullLogger()
    http_client = DummyHttpClient()

    for region in ("cn", "gl", "jp"):
        profile = DEFAULT_REGION_GATEWAY_REGISTRY.resolve(region)
        provider = profile.catalog.provider(http_client, logger)
        preparer = profile.runtime.asset_preparer(
            http_client,
            logger,
            None,
            NeverCancelled(),
        )
        dumper = profile.runtime.dump_backend(
            http_client,
            logger,
            NeverCancelled(),
        )

        assert callable(provider.get_capabilities)
        assert callable(provider.load_catalog)
        assert callable(preparer.prepare)
        assert callable(dumper.dump)


def test_default_region_service_profiles_expose_table_and_index_policy_behavior() -> (
    None
):
    cn = DEFAULT_REGION_GATEWAY_REGISTRY.resolve("cn")
    gl = DEFAULT_REGION_GATEWAY_REGISTRY.resolve("gl")
    jp = DEFAULT_REGION_GATEWAY_REGISTRY.resolve("jp")

    cn_route = cn.tables.extraction_profile(
        _context("cn"), None
    ).payload_router.resolve_database_blob(
        "LogicEffectDataDBSchema.db",
        "LogicEffect_PC",
        "Bytes",
    )
    gl_route = gl.tables.extraction_profile(
        _context("gl"), None
    ).payload_router.resolve_database_blob(
        "LogicEffectDataDBSchema.db",
        "LogicEffect_PC",
        "Bytes",
    )
    jp_route = jp.tables.extraction_profile(
        _context("jp"), None
    ).payload_router.resolve_database_blob(
        "LogicEffectDataDBSchema.db",
        "LogicEffect_PC",
        "Bytes",
    )

    assert cn_route.codec is TablePayloadCodec.MEMORYPACK
    assert cn_route.allow_partial_memorypack is True
    assert gl_route.codec is TablePayloadCodec.MEMORYPACK
    assert gl_route.allow_partial_memorypack is False
    assert jp_route.codec is TablePayloadCodec.MEMORYPACK
    assert jp_route.allow_partial_memorypack is False
    assert callable(cn.character_index.source_profile(_context("cn")).load)
    assert callable(gl.character_index.source_profile(_context("gl")).load)
    assert callable(jp.character_index.source_profile(_context("jp")).load)
    assert cn.character_index.composition_profile(_context("cn")).enrichers
    assert gl.character_index.composition_profile(_context("gl")).enrichers == ()
    assert (
        jp.character_index.composition_profile(_context("jp")).romanize_japanese_names
        is True
    )


def test_registry_raises_for_unknown_region() -> None:
    registry = RegionGatewayRegistry()
    with pytest.raises(KeyError):
        registry.resolve("jp")
