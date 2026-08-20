from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from heapq import heappop, heappush, nlargest
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

    @property
    def succeeded(self) -> bool:
        return self.error is None


@dataclass(frozen=True, slots=True)
class BundleArchiveScan:
    archive_id: str
    sha256: str
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
    max_batch_bytes: int

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

    @property
    def oversized(self) -> bool:
        return self.total_bytes > self.max_batch_bytes


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
        member_groups = self._strongly_connected_components(adjacency)
        component_id_by_node: dict[str, str] = {}
        for member_ids in member_groups:
            component_id = self._component_id(member_ids)
            for member_id in member_ids:
                component_id_by_node[member_id] = component_id

        components: list[BundleComponent] = []
        for member_ids in member_groups:
            member_set = set(member_ids)
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
                for issue in unresolved
                if f"{issue.source_archive_id}::{issue.source_entry_path}" in member_set
            )
            component_ambiguities = tuple(
                issue
                for issue in ambiguities
                if f"{issue.source_archive_id}::{issue.source_entry_path}" in member_set
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


class BundleDependencyBatchPlanner:
    def __init__(self, *, max_batch_bytes: int) -> None:
        if max_batch_bytes <= 0:
            raise ValueError("AssetRipper batch size must be positive.")
        self._max_batch_bytes = max_batch_bytes

    def build(
        self,
        plan: BundleDependencyPlan,
    ) -> tuple[BundleExportBatch, ...]:
        if not plan.components:
            return ()
        component_index = {
            component.component_id: index
            for index, component in enumerate(plan.components)
        }
        dependency_indexes = tuple(
            tuple(
                component_index[dependency_id]
                for dependency_id in component.dependency_component_ids
            )
            for component in plan.components
        )
        closure_bits, closure_members = self._dependency_closures(dependency_indexes)
        component_bytes = tuple(
            sum(entry.size for entry in component.entries)
            for component in plan.components
        )
        closure_bytes = tuple(
            sum(component_bytes[member] for member in members)
            for members in closure_members
        )
        candidate_order = tuple(
            sorted(
                range(len(plan.components)),
                key=lambda index: (-closure_bytes[index], index),
            )
        )

        target_groups: list[list[int]] = []
        loaded_groups: list[int] = []
        loaded_member_groups: list[set[int]] = []
        loaded_group_bytes: list[int] = []
        groups_by_component: list[list[int]] = [[] for _ in plan.components]
        for target_index in candidate_order:
            closure = closure_bits[target_index]
            members = closure_members[target_index]
            already_loaded_groups = groups_by_component[target_index]
            if already_loaded_groups:
                candidate_groups = already_loaded_groups[:1]
            else:
                target_bytes = component_bytes[target_index]
                candidate_groups = nlargest(
                    2,
                    (
                        group_index
                        for group_index, used_bytes in enumerate(loaded_group_bytes)
                        if self._max_batch_bytes - used_bytes >= target_bytes
                    ),
                    key=lambda group_index: (
                        (closure & loaded_groups[group_index]).bit_count(),
                        self._max_batch_bytes - loaded_group_bytes[group_index],
                        -group_index,
                    ),
                )

            selected: int | None = None
            selected_score: tuple[int, int, int] | None = None
            for group_index in candidate_groups:
                loaded_members = loaded_member_groups[group_index]
                shared_bytes = sum(
                    component_bytes[member]
                    for member in members
                    if member in loaded_members
                )
                added_bytes = closure_bytes[target_index] - shared_bytes
                if (
                    added_bytes > 0
                    and loaded_group_bytes[group_index] + added_bytes
                    > self._max_batch_bytes
                ):
                    continue
                score = (shared_bytes, -added_bytes, -group_index)
                if selected_score is None or score > selected_score:
                    selected = group_index
                    selected_score = score

            if (
                selected is None
                and closure_bytes[target_index] <= self._max_batch_bytes
            ):
                best_fit: tuple[int, int] | None = None
                for group_index, used_bytes in enumerate(loaded_group_bytes):
                    remaining = self._max_batch_bytes - used_bytes
                    if closure_bytes[target_index] <= remaining:
                        fit_score = (
                            remaining - closure_bytes[target_index],
                            group_index,
                        )
                        if best_fit is None or fit_score < best_fit:
                            best_fit = fit_score
                            selected = group_index

            if selected is None:
                selected = len(target_groups)
                target_groups.append([])
                loaded_groups.append(0)
                loaded_member_groups.append(set())
                loaded_group_bytes.append(0)

            loaded_members = loaded_member_groups[selected]
            added_members = tuple(
                member for member in members if member not in loaded_members
            )
            added_bytes = sum(component_bytes[member] for member in added_members)
            target_groups[selected].append(target_index)
            loaded_groups[selected] |= closure
            loaded_members.update(added_members)
            loaded_group_bytes[selected] += added_bytes
            for member in added_members:
                groups_by_component[member].append(selected)

        grouped = [
            (tuple(targets), tuple(self._iter_bits(loaded_groups[index])))
            for index, targets in enumerate(target_groups)
        ]

        width = max(1, len(str(len(grouped))))
        return tuple(
            BundleExportBatch(
                batch_id=f"batch-{index:0{width}d}",
                target_components=tuple(
                    plan.components[item] for item in target_indexes
                ),
                loaded_components=tuple(
                    plan.components[item] for item in loaded_indexes
                ),
                max_batch_bytes=self._max_batch_bytes,
            )
            for index, (target_indexes, loaded_indexes) in enumerate(grouped, start=1)
        )

    @staticmethod
    def _dependency_closures(
        dependency_indexes: tuple[tuple[int, ...], ...],
    ) -> tuple[tuple[int, ...], tuple[tuple[int, ...], ...]]:
        remaining = [len(items) for items in dependency_indexes]
        dependents: list[list[int]] = [[] for _ in dependency_indexes]
        for source, dependencies in enumerate(dependency_indexes):
            for dependency in dependencies:
                dependents[dependency].append(source)
        ready: list[int] = []
        for index, count in enumerate(remaining):
            if count == 0:
                heappush(ready, index)

        closures = [0] * len(dependency_indexes)
        closure_members: list[frozenset[int]] = [
            frozenset() for _ in dependency_indexes
        ]
        completed = 0
        while ready:
            current = heappop(ready)
            closure = 1 << current
            members = {current}
            for dependency in dependency_indexes[current]:
                closure |= closures[dependency]
                members.update(closure_members[dependency])
            closures[current] = closure
            closure_members[current] = frozenset(members)
            completed += 1
            for dependent in dependents[current]:
                remaining[dependent] -= 1
                if remaining[dependent] == 0:
                    heappush(ready, dependent)
        if completed != len(dependency_indexes):
            raise ValueError("AssetRipper component dependency graph contains a cycle.")
        return tuple(closures), tuple(
            tuple(sorted(members)) for members in closure_members
        )

    @staticmethod
    def _iter_bits(value: int) -> Iterator[int]:
        while value:
            lowest = value & -value
            yield lowest.bit_length() - 1
            value ^= lowest

    @classmethod
    def _bits_size(cls, value: int, sizes: tuple[int, ...]) -> int:
        return sum(sizes[index] for index in cls._iter_bits(value))
