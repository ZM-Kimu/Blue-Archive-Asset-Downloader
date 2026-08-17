from __future__ import annotations

import ast
import tomllib
from pathlib import Path


def test_api_dependencies_are_optional() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]

    assert not any(
        dependency.startswith(("fastapi", "uvicorn"))
        for dependency in project["dependencies"]
    )
    assert {
        dependency.split(">=", 1)[0]
        for dependency in project["optional-dependencies"]["api"]
    } == {
        "fastapi",
        "uvicorn",
    }


def test_normal_cli_module_does_not_import_api_frameworks() -> None:
    tree = ast.parse(Path("src/ba_downloader/cli/main.py").read_text(encoding="utf-8"))
    imported_roots = {
        alias.name.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_roots.update(
        node.module.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    )

    assert imported_roots.isdisjoint({"fastapi", "uvicorn"})


def test_cli_does_not_import_http_api_adapter() -> None:
    tree = ast.parse(Path("src/ba_downloader/cli/main.py").read_text(encoding="utf-8"))
    imported_modules = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_modules.update(
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    )

    assert not any(
        module == "ba_downloader.api" or module.startswith("ba_downloader.api.")
        for module in imported_modules
    )
