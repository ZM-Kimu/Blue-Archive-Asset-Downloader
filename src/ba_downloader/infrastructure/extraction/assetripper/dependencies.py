from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal

from ba_downloader.domain.models.asset import ChecksumSpec

DependencyKind = Literal["serialized_file", "streamed_resource"]

_ENGINE_RESOURCES = {
    "unity default resources",
    "unity_default_resources",
    "unity editor resources",
    "unity builtin extra",
    "unity_builtin_extra",
}


@dataclass(frozen=True, slots=True)
class BundleArchiveInput:
    path: Path
    archive_id: str
    size: int
    mtime_ns: int
    checksum: ChecksumSpec | None = None

    @classmethod
    def from_path(
        cls,
        path: Path,
        *,
        archive_id: str | None = None,
        checksum: ChecksumSpec | None = None,
    ) -> BundleArchiveInput:
        resolved = path.resolve(strict=True)
        stat = resolved.stat()
        return cls(
            path=resolved,
            archive_id=archive_id or resolved.name,
            size=stat.st_size,
            mtime_ns=stat.st_mtime_ns,
            checksum=checksum,
        )


@dataclass(frozen=True, slots=True)
class SerializedFileScan:
    logical_name: str
    dependencies: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class StreamedResourceScan:
    source_serialized_file: str
    resource_path: str
    asset_type: str


@dataclass(frozen=True, slots=True)
class BundleEntryScan:
    entry_path: str
    sha256: str
    size: int
    serialized_files: tuple[SerializedFileScan, ...] = ()
    resource_files: tuple[str, ...] = ()
    streamed_resources: tuple[StreamedResourceScan, ...] = ()
    error: str | None = None
    crc32: int | None = None

    @property
    def succeeded(self) -> bool:
        return self.error is None


@dataclass(frozen=True, slots=True)
class BundleArchiveScan:
    archive_id: str
    entries: tuple[BundleEntryScan, ...] = ()
    error: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.error is None


@dataclass(frozen=True, slots=True)
class BundleEntryInput:
    archive: BundleArchiveInput
    entry_path: str
    sha256: str
    size: int
    aliases: tuple[tuple[str, str], ...] = ()
    crc32: int | None = None

    @property
    def node_id(self) -> str:
        return f"{self.archive.archive_id}::{self.entry_path}"


@dataclass(frozen=True, slots=True)
class BundleDependencyIssue:
    source_archive_id: str
    source_entry_path: str
    kind: DependencyKind
    logical_name: str


@dataclass(frozen=True, slots=True)
class BundleDependencyAmbiguity(BundleDependencyIssue):
    owner_node_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BundleScanFailure:
    archive_id: str
    entry_path: str | None
    error: str


@dataclass(frozen=True, slots=True)
class BundleComponent:
    component_id: str
    entries: tuple[BundleEntryInput, ...]
    dependency_component_ids: tuple[str, ...]
    unresolved_dependencies: tuple[BundleDependencyIssue, ...]
    ambiguous_dependencies: tuple[BundleDependencyAmbiguity, ...]
    scan_failed: bool = False

    @property
    def archives(self) -> tuple[BundleArchiveInput, ...]:
        by_id = {entry.archive.archive_id: entry.archive for entry in self.entries}
        return tuple(by_id[key] for key in sorted(by_id, key=str.casefold))

    @property
    def archive_ids(self) -> tuple[str, ...]:
        return tuple(archive.archive_id for archive in self.archives)

    @property
    def node_ids(self) -> tuple[str, ...]:
        return tuple(entry.node_id for entry in self.entries)

    @property
    def complete(self) -> bool:
        return not self.scan_failed and not self.unresolved_dependencies


@dataclass(frozen=True, slots=True)
class BundleDependencyPlan:
    components: tuple[BundleComponent, ...]
    unresolved_dependencies: tuple[BundleDependencyIssue, ...]
    ambiguous_dependencies: tuple[BundleDependencyAmbiguity, ...]
    scan_failures: tuple[BundleScanFailure, ...]

    @property
    def entries(self) -> tuple[BundleEntryInput, ...]:
        return tuple(
            entry for component in self.components for entry in component.entries
        )


@dataclass(frozen=True, slots=True)
class BundleExportBatch:
    batch_id: str
    target_components: tuple[BundleComponent, ...]
    loaded_components: tuple[BundleComponent, ...]

    @property
    def entries(self) -> tuple[BundleEntryInput, ...]:
        return tuple(
            entry for component in self.loaded_components for entry in component.entries
        )

    @property
    def target_entries(self) -> tuple[BundleEntryInput, ...]:
        return tuple(
            entry for component in self.target_components for entry in component.entries
        )

    @property
    def node_ids(self) -> tuple[str, ...]:
        return tuple(entry.node_id for entry in self.entries)

    @property
    def target_node_ids(self) -> tuple[str, ...]:
        return tuple(entry.node_id for entry in self.target_entries)

    @property
    def archive_ids(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                {entry.archive.archive_id for entry in self.entries},
                key=str.casefold,
            )
        )

    @property
    def total_bytes(self) -> int:
        return sum(entry.size for entry in self.entries)


