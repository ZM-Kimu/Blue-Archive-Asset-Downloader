from __future__ import annotations

import json

from fastapi import APIRouter, Query

from ba_downloader.api.models import (
    CharacterIndexEntriesResponse,
    CharacterIndexEntryResponse,
    CharacterIndexSearchRequest,
    CharacterIndexSearchResponse,
    CharacterIndexSummaryResponse,
)
from ba_downloader.api.problems import ApiProblem, require_context
from ba_downloader.api.services import ApiServices
from ba_downloader.domain.models.character import CharacterIndex


def create_router(services: ApiServices) -> APIRouter:
    router = APIRouter(prefix="/api/v1/contexts/{context_id}/character-index")

    def load_index(context_id: str) -> CharacterIndex:
        require_context(services, context_id)
        try:
            return services.load_character_index(context_id)
        except FileNotFoundError as exc:
            raise ApiProblem(
                404,
                "CHARACTER_INDEX_NOT_FOUND",
                "Character index not found",
                str(exc),
            ) from exc
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            raise ApiProblem(
                422,
                "CHARACTER_INDEX_INVALID",
                "Character index is invalid",
                str(exc),
            ) from exc

    @router.get(
        "",
        operation_id="getCharacterIndex",
        response_model=CharacterIndexSummaryResponse,
    )
    def get_character_index(context_id: str) -> dict[str, object]:
        index = load_index(context_id)
        return {"version": index.version, "entry_count": len(index.entries)}

    @router.get(
        "/entries",
        operation_id="listCharacterIndexEntries",
        response_model=CharacterIndexEntriesResponse,
    )
    def list_character_index_entries(
        context_id: str,
        cursor: int = Query(default=0, ge=0),
        limit: int = Query(default=100, ge=1, le=1000),
    ) -> dict[str, object]:
        entries = load_index(context_id).entries
        return {
            "items": entries[cursor : cursor + limit],
            "next_cursor": str(cursor + limit)
            if cursor + limit < len(entries)
            else None,
        }

    @router.get(
        "/entries/{character_id}",
        operation_id="getCharacterIndexEntry",
        response_model=CharacterIndexEntryResponse,
    )
    def get_character_index_entry(context_id: str, character_id: int) -> object:
        for entry in load_index(context_id).entries:
            if entry.character_id == character_id:
                return entry
        raise ApiProblem(
            404, "CHARACTER_NOT_FOUND", "Character not found", str(character_id)
        )

    @router.post(
        "/search",
        operation_id="searchCharacterIndex",
        response_model=CharacterIndexSearchResponse,
    )
    def search_character_index(
        context_id: str, body: CharacterIndexSearchRequest
    ) -> dict[str, object]:
        keywords = services.search_character_index(load_index(context_id), body.terms)
        return {"asset_keywords": keywords}

    return router
