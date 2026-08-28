from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from ba_downloader.domain.exceptions import ConfigError


class FilterField(StrEnum):
    path = "path"
    resource_type = "type"
    character_id = "character-id"
    name = "name"
    developer_name = "dev-name"
    file_alias = "alias"
    cv = "cv"
    age = "age"
    height = "height"
    birthday = "birthday"
    illustrator = "illustrator"
    school = "school"
    club = "club"


class FilterOperator(StrEnum):
    contains = "~"
    equals = "="


NUMERIC_FILTER_FIELDS = {
    FilterField.character_id,
    FilterField.age,
    FilterField.height,
}


@dataclass(frozen=True, slots=True)
class FilterPredicate:
    field: FilterField
    operator: FilterOperator
    candidates: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AssetFilter:
    predicates: tuple[FilterPredicate, ...] = ()

    @classmethod
    def parse(cls, expressions: Iterable[str]) -> AssetFilter:
        return cls(
            tuple(cls._parse_predicate(expression) for expression in expressions)
        )

    @staticmethod
    def _parse_predicate(expression: str) -> FilterPredicate:
        operator_index, operator = _find_operator(expression)
        field_name = expression[:operator_index].strip()
        try:
            field = FilterField(field_name)
        except ValueError as exc:
            raise ConfigError(f"Unknown filter field '{field_name}'.") from exc

        candidates = tuple(
            candidate.strip()
            for candidate in expression[operator_index + 1 :].split(",")
        )
        if not candidates or any(not candidate for candidate in candidates):
            raise ConfigError("Filter expression must contain a non-empty candidate.")

        if field in NUMERIC_FILTER_FIELDS:
            if operator is not FilterOperator.equals:
                raise ConfigError(
                    f"Filter field '{field}' only supports the '=' operator."
                )
            if any(not candidate.isdecimal() for candidate in candidates):
                raise ConfigError(
                    f"Filter field '{field}' requires a non-negative integer."
                )

        return FilterPredicate(field, operator, candidates)


def _find_operator(expression: str) -> tuple[int, FilterOperator]:
    matches = [
        (index, operator)
        for operator in FilterOperator
        if (index := expression.find(operator.value)) >= 0
    ]
    if not matches:
        raise ConfigError("Filter expression must contain a '~' or '=' operator.")
    return min(matches, key=lambda match: match[0])
