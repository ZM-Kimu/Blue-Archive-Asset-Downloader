from __future__ import annotations

import pytest

from ba_downloader.domain.exceptions import ConfigError
from ba_downloader.domain.models.asset import AssetCollection, AssetType
from ba_downloader.domain.models.asset_filter import AssetFilter
from ba_downloader.domain.models.character import CharacterIndexEntry
from ba_downloader.domain.services.asset_filter import AssetFilterService


def _assets() -> AssetCollection:
    assets = AssetCollection()
    assets.add("url", "Bundle/CH0198_Ibuki.bundle", 1, "x", "md5", AssetType.bundle)
    assets.add("url", "Media/BGM.zip", 1, "x", "md5", AssetType.media)
    return assets


def test_asset_filter_matches_resource_predicates_with_and_or_semantics() -> None:
    result = AssetFilterService.apply(
        _assets(),
        AssetFilter.parse(["type=bundle,table", "path~ibuki"]),
    )

    assert [asset.path for asset in result] == ["Bundle/CH0198_Ibuki.bundle"]


def test_character_predicates_must_match_the_same_index_entry() -> None:
    entries = [
        CharacterIndexEntry(
            198,
            dev_name="Ibuki",
            names=["伊吹"],
            file_aliases={"CH0198"},
            school_en="Gehenna",
        ),
        CharacterIndexEntry(
            200,
            dev_name="Other",
            names=["Other"],
            file_aliases={"CH0200"},
            school_en="Abydos",
        ),
    ]

    matched = AssetFilterService.apply(
        _assets(),
        AssetFilter.parse(["name~伊吹,Ibuki", "school=Gehenna"]),
        character_entries=entries,
    )
    unmatched = AssetFilterService.apply(
        _assets(),
        AssetFilter.parse(["name~伊吹", "school=Abydos"]),
        character_entries=entries,
    )

    assert [asset.path for asset in matched] == ["Bundle/CH0198_Ibuki.bundle"]
    assert not unmatched


def test_character_filter_requires_index_entries() -> None:
    with pytest.raises(ConfigError):
        AssetFilterService.apply(_assets(), AssetFilter.parse(["cv~Ogura"]))
