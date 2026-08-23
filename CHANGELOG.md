# Changelog

## v3.0.0 - Unreleased

### Breaking Changes
- replace the legacy flat CLI with `assets sync`, `assets download`,
  `assets extract`, `index build`, and `server start`
- remove short options, custom raw/extracted/temp paths, prefixed output
  directories, and legacy `<REGION>CharacterIndex.json` discovery
- isolate output under `<workspace>/<region>/<platform>` and model operations,
  progress, cancellation, artifacts, and region gateways with immutable typed
  contracts
- replace UnityPy bundle extraction with a pinned AssetRipper exporter and
  validated source overlays
- publish versioned runtime and schema snapshots; incompatible internal caches
  are discarded instead of migrated
- publish bundle content with human-readable AssetRipper paths under
  `extracted/bundles/Assets` and a compact identity manifest; schema 9 output
  is not migrated
- replace API-specific AssetRipper loading and processing fields with the
  unified `completed`, `total`, `stage`, `unit`, `status`, and
  `secondary_status` progress contract

### Features
- add typed resource and character filters with AND/OR composition
- add versioned character indexes and full per-invocation index rebuilding
- add the optional local HTTP API with immutable contexts, single-worker FIFO
  jobs, SSE events, catalog and CharacterIndex queries, bounded file access,
  and protected storage cleanup
- add deterministic AssetRipper dependency scanning, native numeric path
  conflict suffixes, and transactional bundle directory publication

### Performance
- discover JP encrypted IL2CPP containers by validated MFTL structure rather
  than package filenames and stream their decryption and decompression
- cache verified JP runtime inspection, minimal character-index schema, and
  content-addressed SQLCipher exports by release and tool identity
- request only TableCatalog for JP index builds and read the three required
  ExcelDB tables through one SQLite session
- avoid retaining downloaded JP packages and encrypted parent containers after
  successful runtime publication
- materialize bundle entry-cache misses through one parallel .NET operation,
  stream stable dependency groups through one persistent AssetRipper process,
  release each group before loading the next, and export collections in parallel
- replace linear sibling scans with indexed collection and streamed-resource
  resolution, and load independent cached bundle payloads concurrently
- restrict bundle output to PNG textures and sprites, audio, fonts, text,
  mesh GLB, scene GLB, and prefab GLB while avoiding generic JSON processing
- reserve deterministic human-readable paths before parallel export and return
  file hashes directly from .NET so Python does not enumerate and re-hash cold
  output

### Fixes
- merge scenario aliases into existing character records so names such as
  `プラナ` remain searchable
- keep non-character game entities in the index while stably ordering entries
  with names or file aliases first
- reject damaged or ambiguous MFTL containers, incomplete TableCatalog data,
  partial table decoding, and invalid staged indexes without replacing the last
  valid output
- validate HTTP status and response shapes while probing JP catalog roots
- normalize AssetRipper C# overlays to LF so manifest hashes remain stable on
  Windows
- remove bundle memory preflight and multi-worker scheduling, preserve catalog
  checksum identities, and report real loading/processor/asset stage progress
  on the single extraction task
- publish bundle manifest schema 10 once per run with exact output inventory,
  filtered accumulation, three-phase directory rollback, and no per-asset
  revision or batch checkpoint data
- serialize shared AssetRipper source/tool publication across processes and
  translate expected lock, capacity, scanner, build, and protocol failures into
  user-level extraction errors

### Internal Changes
- require Python 3.11 or later and replace advisory pylint checks with Ruff
  formatting, Ruff linting, mypy, and import-linter gates
- lazily load generated schema types and keep character-index schema generation
  separate from the canonical full-schema workspace
- preserve third-party attribution and license metadata in source and wheel
  distributions

### Security
- document that the local API intentionally uses plaintext HTTP, has no
  authentication, allows every Origin, and must run only on trusted networks


## v2.3.0 - 2026-07-30

### Breaking Changes
- remove `--version` / `-v`; all regions now resolve the currently available
  release automatically

### Features
- modernize the GL runtime and encrypted table extraction flow

### Fixes
- isolate CN, GL, and JP runtime assets in validated version snapshots
- exclude computed properties without backing fields from MemoryPack layouts
- decode APKPure release responses as protobuf wire data
- support the latest JP encrypted runtime payload name


## v2.2.1 - 2026-07-18

### Fixes
- update metadata recovery and character index sources


## v2.2.0 - 2026-07-09

### Features
- enable CN advanced search and JP SQLCipher key fallback
- enable CharacterIndex-backed filtered extraction
- support encrypted runtime and CharacterIndex data

### Fixes
- address validation failures
- retry truncated Cpp2IL fallback archive

### Refactors
- consolidate region profiles and character index
- consolidate profile-owned workflows
- migrate metadata recovery backend
- split jp profile from legacy paths
- reduce workflow coupling
- compose table source for CharacterIndex data
- move region workflow rules into policies
- remove unused internal helpers

### Documentation
- align search and CharacterIndex command docs

### Tests
- consolidate shared fixtures

### Other Changes
- Merge pull request #11 from ZM-Kimu/fix/cpp2il-fallback-archive-retry


## v2.1.0 - 2026-05-26

### Features
- stabilize schema and extraction pipeline
- preserve GL raw payload exports

### Fixes
- resolve default remote fallback
- route worker logs through parent

### Refactors
- reduce redundant schema infrastructure
- reorganize project boundaries
- reduce infrastructure complexity

### Chores
- sync readme docs and ci submodules
- require net10 tooling
- upgrade project dependencies
- switch to main-only release workflow

### Other Changes
- Merge pull request #9 from ZM-Kimu/refactor/reduce-complexity
- Merge pull request #8 from ZM-Kimu/feat/gl-runtime-and-relation-flow
- Merge pull request #7 from ZM-Kimu/feat/gl-runtime-and-relation-flow


## v2.0.0 - 2026-04-10

### Release
- Published v2.0.0.
