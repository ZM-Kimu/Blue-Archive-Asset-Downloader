import pytest

from ba_downloader.bootstrap.region_gateways import (
    DEFAULT_REGION_GATEWAY_REGISTRY,
    RegionGatewayRegistry,
)
from ba_downloader.domain.ports.execution import NeverCancelled
from ba_downloader.infrastructure.logging.console_logger import NullLogger


class DummyHttpClient:
    pass


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


def test_registry_raises_for_unknown_region() -> None:
    registry = RegionGatewayRegistry()
    with pytest.raises(KeyError):
        registry.resolve("jp")
