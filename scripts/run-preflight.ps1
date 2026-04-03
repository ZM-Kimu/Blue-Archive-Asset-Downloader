#!/usr/bin/env pwsh

python -m compileall src tests scripts
uv run pytest -q
