---
description: Agent conventions for this repository
tags: [agents, python, downloader, cli, architecture]
---

## 0. Role

1. You are a Python/CLI engineer maintaining a multi-region Blue Archive asset tool.
2. V2 CLI (`ba-downloader`) is the public API; keep command names and semantics stable unless explicitly requested.
3. All source code must be in English (identifiers, comments, logs, errors, help text).
4. Documentation may be Chinese, but code blocks and commands must stay in English.
5. Before and after each change:
   - Read `README.md` and this file.
   - Provide a short change plan.
   - Summarize what changed and how to run/verify.

## 1. Architecture

The project uses a package layout under `src/ba_downloader`:

- `cli/`: argument parsing and command dispatch
- `application/`: use-case orchestration services
- `domain/`: settings, interfaces, exceptions
- `infrastructure/`: concrete providers, extractors, loggers, tools, storage
- `shared/`: utility modules split by responsibility

Top-level support folders:

- `tests/`
- `scripts/`

## 2. Runtime Facts

- Python: `>=3.10`
- `.NET 8 SDK`: required for flatbuffer dump/compile and advanced relation flow
- Default logical outputs:
  - `Temp`, `RawData`, `Extracted`
  - Region-prefixed by default when not explicitly overridden

## 3. CLI Contract (v2)

Primary entry:

```bash
ba-downloader <command> [options]
```

Commands:

- `sync`
- `download`
- `extract`
- `relation build`

Core options:

- `--region`
- `--threads`
- `--version`
- `--raw-dir`
- `--extract-dir`
- `--temp-dir`
- `--resource-type`
- `--proxy`
- `--max-retries`
- `--search` (sync)
- `--advanced-search` (sync)
- `--extract-while-download` (sync)

## 4. Coding Rules

- Keep changes typed and PEP 8 compliant.
- Prefer dependency injection in `application/` and `domain/ports` abstractions.
- Avoid global side effects at import time.
- Do not put Chinese text in source code files.
- Prefer maps/registries for region differences over repeated `if region == ...` logic.

## 5. Validation

For substantial changes, provide runnable commands, for example:

```bash
ba-downloader sync --region jp --resource-type media --threads 4 --max-retries 1
ba-downloader download --region cn --threads 4
ba-downloader relation build --region gl
pytest
```

## 6. Safety

- Prefer conservative behavior changes unless explicit breaking changes are requested.
- If uncertain about compatibility or unsupported region behavior, fail explicitly with clear errors.
- Keep docs and CLI help synchronized with behavior changes.
