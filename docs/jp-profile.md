# JP Profile Notes

JP is modeled as one `jp` region profile with platform-specific strategy for `windows`, `android`, and `ios`.

Android remains the strongest semantic table extraction baseline, but `jp_android` is not a separate region.

## Current Ownership

- JP catalog and platform release logic live under the JP region profile.
- JP table extraction owns JP patch pack, ExcelDB, standard zip, stale Excel warning, and raw fallback policy.
- Shared table extraction consumes the JP table profile and must not select JP behavior by checking `context.region`.
- JP character index sources read the JP ExcelDB-backed schemas needed for names, profile text, aliases, and metadata.

## Platform Notes

- `--platform windows`, `--platform android`, and `--platform ios` are JP-only public options.
- Default JP output directories include the platform name unless the user overrides paths.
- `--sqlcipher-key-hex, -kei` supplies the SQLCipher key when encrypted JP table databases require it.

## Table Coverage

- Android table semantic coverage is the most complete.
- Windows and iOS share the JP profile but may fall back to raw extraction for formats that are not semantically covered yet.
- Stale JP `Excel.zip` sources should emit stale-source warnings from the JP profile, not from shared extraction code.

## Suggested Checks

```bash
uv run pytest tests/test_jp_profile.py tests/test_jp_runtime_assets.py tests/test_jp_server.py -q
uv run pytest tests/test_table_components.py tests/test_table_extractor.py tests/test_character_index.py -q
uv run pytest
uv run black --check src tests
uv run ruff check src tests
uv run mypy
git diff --check
```
