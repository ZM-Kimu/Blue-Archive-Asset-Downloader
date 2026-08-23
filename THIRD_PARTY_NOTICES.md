# Third-Party Notices

## AssetRipper

Bundle extraction uses AssetRipper 1.3.14 at commit
`7534ed93857d1ef4464bab6e3c7a13777529f94d`.

- Project: <https://github.com/AssetRipper/AssetRipper>
- License: GNU General Public License v3.0
- License text: [licenses/AssetRipper-GPL-3.0.txt](licenses/AssetRipper-GPL-3.0.txt)

BAAD uses the pinned `third_party/AssetRipper` submodule when available. If it
is unavailable, BAAD downloads the same pinned source archive, verifies its
SHA-256, and caches it locally. The exporter is built locally; AssetRipper
source and binaries are not included in the BAAD Python wheel.

AssetRipper 1.3.14 currently resolves SharpCompress 0.47.4, which is covered by
security advisory GHSA-6c8g-7p36-r338. This upstream dependency must be reviewed
before a v3 release.

## SharpZipLib

JP media archive extraction uses SharpZipLib 1.4.2.

- Project: <https://github.com/icsharpcode/SharpZipLib>
- License: MIT
- License text: [licenses/SharpZipLib-MIT.txt](licenses/SharpZipLib-MIT.txt)

BAAD uses the pinned `third_party/SharpZipLib` submodule when available. If it is
unavailable, BAAD downloads the source archive for the same commit, verifies both
the archive and production source-tree SHA-256, and caches it locally. A local bridge
project compiles those sources directly with the .NET 10 SDK; the media dependency
closure contains no NuGet `PackageReference`. SharpZipLib source and binaries are not
included in the BAAD Python wheel.

The media extractor does not reference AssetRipper or SharpCompress and independently
rejects unsafe ZIP paths before writing files.
