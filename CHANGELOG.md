# Changelog

## Unreleased

### Breaking Changes
- remove `--version` / `-v`; all regions now resolve the currently available
  release automatically

### Fixes
- isolate CN, GL, and JP runtime assets in validated version snapshots
- exclude computed properties without backing fields from MemoryPack layouts
- decode APKPure release responses as protobuf wire data


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
