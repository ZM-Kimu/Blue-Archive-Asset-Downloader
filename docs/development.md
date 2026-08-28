# Development Notes

This document describes the current development workflow and the stable ownership
boundaries of the v3 codebase. Implementation details that are already expressed by
typed constants or tests should remain in code rather than being duplicated here.

## Environment

- Python 3.11, 3.12, or 3.13
- [uv](https://github.com/astral-sh/uv)
- .NET 10 SDK
- Git submodules for offline tool builds

```bash
git submodule update --init --recursive
uv sync --group dev --extra api
```

AssetRipper, Cpp2IL, and SharpZipLib prefer their checked-out submodules. A missing
submodule can be downloaded from its pinned upstream commit during normal execution.
UnityPy is optional and is installed only when its Bundle backend is needed:

```bash
uv sync --extra unitypy
```

## Validation

Use focused suites while editing and the complete gate before a release or broad
handoff:

```powershell
./scripts/run-tests.ps1 -Suite smoke
./scripts/run-tests.ps1 -Suite extraction
./scripts/run-tests.ps1 -Suite all
./scripts/run-preflight.ps1
```

The preflight runs compileall, Ruff formatting and linting, Mypy, Import Linter, and
the complete pytest suite. CI runs pytest on Python 3.11, 3.12, and 3.13 and runs the
static checks once on Python 3.13.

Real .NET integration builds are opt-in locally:

```powershell
$env:BAAD_RUN_DOTNET_BUILD = "1"
uv run pytest -q tests/test_assetripper_dotnet.py
uv run pytest -q tests/test_media_extractor_dotnet.py
```

## Architecture

- CLI and HTTP API adapters translate external input into typed application commands.
- `ExecutionScope` dispatches one command, owns its operation-scoped services, and
  closes those services after execution.
- Application use cases depend on domain models and ports, not infrastructure or
  transport adapters.
- Region gateways own region-specific catalogs, runtime preparation, schemas, table
  routing, and character-index sources.
- Shared extraction code remains region-neutral and consumes region-provided inputs.
- Infrastructure adapters own filesystems, processes, HTTP clients, caches, locks,
  progress rendering, and external tools.

The import rules in `.importlinter` enforce these boundaries. Do not move
region-specific identifiers or protocol knowledge into shared domain or application
modules.

## Internal State and Publication

Current internal manifests, caches, tool protocols, and progress payloads use
`schema_version` 0. They accept only their current structure; v2 workspaces and older
v3 development artifacts are not migrated implicitly.

Content-derived fingerprints identify generated tools, schemas, and exported Bundle
content. Source paths are normalized before hashing so equivalent Windows and Linux
checkouts produce the same identity. External dependency commits remain part of the
identity where their behavior affects a generated tool.

Region-specific runtime and extraction state lives below
`<workspace>/<region>/<platform>/.state`. Shared tool caches and interprocess locks
live below `<workspace>/.ba-downloader`. Cache publication uses unique staging
directories, validation, and atomic replacement. Failed or cancelled publication must
leave the previous public output intact.

## Progress

All workflows publish typed `ProgressState` values. The CLI renders one Rich task and
the API emits the same schema 0 state through the existing job/SSE envelope.

- `overall` is the trustworthy main unit used for the progress bar and ETA.
- `current` is local stage progress and does not affect the overall ETA.
- Bundle extraction uses completed dependency groups as its overall unit.
- Stage transitions do not reset elapsed time.
- Failed and cancelled terminal states retain the last trustworthy counters.

## JP Runtime and Character Index

`index build` fully recomposes `indexes/characters.json`; the existing index is not a
shortcut. Lower-level runtime, schema, table, and SQLCipher caches may be reused only
after their current identities validate.

JP package preparation selects the base APK, Unity data asset pack, and ARM64 split.
The MFTL runtime decoder locates the encrypted container structurally, accepts the
known equivalent MessagePack and footer variants, and streams RSA/AES/LZMA recovery
into a staged ELF. The TARA output length is authoritative for RAW LZMA streams that
omit an end marker. Ambiguous or damaged candidates remain errors.

Character-index preparation requests only the required catalog and schemas. The three
required tables share one read-only SQLite session, and a decode failure aborts the
index build rather than publishing partial character data.

## Bundle Extraction

`--bundle-handler assetripper` is the default. The AssetRipper workflow:

1. scans archive entries and builds the serialized/resource dependency graph;
2. materializes verified entry-cache payloads;
3. forms deterministic dependency-topology groups without splitting components;
4. starts one persistent .NET exporter and processes groups serially;
5. loads and exports within each group using the requested concurrency;
6. releases each group's `GameData` before starting the next group; and
7. validates and transactionally publishes one human-readable `Assets` tree and a
   schema 0 manifest.

The grouping target is defined in `assetripper/bundles.py` and is not a memory budget.
The workflow does not reject a run from a physical-memory estimate. On systems below
the recommended RAM level, the CLI warns that AssetRipper may fail and identifies
UnityPy as the reduced-output alternative.

The selective AssetRipper profile runs the six required processors in their declared
order. It exports the supported primary content, readable GLB hierarchy models, and
embedded transform, morph, and humanoid animation. Stable identity, provenance,
coverage, deterministic path allocation, content hashing, and collision checks are
preserved across groups.

AssetRipper source preparation validates the presence of required upstream projects,
then applies the schema 0 overlay in a locked staging directory. Overlay and tool
caches use content-derived fingerprints. The overlay does not rely on per-file
upstream or replacement SHA allowlists.

`--bundle-handler unitypy` is an optional low-memory backend. It processes archives
sequentially and exports a reduced primary set: Texture2D, Sprite, AudioClip, Font,
TextAsset, and individual Mesh OBJ files. It does not reproduce AssetRipper scene,
prefab, GLB, or animation semantics. Both backends use `extracted/bundles`, so a
successful handler change replaces incompatible output transactionally.

## Media Extraction

Media extraction uses one .NET 10 process and the pinned SharpZipLib source. Source
and cold-build preparation use cross-process locks and atomic caches; different
region/platform extraction contexts can otherwise run independently.

Python sends one schema 0 request for the selected archives. The C# tool performs
central-directory processing, output-path validation, concurrent extraction, size and
CRC verification, structured progress, and archive-level failure aggregation. Public
output is published from staging, while requests, results, and incomplete staging
data are removed after success, failure, or cancellation. Media output intentionally
has no warm extraction shortcut.

## Outputs

Public paths are owned by `WorkspaceLayout`:

- `raw/{tables,media,bundles}` for catalog downloads;
- `extracted/tables` for table output;
- `extracted/media` for media output;
- `extracted/bundles/Assets` and `extracted/bundles/manifest.json` for Bundle output;
- `extracted/schemas` and `extracted/dumps` for generated schemas and IL2CPP dumps;
- `indexes/characters.json` for the character index.

Public CLI changes must update `--help`, `README.md`, and `docs/README.en.md`.
Progress wire changes must update both CLI and API tests. AssetRipper or media tool
changes require their real .NET Release build before release.
