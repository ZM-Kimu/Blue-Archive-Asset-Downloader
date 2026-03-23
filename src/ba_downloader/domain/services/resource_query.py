from __future__ import annotations

from ba_downloader.domain.models.resource import Resource


class ResourceQueryService:
    @staticmethod
    def filter_type(resource: Resource, resource_type: list[str] | tuple[str, ...]) -> Resource:
        if len(resource_type) == 3:
            return resource

        filtered = Resource()
        for item in resource:
            if item.resource_type.name in resource_type:
                filtered.add_item(item)

        return filtered

    @staticmethod
    def search_name(resource: Resource, keywords: list[str] | tuple[str, ...]) -> Resource:
        results = Resource()
        matches = []

        for keyword in keywords:
            matches.extend(resource.search_resource("path", keyword))

        for item in {item.path: item for item in matches}.values():
            results.add_item(item)

        return results


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
