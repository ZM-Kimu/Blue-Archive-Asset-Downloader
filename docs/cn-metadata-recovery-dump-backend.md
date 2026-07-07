# CN Metadata Recovery Dump Backend

CN schema dumping uses the in-repo metadata recovery engine before invoking the shared Cpp2IL dump exporter.

## Runtime Flow

`sync`, `extract`, and `character-index build` with `--region cn` prepare:

- protected `global-metadata.dat`
- `lib/arm64-v8a/libil2cpp.so`
- optional `globalgamemanagers` for Unity version detection

The backend then:

1. recovers a standard v29 metadata image in memory;
2. validates it against the current binary;
3. writes only `<Temp>/CN_MetadataRecovery/global-metadata.standard-v29.dat`;
4. invokes the Cpp2IL dump exporter with the CN metadata recovery shim enabled.

Final BAAD-facing outputs remain:

- `<Extracted>/Dumps/dump.cs`
- `<Extracted>/Dumps/memorypack_formatters.json`

## Constraints

- The old CN metadata-only dumper is not supported.
- Production code must not depend on `G:\test_ba`.
- Recovery parameters such as hidden tail offset and metadata registration VA must be resolved from the current input, not hardcoded from a single sample.

## Suggested Checks

```bash
uv run pytest tests/test_cn_metadata_recovery_pipeline.py tests/test_dump_backend.py -q
uv run pytest
uv run black --check src tests
uv run ruff check src tests
uv run mypy
git diff --check
```
