#!/usr/bin/env pwsh

python -m compileall src tests scripts
uv run ruff check .
uv run mypy
uv run pylint --rcfile .pylintrc src/ba_downloader scripts
uv run pytest -q
