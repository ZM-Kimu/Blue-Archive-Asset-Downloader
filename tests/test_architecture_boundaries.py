import importlib
from pathlib import Path

import pytest

FORBIDDEN_IMPORTS = (
    "ba_downloader.legacy",
    "ba_downloader.utils.",
    "ba_downloader.utils.config",
    "get_runtime_context(",
    "apply_settings(",
    "update_runtime_context(",
    "ba_downloader.lib.",
    "ba_downloader.extractors",
    "ba_downloader.regions",
    "ba_downloader.application.services",
    "ba_downloader.application.catalog_pipeline",
    "ba_downloader.domain.models.settings",
    "ba_downloader.infrastructure.apk",
    "ba_downloader.infrastructure.extract.",
    "ba_downloader.infrastructure.extractors",
    "ba_downloader.infrastructure.jp",
    "ba_downloader.infrastructure.regions.providers",
    "ba_downloader.infrastructure.regions.registry",
    "ba_downloader.infrastructure.runtime.registry",
    "ba_downloader.infrastructure.schema.common.support",
    "ba_downloader.infrastructure.services",
    "ba_downloader.shared.crypto",
    "ba_downloader.shared.misc.template_utils",
    "ba_downloader.domain.models.resource",
    "LegacyRegionPipelineAdapter",
)


def test_runtime_code_avoids_deprecated_import_paths() -> None:
    source_root = Path("src/ba_downloader")
    violations: list[str] = []

    for file_path in source_root.rglob("*.py"):
        content = file_path.read_text(encoding="utf-8")
        for pattern in FORBIDDEN_IMPORTS:
            if pattern in content:
                violations.append(f"{file_path}: {pattern}")

    assert not violations, "\n".join(violations)


def test_removed_internal_packages_do_not_provide_shims() -> None:
    removed_modules = (
        "ba_downloader.application.services",
        "ba_downloader.application.catalog_pipeline",
        "ba_downloader.domain.models.settings",
        "ba_downloader.infrastructure.apk",
        "ba_downloader.infrastructure.extract",
        "ba_downloader.infrastructure.extractors",
        "ba_downloader.infrastructure.jp",
        "ba_downloader.infrastructure.regions.providers",
        "ba_downloader.infrastructure.regions.registry",
        "ba_downloader.infrastructure.regions.jp.catalog_decoder",
        "ba_downloader.infrastructure.runtime.registry",
        "ba_downloader.infrastructure.schema.common.support",
        "ba_downloader.shared.crypto.encryption",
    )

    for module_name in removed_modules:
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(module_name)
