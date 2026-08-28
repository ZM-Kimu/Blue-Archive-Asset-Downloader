from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace

from ba_downloader.domain.exceptions import ConfigError
from ba_downloader.domain.models.asset import AssetCollection, AssetRecord
from ba_downloader.domain.models.asset_filter import (
    AssetFilter,
    FilterField,
    FilterOperator,
    FilterPredicate,
)
from ba_downloader.domain.models.character import CharacterIndexEntry

RESOURCE_FIELDS = {FilterField.path, FilterField.resource_type}


class AssetFilterService:
    @classmethod
    def apply(
        cls,
        resources: AssetCollection,
        asset_filter: AssetFilter,
        *,
        character_entries: Iterable[CharacterIndexEntry] | None = None,
    ) -> AssetCollection:
        if not asset_filter.predicates:
            return resources
        resource_predicates = tuple(
            predicate
            for predicate in asset_filter.predicates
            if predicate.field in RESOURCE_FIELDS
        )
        character_predicates = tuple(
            predicate
            for predicate in asset_filter.predicates
            if predicate.field not in RESOURCE_FIELDS
        )
        aliases: tuple[str, ...] = ()
        if character_predicates:
            if character_entries is None:
                raise ConfigError(
                    "Character index entries are required for character filters."
                )
            aliases = cls._matching_aliases(character_entries, character_predicates)
            if not aliases:
                return AssetCollection()

        result = AssetCollection()
        for resource in resources:
            if not all(
                cls._match_resource(resource, item) for item in resource_predicates
            ):
                continue
            if not aliases:
                result.add_item(resource)
                continue
            if cls._matches_aliases(resource.path, aliases):
                result.add_item(replace(resource, selected_member_paths=None))
                continue
            selected_members = tuple(
                member
                for member in resource.member_paths
                if cls._matches_aliases(member, aliases)
            )
            if selected_members:
                result.add_item(
                    replace(resource, selected_member_paths=selected_members)
                )
        return result

    @staticmethod
    def _matches_aliases(path: str, aliases: tuple[str, ...]) -> bool:
        normalized = path.casefold()
        return any(alias.casefold() in normalized for alias in aliases)

    @classmethod
    def _matching_aliases(
        cls,
        entries: Iterable[CharacterIndexEntry],
        predicates: tuple[FilterPredicate, ...],
    ) -> tuple[str, ...]:
        aliases: set[str] = set()
        for entry in entries:
            if not all(cls._match_character(entry, item) for item in predicates):
                continue
            aliases.update(entry.file_aliases or set())
            if entry.dev_name:
                aliases.add(entry.dev_name)
        return tuple(sorted(aliases, key=str.casefold))

    @classmethod
    def _match_resource(
        cls,
        resource: AssetRecord,
        predicate: FilterPredicate,
    ) -> bool:
        if predicate.field is FilterField.path:
            values = (resource.path,)
        elif predicate.field is FilterField.resource_type:
            values = (resource.asset_type.value,)
        else:
            return False
        return cls._match_values(values, predicate)

    @classmethod
    def _match_character(
        cls,
        entry: CharacterIndexEntry,
        predicate: FilterPredicate,
    ) -> bool:
        values: tuple[str, ...]
        if predicate.field is FilterField.character_id:
            values = (str(entry.character_id),)
        elif predicate.field is FilterField.name:
            values = tuple(entry.names or ())
        elif predicate.field is FilterField.developer_name:
            values = (entry.dev_name,)
        elif predicate.field is FilterField.file_alias:
            values = tuple(entry.file_aliases or ())
        elif predicate.field is FilterField.cv:
            values = (entry.cv,)
        elif predicate.field is FilterField.age:
            values = (str(entry.age),)
        elif predicate.field is FilterField.height:
            values = (str(entry.height),)
        elif predicate.field is FilterField.birthday:
            values = (entry.birthday,)
        elif predicate.field is FilterField.illustrator:
            values = (entry.illustrator,)
        elif predicate.field is FilterField.school:
            values = (entry.school_en,)
        elif predicate.field is FilterField.club:
            values = (entry.club_en,)
        else:
            return False
        return cls._match_values(values, predicate)

    @staticmethod
    def _match_values(values: tuple[str, ...], predicate: FilterPredicate) -> bool:
        normalized_values = tuple(value.casefold() for value in values)
        normalized_candidates = tuple(
            candidate.casefold() for candidate in predicate.candidates
        )
        if predicate.operator is FilterOperator.equals:
            return any(
                candidate == value
                for candidate in normalized_candidates
                for value in normalized_values
            )
        return any(
            candidate in value
            for candidate in normalized_candidates
            for value in normalized_values
        )
