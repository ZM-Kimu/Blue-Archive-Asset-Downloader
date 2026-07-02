# JP Profile Refactor Handoff

本文档面向接手 BAAD 后续重构工作的 AI 或维护者。它记录当前重构方向、已经收口的边界，以及下一步可以继续破坏性清理的区域。

## 当前目标

当前项目的架构主线应优先服务 **JP profile**。JP profile 覆盖 Windows/Android/iOS；其中 Android table 语义提取覆盖最完整，应作为当前验证基线：

1. catalog 解析得到资源、大小写敏感的 table includes metadata。
2. download 按 catalog 原始路径保存 raw asset。
3. schema/runtime preparation 负责 il2cpp dump、FlatBuffer、MemoryPack sidecar。
4. table extraction 按 JP profile 语义 handler 输出 JSON 或明确 raw fallback。
5. relation/search 以 JP `ExcelDB.db` 三表为 source of truth。

CN/GL CLI 对外入口仍保留，但内部应被视为 legacy profile。不要让 CN/GL 的历史兼容细节重新污染 JP 主链路。

## 已完成的边界

- `AssetExtractionWorkflow.extract_tables()` 不再支持通过 monkeypatch `TableExtractor` 走线程 fallback。
  - table extraction 统一进入 `ProcessTableExtractionRunner`。
  - 每个 table 文件在独立 worker 中创建自己的 `TableExtractor`。
  - 测试应验证 workflow 对 runner 的委托，而不是替换 production extractor。

- table payload routing 已按 region 分离。
  - JP: `JpTablePayloadRouter`
  - CN legacy: `CnLegacyTablePayloadRouter`
  - default/GL: `FlatBufferTablePayloadRouter`
  - JP 的 MemoryPack DB blob 不允许 CN partial decode fallback。

- table archive routing 已拆出 handler。
  - `TableArchiveRouter` 只做 route dispatch、metadata password mapping、warning aggregation。
  - `StandardZipArchiveExtractor` 处理普通 zip。
  - `GlLegacyArchiveExtractor` 处理 GL legacy ground/MGS 兼容。
  - JP nested/stage/raw 路径分别在 `nested_archives.py`、`memorypack_archives.py`、`raw_archives.py`。
  - `TableExtractionProfile` 负责为 JP 与 legacy 路径选择 archive registry、payload router、database resolver。

- JP table metadata manifest 不应写入 `.ba-downloader/catalog`。
  - 目标位置是 `context.temp_dir/catalog/jp/{platform}/{version}.table-metadata.json`。
  - 旧 `.ba-downloader/catalog` 缓存只忽略，不迁移、不读取。
  - JP table metadata 缺失且 catalog refresh 失败时直接报错，不再按 archive entry 名称降级兼容。

- JP relation composition 已改为 profile policy。
  - JP romanization 由 composition profile 开启。
  - CN costume/recruit enrichment 由 legacy enricher 注入。
  - composer 不再按 region 字符串分支。

- JP table profile 已显式拒绝 GL/MGS legacy archive route。
  - GL legacy classifier 仍保留旧行为。
  - JP 普通 standard zip/raw fallback 仍保留，但明确的 GL/MGS legacy 名称不会被当作 JP standard zip 处理。


## 下一步可继续清理的区域

### 1. Region workflow/profile

当前方向是让 use case 依赖 `RegionProfile`，而不是散落判断 `context.region`。

继续检查：

```powershell
rg -n "context\.region|region ==|region !=|RuntimeContext\(.*region" src/ba_downloader/application src/ba_downloader/infrastructure
```

目标：

- application use case 不直接知道 JP manifest、SQLCipher、runtime preparer 细节。
- JP profile 提供 schema preparation、table metadata policy、relation source loader、archive handler registry。
- CN/GL profile 只保留 smoke compatibility 所需能力。

### 2. Table extraction

当前 `TableArchiveRouter` 仍通过 `TableArchiveKind` 同时表达 JP 和 GL route。下一步可以进一步拆：

