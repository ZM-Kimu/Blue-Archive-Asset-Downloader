from __future__ import annotations

from ba_downloader.domain.models.asset import AssetCollection, AssetRecord


class ResourceQueryService:
    @staticmethod
    def filter_type(
        resource: AssetCollection,
        resource_type: list[str] | tuple[str, ...],
    ) -> AssetCollection:
        if len(resource_type) == 3:
            return resource

        filtered = AssetCollection()
        for item in resource:
            if item.asset_type.value in resource_type:
                filtered.add_item(item)

        return filtered

    @staticmethod
    def search_name(
        resource: AssetCollection,
        keywords: list[str] | tuple[str, ...],
    ) -> AssetCollection:
        results = AssetCollection()
        matches = []

        for keyword in keywords:
            matches.extend(resource.search("path", keyword))
            matches.extend(ResourceQueryService._search_bundle_files(resource, keyword))

        for item in {item.path: item for item in matches}.values():
            results.add_item(item)

        return results

    @staticmethod
    def _search_bundle_files(
        resource: AssetCollection,
        keyword: str,
    ) -> list[AssetRecord]:
        keyword_lower = keyword.lower()
        return [
            item
            for item in resource
            if any(
                keyword_lower in str(bundle_name).lower()
                for bundle_name in item.metadata.get("bundle_files", [])
            )
        ]


def full_text_filter(
    keywords: str,
    character_map: dict[str, object],
    content_list: list[dict[str, object]],
) -> list[dict[str, object]]:
    filtered_contents: list[dict[str, object]] = []
    keyword_list = keywords.split(",").copy()
    key_mapping = character_map["keyword_mapping"]
    file_mapping = character_map["source_file_mapping"]

    if not isinstance(key_mapping, dict) or not isinstance(file_mapping, dict):
        return filtered_contents

    for keyword in keyword_list.copy():
        for mapped_key, mapped_value in key_mapping.items():
            if keyword.lower() in str(mapped_value).lower():
                keyword_list.append(str(mapped_key).lower())

    for keyword in keyword_list.copy():
        for mapped_file, mapped_value in file_mapping.items():
            if keyword.lower() in str(mapped_value).lower():
                keyword_list.append(str(mapped_file).lower())

    for content in content_list:
        content_path = str(content.get("path", "")).lower()
        if any(keyword.lower() in content_path for keyword in keyword_list):
            filtered_contents.append(content)

    return filtered_contents
