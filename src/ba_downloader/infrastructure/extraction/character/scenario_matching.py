from __future__ import annotations

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