- JP archive registry：GroundGrid、GroundNodeLayer、GroundStage、ExcelDB、standard zip、raw fallback。
- GL legacy archive registry：GL ground/MGS/raw compatibility。
- classifier 不再让 JP registry 吃掉 GL/MGS legacy archive 名称。

扫描：

```powershell
rg -n "GL_|GroundGrid|GroundNodeLayer|GroundStage|MGSLogicGround|TableArchiveKind" src/ba_downloader/infrastructure/extraction/table
```

目标：

- JP handler 不经过 GL route enum。
- GL legacy handler 不引用 JP manifest password policy。
- raw fallback 只保存 payload，不混入语义 decode。

### 3. MemoryPack/schema

长期目标：JP MemoryPack 语义只来自 dump/generated sidecar facts。

继续检查：

```powershell
rg -n "hardcoded|fallback|partial|union|ShapeSpecification|formatter" src/ba_downloader/infrastructure/schema src/ba_downloader/infrastructure/extraction/table
```

目标：

- Python builder 只消费 dump sidecar、generated `MemoryPackData`、formatter facts。
- 字段顺序、继承、union tag、wire type 无法可靠生成时，formatter 标记 unavailable。
- extractor 对 unavailable formatter 明确 raw fallback，而不是生成伪语义 JSON。

### 4. Relation/search

JP relation source 应固定读：

- `ScenarioCharacterNameDBSchema`
- `CharacterDBSchema`
- `LocalizeCharProfileDBSchema`

CN legacy 才读 `Excel.zip` bytes。

继续检查：

```powershell
rg -n "Excel\\.zip|characterexceltable|localizecharprofile|ScenarioCharacterName|CharacterDBSchema|LocalizeCharProfile" src/ba_downloader/infrastructure/extraction/character tests
```

目标：

- `-s` / `-as` selection 不通过闭包隐藏 schema/relation preparation。

### 5. Tests

保留高价值测试：

- JP catalog/download/extract/relation/schema 主链路，至少覆盖 Android table semantic baseline。
- filtered `sync/extract -s/-as` 只处理命中资源。
- extraction 单项失败继续处理其他资源，最后汇总失败。
- CN/GL CLI smoke compatibility。

可删除或改写：

- 测 private helper 名称的测试。
- 通过 monkeypatch production class 触发旧路径的测试。
- 只为防止“写烂代码”而扫描源码字符串的测试。
- 与用户行为无关的文档一致性测试。

## 接手前必跑扫描

```powershell
git status --short
rg -n "_REAL_TABLE_EXTRACTOR|TableExtractor is|workflow\\.TableExtractor" src tests
rg -n "BA_JP_SQLCIPHER_KEY_HEX|jp_sqlcipher_license|jp_sqlcipher_library" src tests README.md docs
rg -n "\\.ba-downloader/catalog|table-metadata\\.json" src tests docs README.md
rg -n "allow_partial_memorypack" src tests
```

预期：

- 不应出现 `_REAL_TABLE_EXTRACTOR` 或 `workflow.TableExtractor` monkeypatch。
- 不应恢复 JP SQLCipher env var/license/library。
- `.ba-downloader/catalog` 不应作为 JP table manifest 读写位置。
- `allow_partial_memorypack=True` 只能属于 CN legacy path。

## 验证 gate

小范围 table/workflow 改动：

```powershell
uv run pytest tests/test_table_components.py tests/test_table_extractor.py tests/test_asset_workflow.py -q
uv run pytest tests/test_extract_service.py tests/test_sync_service.py tests/test_memorypack_codegen.py tests/test_dump_backend.py -q
```

最终 gate：

```powershell
uv run pytest
uv run black --check src tests
uv run ruff check src tests
uv run mypy
git diff --check
```

## 提交建议

优先小提交，按边界提交：

- `refactor(table): split jp and legacy archive handlers`
- `refactor(extract): remove table extraction compatibility branch`
- `refactor(schema): derive memorypack formatters from sidecar facts`
- `test(table): focus extraction tests on jp profile behavior`
- `docs: update jp profile refactor handoff`

不要把“行为修复”和“测试删减”和“文档同步”混成一个大提交，除非当前工作树已经无法拆分。
