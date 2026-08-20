import json
from pathlib import Path

import pytest

from ba_downloader.infrastructure.files.atomic import (
    publish_staged_directory,
    write_json_atomic,
)


def test_write_json_atomic_validates_before_replacing_existing_file(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "manifest.json"
    destination.write_text('{"old":true}\n', encoding="utf-8")

    def reject(path: Path) -> None:
        assert json.loads(path.read_text(encoding="utf-8")) == {"new": True}
        raise ValueError("invalid manifest")

    with pytest.raises(ValueError, match="invalid manifest"):
        write_json_atomic(destination, {"new": True}, validate=reject)

    assert destination.read_text(encoding="utf-8") == '{"old":true}\n'
    assert list(tmp_path.glob(".*.tmp")) == []


def test_publish_staged_directory_replaces_existing_tree(tmp_path: Path) -> None:
    source = tmp_path / "staging"
    destination = tmp_path / "published"
    source.mkdir()
    destination.mkdir()
    (source / "new.txt").write_text("new", encoding="utf-8")
    (destination / "old.txt").write_text("old", encoding="utf-8")

    publish_staged_directory(source, destination)

    assert not source.exists()
    assert (destination / "new.txt").read_text(encoding="utf-8") == "new"
    assert not (destination / "old.txt").exists()
    assert list(tmp_path.glob(".published.replaced-*")) == []
