import pytest

from ba_downloader.bootstrap.region_profiles import (
    DEFAULT_REGION_SERVICE_PROFILE_REGISTRY,
    RegionServiceProfileRegistry,
)
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.execution import NeverCancelled
from ba_downloader.infrastructure.extraction.table.payload_router import (
    TablePayloadCodec,
)
from ba_downloader.infrastructure.logging.console_logger import NullLogger


class DummyHttpClient:
    pass


def _context(region: str) -> RuntimeContext:
    return RuntimeContext(
        region=region,  # type: ignore[arg-type]
        threads=1,
        version="1.0.0",
        raw_dir="RawData",
        extract_dir="Extracted",
        temp_dir="Temp",
        resource_type=("table",),
        proxy_url="",
        max_retries=1,
        search=(),
        advanced_search=(),
        work_dir=".",
    )


def test_default_region_service_profiles_resolve_all_regions() -> None:
    profiles = [
        DEFAULT_REGION_SERVICE_PROFILE_REGISTRY.resolve("cn"),
        DEFAULT_REGION_SERVICE_PROFILE_REGISTRY.resolve("gl"),
        DEFAULT_REGION_SERVICE_PROFILE_REGISTRY.resolve("jp"),
    ]

    assert {profile.region for profile in profiles} == {"cn", "gl", "jp"}


def test_default_region_service_profiles_build_core_factories() -> None:
    logger = NullLogger()
    http_client = DummyHttpClient()

    for region in ("cn", "gl", "jp"):
        profile = DEFAULT_REGION_SERVICE_PROFILE_REGISTRY.resolve(region)
        provider = profile.provider_factory(http_client, logger)
        preparer = profile.runtime_asset_preparer_factory(
            http_client,
            logger,
            None,
            NeverCancelled(),
        )
        dumper = profile.dumper_backend_factory(
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
    cn = DEFAULT_REGION_SERVICE_PROFILE_REGISTRY.resolve("cn")
    gl = DEFAULT_REGION_SERVICE_PROFILE_REGISTRY.resolve("gl")
    jp = DEFAULT_REGION_SERVICE_PROFILE_REGISTRY.resolve("jp")

    cn_route = cn.table_profile_factory(
        _context("cn")
    ).payload_router.resolve_database_blob(
        "LogicEffectDataDBSchema.db",
        "LogicEffect_PC",
        "Bytes",
    )
    gl_route = gl.table_profile_factory(
        _context("gl")
    ).payload_router.resolve_database_blob(
        "LogicEffectDataDBSchema.db",
        "LogicEffect_PC",
        "Bytes",
    )
    jp_route = jp.table_profile_factory(
        _context("jp")
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
    assert callable(cn.character_index_source_profile_factory(_context("cn")).load)
    assert callable(gl.character_index_source_profile_factory(_context("gl")).load)
    assert callable(jp.character_index_source_profile_factory(_context("jp")).load)
    assert cn.character_index_composition_profile_factory(_context("cn")).enrichers
    assert (
        gl.character_index_composition_profile_factory(_context("gl")).enrichers == ()
    )
    assert (
        jp.character_index_composition_profile_factory(
            _context("jp")
        ).romanize_japanese_names
        is True
    )


def test_registry_raises_for_unknown_region() -> None:
    registry = RegionServiceProfileRegistry()
    with pytest.raises(KeyError):
        registry.resolve("jp")
