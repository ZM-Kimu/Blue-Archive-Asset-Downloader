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

Invoke-CheckedCommand -Label "compileall" -Command { python -m compileall src scripts }
Invoke-CheckedCommand -Label "ruff format" -Command { uv run ruff format --check . }
Invoke-CheckedCommand -Label "ruff" -Command { uv run ruff check . }
Invoke-CheckedCommand -Label "mypy" -Command { uv run mypy }
Invoke-CheckedCommand -Label "architecture boundaries" -Command { uv run lint-imports }

Write-Host "Running pylint advisory checks..." -ForegroundColor Cyan
uv run pylint --rcfile .pylintrc src/ba_downloader scripts
if ($LASTEXITCODE -ne 0) {
    Write-Warning "Pylint reported advisory issues."
}

Invoke-CheckedCommand -Label "pytest" -Command { & "$PSScriptRoot/run-tests.ps1" -Suite all }
