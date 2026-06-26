from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from ba_downloader.domain.models.character import CharacterData


def normalize_lookup_token(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


def normalize_lookup_tokens(values: set[str]) -> set[str]:
    return {token for value in values if (token := normalize_lookup_token(value))}


def tokens_match_exact(candidates: set[str], references: set[str]) -> bool:
    return bool(
        normalize_lookup_tokens(candidates).intersection(
            normalize_lookup_tokens(references)
        )
    )


def token_matches_prefix(candidate: str, prefix: str) -> bool:
    normalized_candidate = normalize_lookup_token(candidate)
    normalized_prefix = normalize_lookup_token(prefix)
    if len(normalized_prefix) < 3:
        return False
    if normalized_candidate == normalized_prefix:
        return True
    if not normalized_candidate.startswith(normalized_prefix):
        return False

    raw_candidate = candidate.strip()
    raw_prefix = prefix.strip()
    if not raw_candidate.casefold().startswith(raw_prefix.casefold()):
        return False

    suffix = raw_candidate[len(raw_prefix) :]
    if not suffix:
        return True
    first_suffix_char = suffix[0]
    return (
        first_suffix_char in {"_", "-", " ", "."}
        or first_suffix_char.isdigit()
        or first_suffix_char.isupper()
    )


def tokens_match_prefix(candidates: set[str], references: set[str]) -> bool:
    return any(
        token_matches_prefix(candidate, reference)
        for candidate in candidates
        for reference in references
    )


def is_plain_default_dev_name(dev_name: str) -> bool:
    parts = dev_name.split("_")
    return len(parts) == 2 and parts[1].casefold() == "default"


def collect_dev_exact_aliases(dev_name: str) -> set[str]:
    if not dev_name:
        return set()

    aliases = {dev_name}
    parts = dev_name.split("_")
    if is_plain_default_dev_name(dev_name):
        aliases.add(parts[0])
    elif len(parts) >= 2:
        aliases.add("_".join(parts[:2]))
    return aliases


def collect_dev_prefix_aliases(dev_name: str) -> set[str]:
    if not dev_name:
        return set()
    return {dev_name.split("_", 1)[0]}


def candidate_rank(
    char_data: CharacterData,
    file_candidates: set[str],
) -> tuple[int, int, int, int]:
    dev_exact_aliases = collect_dev_exact_aliases(char_data.dev_name)
    full_dev_exact = int(tokens_match_exact(file_candidates, dev_exact_aliases))
    base_default_exact = int(
        is_plain_default_dev_name(char_data.dev_name)
        and tokens_match_exact(
            file_candidates,
            collect_dev_prefix_aliases(char_data.dev_name),
        )
    )
    has_profile_names = int(bool(char_data.names))
    plain_default = int(is_plain_default_dev_name(char_data.dev_name))
    return full_dev_exact, base_default_exact, has_profile_names, plain_default


def select_best_scenario_candidate(
    candidates: list[CharacterData],
    file_candidates: set[str],
) -> CharacterData | None:
    unique_candidates = {candidate.character_id: candidate for candidate in candidates}
    if not unique_candidates:
        return None

    ranked_candidates = sorted(
        unique_candidates.values(),
        key=lambda candidate: candidate_rank(candidate, file_candidates),
        reverse=True,
    )
    if len(ranked_candidates) == 1:
        return ranked_candidates[0]

    best_rank = candidate_rank(ranked_candidates[0], file_candidates)
    second_rank = candidate_rank(ranked_candidates[1], file_candidates)
    if best_rank == second_rank:
        return None
    return ranked_candidates[0]


class ScenarioMatchIndex:
    def __init__(self, characters: Iterable[CharacterData]) -> None:
        self.name_index: dict[str, list[CharacterData]] = defaultdict(list)
        self.exact_index: dict[str, list[CharacterData]] = defaultdict(list)
        self.prefix_index: dict[str, list[tuple[str, CharacterData]]] = defaultdict(
            list
        )
        for character in characters:
            self.add_character(character)

    def add_character(self, character: CharacterData) -> None:
        for token in normalize_lookup_tokens(set(character.names or [])):
            self.name_index[token].append(character)

        aliases = set(character.file_name or set())
        exact_references = aliases.union(collect_dev_exact_aliases(character.dev_name))
        for token in normalize_lookup_tokens(exact_references):
            self.exact_index[token].append(character)

        prefix_references = aliases.union(
            collect_dev_prefix_aliases(character.dev_name)
        )
        for reference in prefix_references:
            token = normalize_lookup_token(reference)
            if len(token) >= 3:
                self.prefix_index[token].append((reference, character))

    def match(
        self,
        scenario_names: set[str],
        file_candidates: set[str],
    ) -> CharacterData | None:
        normalized_scenario_names = normalize_lookup_tokens(scenario_names)
        candidate_groups = (
            self._match_names(normalized_scenario_names),
            self._match_exact_files(file_candidates),
            self._match_prefix_files(file_candidates),
        )
        for candidates in candidate_groups:
            if matched := select_best_scenario_candidate(candidates, file_candidates):
                return matched
        return None

    def _match_names(self, normalized_scenario_names: set[str]) -> list[CharacterData]:
        candidates: list[CharacterData] = []
        for token in normalized_scenario_names:
            candidates.extend(self.name_index.get(token, []))
        return candidates

    def _match_exact_files(self, file_candidates: set[str]) -> list[CharacterData]:
        candidates: list[CharacterData] = []
        for token in normalize_lookup_tokens(file_candidates):
            candidates.extend(self.exact_index.get(token, []))
        return candidates

    def _match_prefix_files(self, file_candidates: set[str]) -> list[CharacterData]:
        candidates: list[CharacterData] = []
        for candidate in file_candidates:
            normalized_candidate = normalize_lookup_token(candidate)
            for end in range(3, len(normalized_candidate) + 1):
                prefix_token = normalized_candidate[:end]
                for raw_prefix, character in self.prefix_index.get(prefix_token, []):
                    if token_matches_prefix(candidate, raw_prefix):
                        candidates.append(character)
        return candidates
