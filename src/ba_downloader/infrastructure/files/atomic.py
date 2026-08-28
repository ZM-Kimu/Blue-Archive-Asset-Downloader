from __future__ import annotations

import json
import os
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any
from uuid import uuid4


def write_json_atomic(
    path: Path,
    payload: Any,
    *,
    indent: int | None = None,
    ensure_ascii: bool = True,
    sort_keys: bool = False,
    separators: tuple[str, str] | None = None,
    trailing_newline: bool = True,
    validate: Callable[[Path], None] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(
                payload,
                stream,
                indent=indent,
                ensure_ascii=ensure_ascii,
                sort_keys=sort_keys,
                separators=separators,
            )
            if trailing_newline:
                stream.write("\n")
        if validate is not None:
            validate(temporary)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def publish_staged_directory(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    backup = destination.with_name(f".{destination.name}.replaced-{uuid4().hex}")
    had_destination = destination.exists() or destination.is_symlink()
    if had_destination:
        destination.replace(backup)
    try:
        shutil.move(str(source), str(destination))
    except BaseException:
        if had_destination and backup.exists() and not destination.exists():
            backup.replace(destination)
        raise
    else:
        if backup.is_dir():
            shutil.rmtree(backup)
        else:
            backup.unlink(missing_ok=True)


def recover_replaced_directory(destination: Path) -> None:
    backups = sorted(
        destination.parent.glob(f".{destination.name}.replaced-*"),
        key=lambda path: path.name,
    )
    if destination.exists() or destination.is_symlink():
        stale = backups
    elif backups:
        latest = backups.pop()
        latest.replace(destination)
        stale = backups
    else:
        return
    for backup in stale:
        if backup.is_dir():
            shutil.rmtree(backup, ignore_errors=True)
        else:
            backup.unlink(missing_ok=True)
