from pathlib import Path


FORBIDDEN_IMPORTS = (
    "ba_downloader.utils.",
    "ba_downloader.utils.config",
    "get_runtime_context(",
    "apply_settings(",
    "update_runtime_context(",
    "ba_downloader.lib.",
    "ba_downloader.extractors",
    "ba_downloader.regions",
    "ba_downloader.infrastructure.services",
    "ba_downloader.shared.misc.template_utils",
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
