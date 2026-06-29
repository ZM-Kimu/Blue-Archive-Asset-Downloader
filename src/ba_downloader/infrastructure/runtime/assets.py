from __future__ import annotations

from pathlib import Path


class RuntimeAssetLocator:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir

    def find_first(self, file_names: tuple[str, ...]) -> Path | None:
        if not self.base_dir.exists():
            return None

        for file_name in file_names:
            matches = sorted(
                self.base_dir.rglob(file_name),
                key=lambda path: (len(path.parts), path.as_posix().lower()),
            )
            if matches:
                return matches[0]
        return None
