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

    args = parser.parse_args(["character-index", "build", "--region", "jp"])

    assert args.command == "character-index"
    assert args.character_index_command == "build"
    assert args.region == "jp"


def test_relation_build_command_is_removed() -> None:
    parser = build_parser()

    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["relation", "build", "--region", "jp"])

    assert exc_info.value.code == 2


def test_character_index_store_writes_entries_schema(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    store = CharacterIndexFileStore(RecordingLogger())
    monkeypatch.chdir(tmp_path)

    index_path = store.save(
        "1.0.0",
        "jp",
        [
            CharacterIndexEntry(
                10003,
                dev_name="Hihumi_default",
                names=["Hifumi"],
                file_aliases={"Hihumi"},
            )
        ],
    )

    assert index_path == (tmp_path / "JPCharacterIndex.json").resolve()
    old_index_name = "JP" + "Character" + "Relation.json"
    assert not (tmp_path / old_index_name).exists()
    assert json.loads(index_path.read_text(encoding="utf8")) == {
        "version": "JP1.0.0",
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


def test_character_index_store_rejects_legacy_relation_schema(
    tmp_path: Path,
) -> None:
    index_path = tmp_path / "JPCharacterIndex.json"
    index_path.write_text(
        json.dumps({"version": "JP1.0.0", "relations": []}),
        encoding="utf8",
    )
    store = CharacterIndexFileStore(RecordingLogger())

    with pytest.raises(ValueError, match="entries"):
        store.load_path(index_path, build_runtime_context(tmp_path, region="jp"))


def test_character_index_store_does_not_read_old_relation_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    old_index_name = "JP" + "Character" + "Relation.json"
    (tmp_path / old_index_name).write_text(
        json.dumps({"version": "JP1.0.0", "relations": []}),
        encoding="utf8",
    )
    monkeypatch.chdir(tmp_path)
    store = CharacterIndexFileStore(RecordingLogger())

    with pytest.raises(FileNotFoundError):
        store.load(build_runtime_context(tmp_path, region="jp"))