def normalize_unity_file_identifier(value: str) -> str:
    normalized = value.replace("\\", "/").lower()
    if normalized.startswith("library/"):
        normalized = normalized[len("library/") :]
    elif normalized.startswith("resources/"):
        normalized = normalized[len("resources/") :]
    if normalized.startswith("archive:/"):
        normalized = PurePosixPath(normalized).name
    return normalized


class BundleDependencyPlanner:
    def __init__(
        self,
        cancellation_check: Callable[[], None] | None = None,
    ) -> None:
        self._cancellation_check = cancellation_check or (lambda: None)

    def build(
        self,
        archives: tuple[BundleArchiveInput, ...],
        scans: tuple[BundleArchiveScan, ...],
    ) -> BundleDependencyPlan:
        archive_by_id = {archive.archive_id: archive for archive in archives}
        scan_by_id = {scan.archive_id: scan for scan in scans}
        if (
            len(archive_by_id) != len(archives)
            or len(scan_by_id) != len(scans)
            or set(archive_by_id) != set(scan_by_id)
        ):
            raise ValueError("Dependency scan results do not match bundle inputs.")

        entry_candidates: dict[
            tuple[str, int], list[tuple[BundleArchiveInput, BundleEntryScan]]
        ] = defaultdict(list)
        archive_failures: list[BundleScanFailure] = []
        for scan in scans:
            self._cancellation_check()
            if not scan.succeeded:
                archive_failures.append(
                    BundleScanFailure(
                        scan.archive_id,
                        None,
                        scan.error or "Unknown archive scan failure",
                    )
                )
                continue
            seen_paths: set[str] = set()
            for scanned_entry in scan.entries:
                normalized_path = scanned_entry.entry_path.casefold()
                if normalized_path in seen_paths:
                    raise ValueError(
                        "Dependency scan contains duplicate archive entry paths."
                    )
                seen_paths.add(normalized_path)
                entry_candidates[(scanned_entry.sha256, scanned_entry.size)].append(
                    (archive_by_id[scan.archive_id], scanned_entry)
                )

        entry_by_node: dict[str, BundleEntryInput] = {}
        scan_by_node: dict[str, BundleEntryScan] = {}
        entry_failures: list[BundleScanFailure] = []
        for candidates in entry_candidates.values():
            self._cancellation_check()
            candidates.sort(
                key=lambda item: (
                    item[0].archive_id.casefold(),
                    item[1].entry_path.casefold(),
                )
            )
            archive, entry_scan = candidates[0]
            aliases = tuple(
                (item_archive.archive_id, item_scan.entry_path)
                for item_archive, item_scan in candidates[1:]
            )
            entry_input = BundleEntryInput(
                archive=archive,
                entry_path=entry_scan.entry_path,
                sha256=entry_scan.sha256,
                size=entry_scan.size,
                crc32=entry_scan.crc32,
                aliases=aliases,
            )
            entry_by_node[entry_input.node_id] = entry_input
            scan_by_node[entry_input.node_id] = entry_scan
            if not entry_scan.succeeded:
                entry_failures.append(
                    BundleScanFailure(
                        archive.archive_id,
                        entry_scan.entry_path,
                        entry_scan.error or "Unknown entry scan failure",
                    )
                )

        failed_ids = {
            f"{failure.archive_id}::{failure.entry_path}"
            for failure in entry_failures
            if failure.entry_path is not None
        }
        owner_index: dict[str, set[str]] = defaultdict(set)
        for node_id, entry_scan in scan_by_node.items():
            self._cancellation_check()
            if not entry_scan.succeeded:
                continue
            for serialized_file in entry_scan.serialized_files:
                owner_index[
                    normalize_unity_file_identifier(serialized_file.logical_name)
                ].add(node_id)
            for resource_file in entry_scan.resource_files:
                owner_index[normalize_unity_file_identifier(resource_file)].add(node_id)

        adjacency: dict[str, set[str]] = {node_id: set() for node_id in entry_by_node}
        unresolved: list[BundleDependencyIssue] = []
        ambiguities: list[BundleDependencyAmbiguity] = []
        for node_id, entry_scan in scan_by_node.items():
            self._cancellation_check()
            if not entry_scan.succeeded:
                continue
            source_entry = entry_by_node[node_id]
            references: list[tuple[DependencyKind, str]] = []
            for serialized_file in entry_scan.serialized_files:
                references.extend(
                    ("serialized_file", item) for item in serialized_file.dependencies
                )
            references.extend(
                ("streamed_resource", item.resource_path)
                for item in entry_scan.streamed_resources
            )
            for kind, raw_name in references:
                logical_name = normalize_unity_file_identifier(raw_name)
                if logical_name in _ENGINE_RESOURCES:
                    continue
                owners = tuple(
                    sorted(owner_index.get(logical_name, ()), key=str.casefold)
                )
                if not owners:
                    unresolved.append(
                        BundleDependencyIssue(
                            source_entry.archive.archive_id,
                            source_entry.entry_path,
                            kind,
                            logical_name,
                        )
                    )
                    continue
                if node_id in owners:
                    continue
                if len(owners) > 1:
                    ambiguities.append(
                        BundleDependencyAmbiguity(
                            source_entry.archive.archive_id,
                            source_entry.entry_path,
                            kind,
                            logical_name,
                            owners,
                        )
                    )
                for owner in owners:
                    adjacency[node_id].add(owner)

        unresolved.sort(key=self._issue_key)
        ambiguities.sort(key=self._issue_key)
        unresolved_by_node: dict[str, list[BundleDependencyIssue]] = defaultdict(list)
        ambiguities_by_node: dict[str, list[BundleDependencyAmbiguity]] = defaultdict(
            list
        )
        for issue in unresolved:
            unresolved_by_node[
                f"{issue.source_archive_id}::{issue.source_entry_path}"
            ].append(issue)
        for issue in ambiguities:
            ambiguities_by_node[
                f"{issue.source_archive_id}::{issue.source_entry_path}"
            ].append(issue)
        member_groups = self._strongly_connected_components(adjacency)
        component_id_by_node: dict[str, str] = {}
        for member_ids in member_groups:
            self._cancellation_check()
            component_id = self._component_id(member_ids)
            for member_id in member_ids:
                component_id_by_node[member_id] = component_id

        components: list[BundleComponent] = []
        for member_ids in member_groups:
            self._cancellation_check()
            component_id = component_id_by_node[member_ids[0]]
            dependency_component_ids = tuple(
                sorted(
                    {
                        component_id_by_node[dependency]
                        for member_id in member_ids
                        for dependency in adjacency[member_id]
                        if component_id_by_node[dependency] != component_id
                    },
                    key=str.casefold,
                )
            )
            component_unresolved = tuple(
                issue
                for member_id in member_ids
                for issue in unresolved_by_node.get(member_id, ())
            )
            component_ambiguities = tuple(
                issue
                for member_id in member_ids
                for issue in ambiguities_by_node.get(member_id, ())
            )
            components.append(
                BundleComponent(
                    component_id=component_id,
                    entries=tuple(entry_by_node[item] for item in member_ids),
                    dependency_component_ids=dependency_component_ids,
                    unresolved_dependencies=component_unresolved,
                    ambiguous_dependencies=component_ambiguities,
                    scan_failed=any(
                        member_id in failed_ids for member_id in member_ids
                    ),
                )
            )

        failures = tuple(
            sorted(
                archive_failures + entry_failures,
                key=lambda item: (
                    item.archive_id.casefold(),
                    (item.entry_path or "").casefold(),
                ),
            )
        )
        return BundleDependencyPlan(
            components=tuple(components),
            unresolved_dependencies=tuple(unresolved),
            ambiguous_dependencies=tuple(ambiguities),
            scan_failures=failures,
        )

    @staticmethod
    def _strongly_connected_components(
        adjacency: dict[str, set[str]],
    ) -> tuple[tuple[str, ...], ...]:
        visited: set[str] = set()
        finish_order: list[str] = []
        for start in sorted(adjacency, key=str.casefold):
            if start in visited:
                continue
            stack = [(start, False)]
            while stack:
                current, expanded = stack.pop()
                if expanded:
                    finish_order.append(current)
                    continue
                if current in visited:
                    continue
                visited.add(current)
                stack.append((current, True))
                for dependency in sorted(
                    adjacency[current],
                    key=str.casefold,
                    reverse=True,
                ):
                    if dependency not in visited:
                        stack.append((dependency, False))

        reverse_adjacency: dict[str, set[str]] = {
            node_id: set() for node_id in adjacency
        }
        for source, dependencies in adjacency.items():
            for dependency in dependencies:
                reverse_adjacency[dependency].add(source)

        assigned: set[str] = set()
        groups: list[tuple[str, ...]] = []
        for start in reversed(finish_order):
            if start in assigned:
                continue
            members: set[str] = set()
            reverse_stack = [start]
            while reverse_stack:
                current = reverse_stack.pop()
                if current in assigned:
                    continue
                assigned.add(current)
                members.add(current)
                reverse_stack.extend(reverse_adjacency[current] - assigned)
            groups.append(tuple(sorted(members, key=str.casefold)))
        return tuple(sorted(groups, key=lambda item: item[0].casefold()))

    @staticmethod
    def _component_id(node_ids: tuple[str, ...]) -> str:
        digest = hashlib.sha256("\n".join(node_ids).encode("utf8")).hexdigest()
        return digest[:12]

    @staticmethod
    def _issue_key(issue: BundleDependencyIssue) -> tuple[str, str, str, str]:
        return (
            issue.source_archive_id.casefold(),
            issue.source_entry_path.casefold(),
            issue.kind,
            issue.logical_name,
        )
