import ast
from pathlib import Path

PYTHON_SOURCE_ROOT = Path("src/ba_downloader")

FORBIDDEN_INFRA_EDGES = {
    ("infrastructure.download", "infrastructure.extraction"),
    ("infrastructure.extraction", "infrastructure.regions"),
    ("infrastructure.regions", "infrastructure.schema"),
}

INFRA_EDGE_ALLOWLIST: set[tuple[str, str]] = {
    (
        "ba_downloader.infrastructure.regions.jp.catalog_decoder",
        "ba_downloader.infrastructure.schema.memorypack.cursor",
    ),
    (
        "ba_downloader.infrastructure.regions.jp.catalog_decoder",
        "ba_downloader.infrastructure.schema.memorypack.reader",
    ),
}

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
    "ba_downloader.shared",
    "ba_downloader.shared.crypto",
    "ba_downloader.shared.misc.template_utils",
    "ba_downloader.domain.models.resource",
    "LegacyRegionPipelineAdapter",
)


def test_runtime_code_avoids_deprecated_import_paths() -> None:
    violations: list[str] = []

    for file_path in PYTHON_SOURCE_ROOT.rglob("*.py"):
        content = file_path.read_text(encoding="utf-8")
        for pattern in FORBIDDEN_IMPORTS:
            if pattern in content:
                violations.append(f"{file_path}: {pattern}")

    assert not violations, "\n".join(violations)


def _module_name(path: Path) -> str:
    relative = path.relative_to("src").with_suffix("").as_posix().replace("/", ".")
    if relative.endswith(".__init__"):
        return relative.removesuffix(".__init__")
    return relative


def _infra_layer(module_name: str) -> str:
    parts = module_name.split(".")
    if len(parts) >= 3 and parts[:2] == ["ba_downloader", "infrastructure"]:
        return ".".join(parts[1:3])
    return ""


def _internal_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(
                alias.name
                for alias in node.names
                if alias.name.startswith("ba_downloader.")
            )
        elif (
            isinstance(node, ast.ImportFrom)
            and node.module
            and node.module.startswith("ba_downloader.")
        ):
            imports.add(node.module)
    return imports


def test_new_infrastructure_cross_edges_do_not_bypass_boundaries() -> None:
    violations: list[str] = []
    for file_path in PYTHON_SOURCE_ROOT.rglob("*.py"):
        if "__pycache__" in file_path.parts:
            continue
        source_module = _module_name(file_path)
        source_layer = _infra_layer(source_module)
        if not source_layer:
            continue
        for target_module in _internal_imports(file_path):
            target_layer = _infra_layer(target_module)
            edge = (source_layer, target_layer)
            module_edge = (source_module, target_module)
            if (
                edge in FORBIDDEN_INFRA_EDGES
                and module_edge not in INFRA_EDGE_ALLOWLIST
            ):
                violations.append(f"{source_module} -> {target_module}")

    assert not violations, "\n".join(violations)


def test_package_download_does_not_construct_terminal_progress() -> None:
    path = PYTHON_SOURCE_ROOT / "infrastructure/packages/android_package.py"
    imports = _internal_imports(path)

    assert "ba_downloader.infrastructure.progress.rich_progress" not in imports


def test_api_adapter_does_not_import_infrastructure() -> None:
    api_root = PYTHON_SOURCE_ROOT / "api"
    violations: list[str] = []
    for file_path in api_root.rglob("*.py"):
        for imported in _internal_imports(file_path):
            if imported.startswith("ba_downloader.infrastructure"):
                violations.append(f"{_module_name(file_path)} -> {imported}")

    assert not violations, "\n".join(violations)
