# Third-Party Notices

## AssetRipper

Bundle extraction uses AssetRipper 2.0.0 at commit
`1ac666f47d8e9dedf96afb0b914c70d7656151ea`.

- Project: <https://github.com/AssetRipper/AssetRipper>
- License: GNU General Public License v3.0
- License text: [licenses/AssetRipper-GPL-3.0.txt](licenses/AssetRipper-GPL-3.0.txt)

BAAD uses the pinned `third_party/AssetRipper` submodule when available. If it
is unavailable, BAAD downloads and caches the same pinned source archive.
The exporter is built locally; AssetRipper
source and binaries are not included in the BAAD Python wheel.

## Cpp2IL

IL2CPP metadata and schema preparation uses Cpp2IL at commit
`cae273a255d317f334ad8d71f457848645635d83`.

- Project: <https://github.com/SamboyCoding/Cpp2IL>
- License: MIT
- License text: [licenses/Cpp2IL-MIT.txt](licenses/Cpp2IL-MIT.txt)

BAAD uses the pinned `third_party/Cpp2IL` submodule when available. If it is
unavailable, BAAD downloads and caches the same pinned source archive. The dump
exporter is built locally; Cpp2IL source and
binaries are not included in the BAAD Python wheel.

## SharpZipLib

JP media archive extraction uses SharpZipLib 1.4.2.

- Project: <https://github.com/icsharpcode/SharpZipLib>
- License: MIT
- License text: [licenses/SharpZipLib-MIT.txt](licenses/SharpZipLib-MIT.txt)

BAAD uses the pinned `third_party/SharpZipLib` submodule when available. If it is
unavailable, BAAD downloads and caches the source archive for the same commit. A local bridge
project compiles those sources directly with the .NET 10 SDK; the media dependency
closure contains no NuGet `PackageReference`. SharpZipLib source and binaries are not
included in the BAAD Python wheel.

The media extractor does not reference AssetRipper or SharpCompress and independently
rejects unsafe ZIP paths before writing files.
