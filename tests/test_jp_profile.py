from __future__ import annotations

import pytest

from ba_downloader.infrastructure.regions.jp.platform import build_jp_platform_profile
from support import build_runtime_context


@pytest.mark.parametrize(
    ("platform", "patch_dir"),
    [
        ("windows", "Windows_PatchPack"),
        ("android", "Android_PatchPack"),
        ("ios", "iOS_PatchPack"),
    ],
)
def test_jp_platform_profile_resolves_bundle_patch_dir(
    tmp_path,
    platform: str,
    patch_dir: str,
) -> None:
    profile = build_jp_platform_profile(
        build_runtime_context(
            tmp_path,
            region="jp",
            platform=platform,  # type: ignore[arg-type]
        )
    )

    assert profile.bundle_patch_dir == patch_dir
