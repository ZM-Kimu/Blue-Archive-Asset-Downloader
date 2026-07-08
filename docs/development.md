# Development Notes

This document keeps only the project rules needed for day-to-day maintenance.

## Environment

- Python 3.10+
- `uv`
- .NET 10 SDK
- Initialized Git submodules

```bash
uv sync --group dev
```

## Checks

Run focused tests while editing, then run the full gate before handing off broad changes.

```bash
uv run pytest
uv run black --check src tests
uv run ruff check src tests
uv run mypy
git diff --check
```

Use `scripts/preflight_check.ps1` when a single local gate is more convenient.

## Architecture

- CLI parses arguments and delegates to application use cases.
- Application code owns user workflows and stable settings models.
- Bootstrap resolves a region service profile for CN, GL, or JP.
- Region profiles own catalog providers, runtime preparation, dump backend selection, table routing, and character index source policy.
- Shared extraction code must stay region-neutral and consume profile-provided strategies.
- CN metadata recovery stays in `infrastructure.tools.cn_metadata_recovery` as a reusable engine; the CN region backend only orchestrates it.
- Cpp2IL exporter generation is shared, but region-specific shims must be injected by the requesting region backend.

## Boundaries

- Do not make shared extraction import concrete CN/GL/JP region modules.
- Do not put region-specific route names, schema names, or command hints in shared engines.
- Do not add numeric LOC or branching budgets. Keep code readable by ownership, not by mechanical splitting.
- Internal Python import paths may change; CLI commands and default output contracts need deliberate migration notes.

## Outputs

Schema workflows produce:

- `<Extracted>/Dumps/dump.cs`
- `<Extracted>/Dumps/memorypack_formatters.json`

Character index workflows produce:

- `<REGION>CharacterIndex.json`

Table extraction writes JSON under `<Extracted>/Table/` according to the active region profile.

## Compatibility Notes

Breaking internal refactors are acceptable when they simplify ownership. Public CLI changes must update `--help`, `README.md`, and `docs/README.en.md`, and the migration risk must be called out in the change summary.
