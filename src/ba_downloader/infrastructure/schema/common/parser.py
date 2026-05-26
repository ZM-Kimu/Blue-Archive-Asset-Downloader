from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass

NULL_TOKEN = ""


@dataclass(frozen=True)
class DumpBlock:
    namespace: str
    header_match: re.Match[str]
    body_lines: list[str]


@dataclass(frozen=True)
class EnumMemberRow:
    name: str
    value: int
    token: str


def normalize_namespace(value: str) -> str:
    namespace = value.strip()
    if namespace == "-":
        return ""
    return namespace


def collect_type_body(lines: list[str], start_index: int) -> tuple[list[str], int]:
    body_lines: list[str] = []
    depth = 0
    started = False
    index = start_index
    while index < len(lines):
        line = lines[index]
        body_lines.append(line)
        depth += line.count("{")
        if "{" in line:
            started = True
        depth -= line.count("}")
        index += 1
        if started and depth <= 0:
            break
    return body_lines, index


def iter_dump_blocks(
    data: str,
    *,
    namespace_pattern: re.Pattern[str],
    header_pattern: re.Pattern[str],
    include_header: Callable[[re.Match[str], str], bool] | None = None,
) -> Iterator[DumpBlock]:
    namespace = ""
    lines = data.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        if namespace_match := namespace_pattern.match(line):
            namespace = normalize_namespace(namespace_match.group("namespace"))
            index += 1
            continue

        header_match = header_pattern.match(line)
        if header_match is None or (
            include_header is not None and not include_header(header_match, line)
        ):
            index += 1
            continue

        body_lines, next_index = collect_type_body(lines, index)
        yield DumpBlock(namespace, header_match, body_lines)
        index = next_index


def parse_enum_member_rows(
    body_lines: list[str],
    *,
    enum_value_pattern: re.Pattern[str],
    enum_member_pattern: re.Pattern[str],
    normalize_underlying_type: Callable[[str], str] = str.strip,
) -> tuple[str, list[EnumMemberRow]]:
    underlying_type = "System.Int32"
    members: list[EnumMemberRow] = []
    next_value = 0
    for line in body_lines:
        if value_match := enum_value_pattern.match(line):
            underlying_type = normalize_underlying_type(value_match.group("type"))
            continue

        member_match = enum_member_pattern.match(line)
        if member_match is None:
            continue

        value_text = member_match.group("value")
        value = int(value_text) if value_text is not None else next_value
        members.append(
            EnumMemberRow(
                name=member_match.group("name"),
                value=value,
                token=member_match.group("token") or NULL_TOKEN,
            )
        )
        next_value = value + 1

    return underlying_type, members
