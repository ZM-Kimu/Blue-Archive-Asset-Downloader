from __future__ import annotations

from dataclasses import dataclass

from ba_downloader.domain.models.region import Platform
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.infrastructure.regions.jp.models import resolve_jp_patch_pack_dir


@dataclass(frozen=True, slots=True)
class JpPlatformProfile:
    platform: Platform
    bundle_patch_dir: str


def build_jp_platform_profile(context: RuntimeContext) -> JpPlatformProfile:
    return JpPlatformProfile(
        platform=context.platform,
        bundle_patch_dir=resolve_jp_patch_pack_dir(context.platform),
    )
