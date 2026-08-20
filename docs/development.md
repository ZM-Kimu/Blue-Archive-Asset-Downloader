# Development Notes

This document keeps only the project rules needed for day-to-day maintenance.

## Environment

- Python 3.11+
- `uv`
- .NET 10 SDK
- Initialized Git submodules

```bash
uv sync --group dev --extra api
```

## Checks

Run focused tests while editing, then run the full gate before handing off broad changes.

```bash
./scripts/run-tests.ps1 -Suite smoke
./scripts/run-tests.ps1 -Suite extraction
./scripts/run-tests.ps1 -Suite all
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run lint-imports
git diff --check
```

The available focused suites are `application`, `runtime`, `extraction`, `regions`, and
`api`. They are local development shortcuts only. CI runs the complete core suite on
Python 3.11, 3.12, and 3.13. Static quality gates and the actual AssetRipper exporter
.NET build run once on Python 3.13.

The AssetRipper integration build is opt-in locally:

```powershell
$env:BAAD_RUN_DOTNET_BUILD = "1"
uv run pytest -q tests/test_assetripper_dotnet.py
```

Use `scripts/run-preflight.ps1` when a single local gate is more convenient.

## Architecture

- CLI and HTTP API adapters translate input directly into typed application commands.
- `ExecutionScope` is the only application executor: it dispatches one typed command to
  one use case, owns the operation-scoped service graph, and closes its resources after
  execution.
- Operation-only values such as concurrency, resource selection, and filters stay on the
  typed command instead of being copied into `ExecutionContext`.
- Application use cases own workflows and depend on domain ports.
- Region gateways own catalog providers, runtime preparation, dump backend selection, table routing, character index sources, and catalog metadata policy.
- Shared extraction code must stay region-neutral and consume profile-provided strategies.
- CN metadata recovery stays in `infrastructure.tools.cn_metadata_recovery` as a reusable engine; the CN region backend only orchestrates it.
- Cpp2IL exporter generation is shared, but region-specific shims must be injected by the requesting region backend.

## Boundaries

- Do not make shared extraction import concrete CN/GL/JP region modules.
- Do not put region-specific route names, schema names, or command hints in shared engines.
- Do not add numeric LOC or branching budgets. Keep code readable by ownership, not by mechanical splitting.
- Internal Python import paths and `.state` manifest schemas may change; CLI commands, HTTP contracts, and published output paths need deliberate migration notes.

## Runtime and Schema State

- Runtime snapshots record release, source/tool identity, verified artifact size/hash, and provenance. Missing or incompatible provenance invalidates the snapshot.
- Schema snapshots use separate `full` and `character-index` purpose namespaces. The character-index purpose generates only the three JP target types and their transitive FlatBuffer dependencies; it does not publish MemoryPack formatters or replace the canonical full schema.
- Generated Python is validated with in-memory `compile()` and must not publish `.pyc` files.
- Published artifacts use staging, complete validation, fsync where applicable, and atomic replacement. A failed operation must preserve the previous valid artifact.
- Streaming SHA-256, atomic JSON writes, and rollback-safe staging-directory publication
  live in `infrastructure.files`; manifests retain their own schemas and validation rules.

## JP Character Index

`index build` always reads the required tables and fully recomposes `characters.json`; the existing index is never a build shortcut. Warm operations may reuse lower-level state only after release, source, and tool fingerprints match.

- Package preparation selects the base APK, Unity data asset pack, and ARM64 split instead of unpacking every XAPK entry.
- The encrypted runtime is discovered by ELF64 little-endian AArch64 structure, internal `libappsign4a.so`, one bounded `libil2cpp.so` directory entry, and a v1 `MFTL` footer exactly 44 bytes before EOF. Damaged near-candidates and multiple valid candidates are errors; there is no plaintext fallback.
- RSA material scanning, AES-CBC decryption, and raw LZMA decompression stream into a staged ELF. Runtime manifests record `jp_mftl_v1` provenance rather than retaining the encrypted parent container.
- Index builds probe catalog roots semantically and request only TableCatalog. The table metadata manifest is replaced only after one valid ExcelDB source is identified.
- The SQLCipher plaintext cache is content-addressed by region, platform, release, resource identity, exporter version, and non-plaintext key ID. The three required tables share one read-only SQLite session and any blob decode failure aborts the build.

## AssetRipper

AssetRipper source is pinned as a submodule. The fallback archive is verified before use. Overlay manifests validate both upstream source SHA-256 and replacement SHA-256; `.gitattributes` forces every overlay C# file to LF because replacement hashes are byte-sensitive on Windows.

The patched source and exporter build are shared at
`<workspace>/.ba-downloader/tools`, keyed by the AssetRipper commit, overlay, and wrapper
fingerprints. They are not copied once per region or platform. The wheel source under
`src/ba_downloader/infrastructure/extraction/assetripper/tool` is the only exporter
wrapper source; repository builds and tests must reference it directly.

Bundle planning scans Unity entries, deduplicates historical content by SHA-256, groups serialized/resource dependencies into strongly connected components and transitive closures, and targets 500 MiB batches. Shared dependencies may appear in multiple batches; an indivisible oversized closure runs separately with a warning.

Missing dependencies or scan failures skip only affected components and their dependents. Independent batches continue after a failure. If at least one batch succeeds, usable output is atomically published; if all batches fail, the old output remains. Manifest schema 7 records source fingerprints, scans, batch outcomes, conflicts, skips, and `complete`. Conflicting contents are retained under `_baad_conflicts/<sha256>/<original-path>`.

## Outputs

Schema workflows produce:

- `<workspace>/<region>/<platform>/extracted/dumps/dump.cs`
- `<workspace>/<region>/<platform>/extracted/dumps/memorypack_formatters.json`

Character index workflows produce:

- `<workspace>/<region>/<platform>/indexes/characters.json`

Table extraction writes JSON under `<workspace>/<region>/<platform>/extracted/tables/` according to the active region profile.

## Compatibility Notes

Breaking internal refactors are acceptable when they simplify ownership. Public CLI changes must update `--help`, `README.md`, and `docs/README.en.md`, and the migration risk must be called out in the change summary. AssetRipper overlay changes additionally require an actual .NET exporter build and manifest hash verification.
