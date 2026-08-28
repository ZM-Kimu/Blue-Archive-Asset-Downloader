from __future__ import annotations

import pytest

from ba_downloader.domain.models.asset import (
    AssetCollection,
    AssetRecord,
    AssetType,
    BootstrapSession,
    ChecksumSpec,
    ResolvedRelease,
)
from ba_downloader.domain.models.asset_filter import AssetFilter
from ba_downloader.domain.models.character import CharacterIndexEntry
from ba_downloader.domain.models.region_catalog import DecodedJPCatalog
from ba_downloader.domain.services.asset_filter import AssetFilterService
from ba_downloader.infrastructure.regions.jp.asset_normalizer import JPAssetNormalizer


def test_jp_bundle_members_are_normalized_once_and_preserve_order() -> None:
    payload = DecodedJPCatalog(
        tables=[],
        media=[],
        bundles=[
            {
                "name": "FullPatch_044.zip",
                "size": 123,
                "crc": "42",
                "bundle_files": [
                    r"characters\ibuki.bundle",
                    {"Name": "/characters//ibuki.bundle"},
                    {"name": "characters/CH0335.bundle"},
                    "",
                    {"unknown": "ignored"},
                    10,
                ],
            }
        ],
    )
    session = BootstrapSession(
        ResolvedRelease("jp", "test"),
        "https://server.example/",
        "https://cdn.example/root/",
    )

    resource = JPAssetNormalizer.normalize(payload, session)[0]

    assert resource.member_paths == (
        "characters/ibuki.bundle",
        "characters/CH0335.bundle",
    )
    assert resource.metadata["bundle_files"] == list(resource.member_paths)


def test_character_filter_selects_only_matching_bundle_members() -> None:
    resources = AssetCollection(
        [
            _asset(
                "Bundle/FullPatch_044.zip",
                AssetType.bundle,
                (
                    "characters/ibuki_original.bundle",
                    "characters/hoshino.bundle",
                    "ui/CH0335_portrait.bundle",
                ),
            ),
            _asset("Media/ibuki_voice.zip", AssetType.media),
        ]
    )
    entries = [
        CharacterIndexEntry(
            335,
            dev_name="Ibuki",
            names=["Ibuki"],
            file_aliases={"CH0335"},
        )
    ]

    selected = AssetFilterService.apply(
        resources,
        AssetFilter.parse(["name=ibuki"]),
        character_entries=entries,
    )

    assert [item.path for item in selected] == [
        "Bundle/FullPatch_044.zip",
        "Media/ibuki_voice.zip",
    ]
    assert selected[0].selected_member_paths == (
        "characters/ibuki_original.bundle",
        "ui/CH0335_portrait.bundle",
    )
    assert selected[1].selected_member_paths is None


def test_path_filter_never_searches_bundle_members() -> None:
    resources = AssetCollection(
        [
            _asset(
                "Bundle/FullPatch_044.zip",
                AssetType.bundle,
                ("characters/ibuki.bundle",),
            )
        ]
    )

    assert not AssetFilterService.apply(
        resources,
        AssetFilter.parse(["path~ibuki"]),
    )
    selected = AssetFilterService.apply(
        resources,
        AssetFilter.parse(["path~fullpatch", "name=ibuki"]),
        character_entries=[CharacterIndexEntry(1, dev_name="IBUKI", names=["Ibuki"])],
    )
    assert selected[0].selected_member_paths == ("characters/ibuki.bundle",)


def test_character_predicates_are_combined_and_empty_match_is_empty() -> None:
    entries = [
        CharacterIndexEntry(
            1,
            dev_name="Ibuki",
            names=["Ibuki"],
            file_aliases={"CH0335"},
            school_en="Hyakkiyako",
        )
    ]
    resources = AssetCollection(
        [_asset("Bundle/FullPatch.zip", AssetType.bundle, ("CH0335.bundle",))]
    )

    selected = AssetFilterService.apply(
        resources,
        AssetFilter.parse(["name=IBUKI", "school~hyakki"]),
        character_entries=entries,
    )
    rejected = AssetFilterService.apply(
        resources,
        AssetFilter.parse(["name=Ibuki", "school=Trinity"]),
        character_entries=entries,
    )

    assert len(selected) == 1
    assert not rejected


def test_empty_selected_member_tuple_is_rejected() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        _asset("Bundle/a.zip", AssetType.bundle, selected=())


def _asset(
    path: str,
    asset_type: AssetType,
    members: tuple[str, ...] = (),
    *,
    selected: tuple[str, ...] | None = None,
) -> AssetRecord:
    return AssetRecord(
        url="https://cdn.example/" + path,
        path=path,
        size=100,
        checksum=ChecksumSpec("crc", "0"),
        asset_type=asset_type,
        member_paths=members,
        selected_member_paths=selected,
    )
