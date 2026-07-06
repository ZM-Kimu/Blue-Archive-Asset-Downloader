# CN metadata recovery dump backend 手动验证

本文记录 CN dump backend 迁移后的手动验证基线。生产代码不会硬编码样本 hash；该 hash 只作为当前已确认样本的回归参考。

## 自动流程

`ba-downloader sync/extract/relation build --region cn` 会自动：

1. 从 CN APK central directory 准备 `global-metadata.dat`、`lib/arm64-v8a/libil2cpp.so`，并尽量提取 `globalgamemanagers`。
2. 在内存中运行 vendored CN metadata recovery pipeline。
3. 只写出 final standard v29 metadata：`<Temp>/CN_MetadataRecovery/global-metadata.standard-v29.dat`。
4. 使用 Cpp2IL exporter 读取 final v29 metadata 与 `libil2cpp.so`。
5. 输出 `<Extracted>/Dumps/dump.cs` 与 `<Extracted>/Dumps/memorypack_formatters.json`。

CLI 参数、命令名和默认输出目录不变。

## 已确认样本

来源样本：

```text
G:\test_ba\ylda_2.1.2_24_20250924_063444_02a41
```

最终 metadata：

```text
G:\test_ba\artifacts\metadata\ylda_metadata_standard29_attrdata_candidate.dat
SHA256: 1B908500A3F6BC2D100225CEBA745F5282CC8FF362AF5DC518FE1B61E8C2297F
```

验证结果：

```text
0 errors / 0 warnings
```

Cpp2IL direct load 已确认：

```text
Using actual IL2CPP Metadata version 29
CN metadata recovery shim using auto-scanned(score=987, modules=0xA61E4B8) CodeRegistration at 0xAD5DEC8
Mapping pointers to Il2CppMethodDefinitions...Processed 223135 OK
Application model created
Done
```

## 本地 gate

高价值快速 gate：

```shell
uv run pytest tests/test_dump_backend.py tests/test_provider_results.py tests/test_zip_range_reader.py tests/test_cn_metadata_recovery_pipeline.py -q
```

完整 gate：

```shell
uv run pytest
uv run black --check src tests
uv run ruff check src tests
uv run mypy
git diff --check
```
