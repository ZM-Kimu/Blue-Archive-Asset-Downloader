from ba_downloader.lib.console import print
from ba_downloader.lib.structure import Resource, ResourceItem


class ResourceUtils:
    @staticmethod
    def filter_type(resource: Resource, resource_type: list[str] | tuple[str, ...]) -> Resource:
        if len(resource_type) == 3:
            return resource

        filtered_res = Resource()
        for item in resource:
            if item.resource_type.name in resource_type:
                filtered_res.add_item(item)

        return filtered_res

    @staticmethod
    def search_name(resource: Resource, keywords: list[str] | tuple[str, ...]) -> Resource:
        results = Resource()
        searched_list: list[ResourceItem] = []

        for keyword in keywords:
            searched_list += resource.search_resource("path", keyword)

        unique_res = {item.path: item for item in searched_list}
        for searched in unique_res.values():
            results.add_item(searched)

        return results


def full_text_filter(keywords: str, character_map: dict, content_list: list) -> list:
    print(f"Searching for mapping data with version {character_map['version']}...")

    new_contents = []
    keyword_list = keywords.split(",").copy()
    key_mapping = character_map["keyword_mapping"]
    file_mapping = character_map["source_file_mapping"]

    for keyword in keyword_list.copy():
        for key in key_mapping:
            if keyword.lower() in key_mapping[key].lower():
                keyword_list.append(key.lower())

    for keyword in keyword_list.copy():
        for file in file_mapping:
            if keyword.lower() in file_mapping[file].lower():
                keyword_list.append(file.lower())

    for content in content_list:
        for keyword in keyword_list:
            if keyword.lower() in content["path"].lower():
                new_contents.append(content)

    return new_contents
