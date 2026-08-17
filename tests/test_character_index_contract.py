from __future__ import annotations

import json
from pathlib import Path

import pytest

from ba_downloader.cli.main import build_parser
from ba_downloader.domain.models.character import CharacterIndexEntry
from ba_downloader.infrastructure.extraction.character.index_store import (
    CharacterIndexFileStore,
)
from support import RecordingLogger, build_runtime_context


def test_character_index_build_command_parses() -> None:
    parser = build_parser()

    args = parser.parse_args(["index", "build", "--region", "jp"])

    assert args.command_group == "index"
    assert args.operation == "build"
    assert args.region == "jp"


def test_character_index_store_writes_entries_schema(
    tmp_path: Path,
) -> None:
    store = CharacterIndexFileStore(RecordingLogger())
    context = build_runtime_context(tmp_path, region="jp", version="1.0.0")

    index_path = store.save(
        context,
        [
            CharacterIndexEntry(
                10003,
                dev_name="Hihumi_default",
                names=["Hifumi"],
                file_aliases={"Hihumi"},
            )
        ],
    )

    assert index_path == (tmp_path / "indexes" / "characters.json").resolve()
    assert json.loads(index_path.read_text(encoding="utf8")) == {
        "schema_version": 1,
        "metadata": {
            "region": "jp",
            "platform": "android",
            "resource_version": "1.0.0",
        },
        "entries": [
            {
                "character_id": 10003,
                "dev_name": "Hihumi_default",
                "names": ["Hifumi"],
                "file_aliases": ["Hihumi"],
                "cv": "",
                "age": 0,
                "height": 0,
                "birthday": "",
                "illustrator": "",
                "school_en": "",
                "club_en": "",
            }
        ],
    }


def test_character_index_store_rejects_pre_index_schema(
    tmp_path: Path,
) -> None:
    index_path = tmp_path / "indexes" / "characters.json"
    index_path.parent.mkdir(parents=True)
    index_path.write_text(
        json.dumps({"version": "JP1.0.0", "relations": []}),
        encoding="utf8",
    )
    store = CharacterIndexFileStore(RecordingLogger())

    with pytest.raises(ValueError, match="schema_version"):
        store.load_path(index_path, build_runtime_context(tmp_path, region="jp"))


def test_character_index_store_rejects_empty_output_without_replacing_old_index(
    tmp_path: Path,
) -> None:
    store = CharacterIndexFileStore(RecordingLogger())
    context = build_runtime_context(tmp_path, region="jp", version="1.0.0")
    index_path = store.save(context, [CharacterIndexEntry(10003)])
    original_payload = index_path.read_bytes()

    with pytest.raises(ValueError, match="at least one entry"):
        store.save(context, [])

    assert index_path.read_bytes() == original_payload
    assert list(index_path.parent.glob("*.tmp")) == []


def test_character_index_store_semantically_validates_every_entry(
    tmp_path: Path,
) -> None:
    context = build_runtime_context(tmp_path, region="jp", version="1.0.0")
    index_path = tmp_path / "indexes" / "characters.json"
    index_path.parent.mkdir(parents=True)
    index_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "metadata": {
                    "region": "jp",
                    "platform": "android",
                    "resource_version": "1.0.0",
                },
                "entries": [
                    {
                        "character_id": "10003",
                        "dev_name": "Hihumi_default",
                        "names": [],
                        "file_aliases": [],
                        "cv": "",
                        "age": 0,
                        "height": 0,
                        "birthday": "",
                        "illustrator": "",
                        "school_en": "",
                        "club_en": "",
                    }
                ],
            }
        ),
        encoding="utf8",
    )
    store = CharacterIndexFileStore(RecordingLogger())

    assert store.verify(context) is False
    with pytest.raises(ValueError, match="integer fields"):
        store.load(context)
