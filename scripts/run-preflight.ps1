#!/usr/bin/env pwsh

$ErrorActionPreference = "Stop"

function Invoke-CheckedCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Label,
        [Parameter(Mandatory = $true)]
        [scriptblock]$Command
    )

    Write-Host "Running $Label..." -ForegroundColor Cyan
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE."
    }
}

Invoke-CheckedCommand -Label "compileall" -Command { python -m compileall src tests scripts }
Invoke-CheckedCommand -Label "ruff" -Command { uv run ruff check . }
Invoke-CheckedCommand -Label "mypy" -Command { uv run mypy }

Write-Host "Running pylint advisory checks..." -ForegroundColor Cyan
uv run pylint --rcfile .pylintrc src/ba_downloader scripts
if ($LASTEXITCODE -ne 0) {
    Write-Warning "Pylint reported advisory issues."
}

Invoke-CheckedCommand -Label "pytest" -Command { uv run pytest -q }
