from __future__ import annotations

import re
from typing import Any

from ba_downloader.domain.models.character import CharacterIndexEntry
from ba_downloader.infrastructure.extraction.character.index_composer import (
    CharacterIndexComposer,
    append_names,
)
from ba_downloader.infrastructure.extraction.character.index_sources import (
    CharacterIndexSources,
)


class CnArchiveCharacterIndexEnricher:
    def enrich(
        self,
        composer: CharacterIndexComposer,
        hash_map: dict[int, CharacterIndexEntry],
        sources: CharacterIndexSources,
    ) -> None:
        composer.apply_costume_data(hash_map, sources.costume_excel)
        apply_cn_recruit_data(
            hash_map,
            sources.shop_recruit,
            sources.localize_gacha,
        )


def apply_cn_recruit_data(
    hash_map: dict[int, CharacterIndexEntry],
    shop_recruit: list[dict[str, Any]],
    localize_gacha: list[dict[str, Any]],
) -> None:
    subtitle_by_shop_id = {
        int(item.get("GachaShopId", 0) or 0): str(item.get("SubTitleKr", ""))
        for item in localize_gacha
        if item.get("SubTitleKr")
    }

    for recruit in shop_recruit:
        shop_id = int(recruit.get("Id", 0) or 0)
        subtitle = subtitle_by_shop_id.get(shop_id, "")
        if not subtitle:
            continue

        info_character_ids = [
            int(value)
            for value in recruit.get("InfoCharacterId", [])
            if int(value or 0) > 0
        ]
        if not info_character_ids:
            continue

        recruit_names = extract_recruit_names(subtitle)
        if not recruit_names:
            continue

        if len(info_character_ids) == 1:
            append_names(hash_map, info_character_ids[0], {recruit_names[0]})
            continue

        for char_id, recruit_name in zip(
            info_character_ids, recruit_names, strict=False
        ):
            append_names(hash_map, char_id, {recruit_name})


def extract_recruit_names(subtitle: str) -> list[str]:
    names: list[str] = []
    for segment in re.split(r"[/\n]+", subtitle):
        normalized = segment.strip()
        if not normalized:
            continue

        normalized = normalized.replace("还可招募", "").strip()
        normalized = re.sub(r"^【[^】]+】", "", normalized).strip()
        normalized = re.sub(r"招募概率提升[\uFF01!]*$", "", normalized).strip()
        normalized = re.sub(r"^[123]★", "", normalized).strip()
        normalized = re.sub(r"\uFF08[123]★\uFF09$", "", normalized).strip()
        normalized = normalized.strip("\uff01! ")

        if normalized:
            names.append(normalized)
    return names
