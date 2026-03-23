from ba_downloader.domain.models.resource import Resource, ResourceType
from ba_downloader.domain.services.resource_query import ResourceQueryService


def _build_resource() -> Resource:
    resource = Resource()
    resource.add(
        "https://example.invalid/a",
        "Media/Announce/title.png",
        10,
        "a",
        "md5",
        ResourceType.media,
    )
    resource.add(
        "https://example.invalid/b",
        "Bundle/character.bundle",
        20,
        "b",
        "md5",
        ResourceType.bundle,
    )
    resource.add(
        "https://example.invalid/c",
        "Table/CharacterExcel.bytes",
        30,
        "c",
        "md5",
        ResourceType.table,
    )
    return resource


def test_filter_type_returns_matching_resource_types() -> None:
    filtered = ResourceQueryService.filter_type(_build_resource(), ["media", "table"])

    assert len(filtered) == 2
    assert [item.resource_type for item in filtered] == [
        ResourceType.media,
        ResourceType.table,
    ]


def test_search_name_deduplicates_results() -> None:
    results = ResourceQueryService.search_name(_build_resource(), ["character", "excel"])

    assert len(results) == 2
    assert results[0].path == "Bundle/character.bundle"
    assert results[1].path == "Table/CharacterExcel.bytes"
