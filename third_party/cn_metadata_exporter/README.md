# CN Metadata Exporter

`cn_metadata_exporter` is the C# exporter for the protected CN metadata format used in this workspace.

It is intentionally structured as a standalone tool:

- `Cpp2IL` is referenced as a clean dependency
- CN-specific restore and parsing logic live here
- the tool accepts either raw protected `global-metadata.dat` or an already restored metadata buffer

## Purpose

The exporter performs explicit phases:

1. Detect protected metadata
2. Restore it into a parseable metadata buffer
3. Parse the CN custom metadata layout
4. Build resolved export artifacts
5. Emit a reference-style `dump.cs` text description

Semantic recovery currently includes:

- readable modifiers
- optional private-member filtering by category
- optional reference-style method address placeholder comments
- common BCL and Unity type names
- backing-field to property linkage
- metadata-driven nested/interface/vtable section parsing
- interface and inheritance resolution
- delegate, closure, and state-machine annotations
- hotspot fixes for URL/root/path string arrays in business types
- stage timing diagnostics for restore/parse/build/emit

## Project Layout

```text
cn_metadata_exporter/
  Cli/
    Program.cs
    ExportOptions.cs
    ExportProfiler.cs
  Application/
    ResolvedExportArtifactBuilder.cs
  Indexing/
    TypeDescriptorIndex.cs
    TypeDescriptorIndexBuilder.cs
    TypeNameLookup.cs
    TypeIndexBuilder.cs
    RelationshipIndexBuilder.cs
    MemberIndexBuilder.cs
  Exporting/
    DumpExporter.cs
    DumpExporter.Writers.cs
  Metadata/
    MetadataLayout.cs
    MetadataReader.cs
    MetadataRestorer.cs
  Models/
    MetadataModels.cs
    ResolutionModels.cs
    ResolvedExportModels.cs
  Resolution/
    MemberResolver.cs
    RelationshipResolver.cs
    ResolutionConstants.cs
    ResolutionUtilities.cs
    TypeResolver.cs
  README.md
  cn_metadata_exporter.csproj
```

Responsibilities:

- `Cli/`: process entry and argument parsing
- `Application/`: export orchestration over parsed metadata and resolved indexes
- `Metadata/`: protected-buffer restore and metadata layout decoding
- `Indexing/`: one-time cold-path descriptor and artifact builders
- `Resolution/`: type-name recovery, relationship resolution, and member-signature reconstruction
- `Exporting/`: formatting-only `dump.cs` emission over resolved models
- `Models/`: shared in-memory structures

## Build

```powershell
dotnet build cn_metadata_exporter\cn_metadata_exporter.csproj -c Release
```

## Run

```powershell
dotnet run --project cn_metadata_exporter\cn_metadata_exporter.csproj -c Release -- `
  --metadata "path\to\your\global-metadata.dat" `
  --output "path\to\your\cn_dump_cs_from_csharp_full.cs" `
  --profile
```

Persist the restored metadata buffer:

```powershell
dotnet run --project cn_metadata_exporter\cn_metadata_exporter.csproj -c Release -- `
  --metadata "path\to\your\global-metadata.dat" `
  --restored-output "path\to\your\tmp_cn_restored_from_csharp.dat" `
  --output "path\to\your\cn_dump_cs_from_csharp_full.cs"
```

Show help:

```powershell
dotnet run --project cn_metadata_exporter\cn_metadata_exporter.csproj -c Release -- --help
```

Export a subset:

```powershell
dotnet run --project cn_metadata_exporter\cn_metadata_exporter.csproj -c Release -- `
  --metadata "path\to\your\global-metadata.dat" `
  --image "BlueArchive.dll" `
  --type-filter "ServerInfo" `
  --private-members none
```

Emit reference-shaped placeholder method addresses:

```powershell
dotnet run --project cn_metadata_exporter\cn_metadata_exporter.csproj -c Release -- `
  --metadata "path\to\your\global-metadata.dat" `
  --output "path\to\your\cn_dump_with_placeholders.cs" `
  --method-address-placeholders
```

## CLI Options

- `--metadata`
- `--output`
- `--image`
- `--type-filter`
- `--private-members`
- `--method-address-placeholders`
- `--restored-output`
- `--key-constant`
- `--profile`

## Design Notes

- This project prefers sample-derived recovery over cross-version reference assumptions.
- Clean `Cpp2IL` is used as a dependency, not as the owner of CN-specific behavior.
- The exporter is organized around explicit phases: restore, parse, build resolved artifact, emit.
- The project intentionally avoids a persistent cache layer to keep the runtime path and maintenance model simple.
- `--private-members` only controls members whose resolved accessibility is exactly `private`; it does not hide `internal`, `protected`, or `public` members.
- `--method-address-placeholders` only affects method metadata comment formatting. It emits `RVA/Offset/VA` placeholders and does not imply real binary-derived addresses.
- Raw custom metadata section knowledge stays in `Metadata/`; `Exporting/` should not reach into raw layout details.
- The parser now builds a typed section inventory from `0x18..0xB8` and promotes high-value type-system sections into explicit models before resolution runs.

## Current Boundaries

- Some private business types still fall back to `Type_0x...`
- Complex generic signatures are only partially recovered
- Some collection/delegate signatures still rely on resolver heuristics because binary-side type info is intentionally out of scope
- The exporter targets analyst readability, not byte-identical `Il2CppDumper` output
