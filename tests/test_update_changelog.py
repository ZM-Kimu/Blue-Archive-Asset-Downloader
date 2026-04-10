from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "update_changelog.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("update_changelog", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_update_unreleased_preserves_existing_release_sections(monkeypatch) -> None:
    module = _load_module()
    existing = """# Changelog

## Unreleased

- Old content

## v2.0.0 - 2026-04-10

### Release
- Published v2.0.0.
"""

    monkeypatch.setattr(
        module,
        "_run_git_log",
        lambda base_ref, head_ref: [
            "feat(cli): add main-only release flow",
            "fix(release): preserve changelog sections",
        ],
    )

    updated = module.update_unreleased_changelog(existing, "v2.0.0", "HEAD")

    assert "## Unreleased" in updated
    assert "- Old content" not in updated
    assert "### Features" in updated
    assert "- add main-only release flow" in updated
    assert "### Fixes" in updated
    assert "- preserve changelog sections" in updated
    assert "## v2.0.0 - 2026-04-10" in updated
    assert "- Published v2.0.0." in updated


def test_finalize_release_promotes_unreleased_and_resets_placeholder() -> None:
    module = _load_module()
    existing = """# Changelog

## Unreleased

### Fixes
- stabilize release workflow

## v2.0.0 - 2026-04-10

### Release
- Published v2.0.0.
"""

    finalized = module.finalize_release_changelog(existing, "2.0.1", "2026-04-11")

    assert "## Unreleased" in finalized
    assert module.NO_UNRELEASED_CHANGES in finalized
    assert "## v2.0.1 - 2026-04-11" in finalized
    assert "- stabilize release workflow" in finalized
    assert "## v2.0.0 - 2026-04-10" in finalized


def test_extract_release_notes_returns_requested_version_section() -> None:
    module = _load_module()
    existing = """# Changelog

## Unreleased

- No unreleased changes recorded.

## v2.0.1 - 2026-04-11

### Features
- add release notes extraction

## v2.0.0 - 2026-04-10

### Release
- Published v2.0.0.
"""

    notes = module.extract_release_notes(existing, "2.0.1")

    assert notes == "### Features\n- add release notes extraction"


def test_parse_args_supports_legacy_update_invocation() -> None:
    module = _load_module()

    args = module.parse_args(
        ["--base", "v2.0.0", "--head", "HEAD", "--output", "CHANGELOG.md"]
    )

    assert args.command == "update"
    assert args.base == "v2.0.0"
    assert args.head == "HEAD"
