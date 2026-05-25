# 开发与维护说明

本文档面向仓库维护者。

## 开发环境

- Python 3.10 或更高版本
- `.NET10 SDK`
- `uv`（推荐）

初始化开发环境：

```shell
uv sync --group dev
```

如需启用提交前检查：

```shell
uv run pre-commit install --hook-type pre-commit --hook-type pre-push
```

## 静态检查与预检

当前仓库使用以下工具：

- `ruff`
- `mypy`
- `pylint`
- `black`（通过 `pre-commit` 处理改动文件）

常用本地检查命令：

```shell
uv run ruff check .
uv run mypy
uv run pylint --rcfile .pylintrc src/ba_downloader scripts
powershell -ExecutionPolicy Bypass -File scripts/run-preflight.ps1
```

`scripts/run-preflight.ps1` 当前会执行：

- `python -m compileall src tests scripts`
- `uv run ruff check .`
- `uv run mypy`
- `uv run pylint --rcfile .pylintrc src/ba_downloader scripts`（advisory，不阻断）
- `uv run pytest -q`

## Dumper 与 Cpp2IL 说明

当前 dumper backend 策略：

- `jp`：默认使用 `cpp2il_custom`
- `gl`：默认使用 `cpp2il_custom`
- `cn`：内部使用 metadata-only `cn_metadata_exporter`

如果以源码方式运行并希望固定 Cpp2IL 依赖，请使用子模块：

```shell
git clone --recurse-submodules <repo-url>
git submodule update --init --recursive
```

`pip` 安装场景下如果缺失 `third_party/Cpp2IL`，程序会自动下载固定 commit 的 Cpp2IL 源码到本地工具缓存：

- `./.ba-downloader/tools/`

CN metadata backend 额外依赖仓库内 vendored 的独立 dumper 工程：

- `third_party/cn_metadata_exporter`

该工程当前以源码快照方式纳入仓库，依赖 `third_party/Cpp2IL/LibCpp2IL`，可单独验证：

```shell
dotnet build third_party/cn_metadata_exporter/cn_metadata_exporter.csproj -c Release
```

## FlatBuffer 与 MemoryPack schema 说明

`SchemaWorkflow.compile()` 会从 `dump.cs` 中生成两类运行时 schema：

- `FlatBufferData`：FlatBuffer descriptor-first schema registry。Table 解析直接加载 `_registry.py`，通过 generic reader/exporter 解码 payload；旧 `FlatData/dump_wrapper.py` 不再是运行时依赖，旧内部别名 `CSParser` / `CompileToPython` 已移除。
- `MemoryPackData`：实验性的 MemoryPack annotation schema。JP catalog decoder 在该 registry 可用时会优先使用 generic `MemoryPackReader`，registry 缺失或解码失败时回退到现有专用 decoder；该流程仍不影响 FlatBuffer table 解析主路径。

- FlatBuffer 输出目录：`<Extracted>/FlatBufferData`
- MemoryPack 输出目录：`<Extracted>/MemoryPackData`
- MemoryPack formatter sidecar：`<Extracted>/Dumps/memorypack_formatters.json`。该文件记录可追踪的 formatter 元数据；若 formatter 布局仍为 unresolved，DB BLOB 解码会保留 raw fallback，而不会假装语义解析成功。
- 产物形态：每个 MemoryPack 类型一个 dataclass module，字段使用 `typing.Annotated`
- 类型表达：`dump.cs` 中的 C# enum 会生成 Python `IntEnum`；可解析的 schema 引用会写成真实类型引用，例如 `dict[str, Media] | None`
- 循环引用：生成器会保留 annotation 中的类型名，并对循环 import 使用 `TYPE_CHECKING` fallback，确保生成模块可导入
- 当前用途：JP catalog MemoryPack payload 的优先解码路径，以及后续 MemoryPack payload inspect / typed JSON 导出的 schema 基础

FlatBuffer schema 生成失败会中断 compile；MemoryPack schema 生成失败只会记录 warning 并继续原有流程。

### Table payload 路由策略

当前 table payload 解包仍采用“已验证来源优先”的阶段性策略：

- 通用 `ExcelDB.db` 与 `.bytes` payload 继续走 `FlatBufferData` registry。
- CN 三类 DAO SQLite BLOB 使用 CN 专用 MemoryPack DAO 路由。
- GL script / boss / eliminateRaid / beatmap 等暂按已确认的 raw 导出或专用解析路径处理。

在各区服格式尚未全部可语义解包前，不做未验证的统一格式猜测。后续当 CN / GL / JP 的 table payload 语义覆盖足够完整时，再将这些来源特定规则收敛为统一 payload router，并以统一路由作为唯一入口。

## 架构边界与复杂度预算

当前仓库允许内部 Python API 进行 breaking change，但 CLI 命令、核心参数、默认输出目录默认保持稳定。较大的重构应先补架构或行为测试，再拆实现。

依赖方向原则：

- `bootstrap` 负责 CLI runtime 装配、region registry、runtime preparer registry；除 CLI 入口外，不应由业务模块反向依赖。
- `application.use_cases` 负责编排 use case，不承载格式解析细节。
- `domain` 只放稳定值对象、端口和无外部依赖的领域服务，例如 `domain.services.catalog_pipeline`。
- `download` 只负责下载、校验和下载进度，不直接依赖 table/media/bundle extractor。
- `infrastructure.extraction` 负责编排和格式导出，按 `bundle` / `media` / `table` / `character` 子包拆分。
- `infrastructure.packages` 负责 APK / XAPK / ZIP range IO，不承载区服 catalog 语义。
- `regions` 只负责区服 release/catalog 获取和 asset normalization；schema codec 与 Unity 读取细节不得放回 provider facade。
- `schema` 只负责 dump schema、generated registry 与 binary reader/exporter，不直接驱动下载或提取流程。

复杂度守门在 `tests/test_architecture_complexity.py` 中维护。默认不为历史热点保留 allowlist；如确需临时放行，必须在对应减熵阶段结束时同步收紧预算或移除放行项。

内部模块按职责拆分：

- CLI 装配：`ba_downloader.bootstrap`
- Use cases：`ba_downloader.application.use_cases`
- Region providers：`ba_downloader.infrastructure.regions.cn|gl|jp`
- Extraction：`ba_downloader.infrastructure.extraction`
- APK / XAPK / ZIP IO：`ba_downloader.infrastructure.packages`
- File checksum：`ba_downloader.infrastructure.files.checksum`
- FlatBuffer：`ba_downloader.infrastructure.schema.flatbuffer`
- MemoryPack：`ba_downloader.infrastructure.schema.memorypack`
- 共享能力：`ba_downloader.infrastructure.schema.common`
- dump / IL2CPP / runtime probe 等外部工具仍位于 `ba_downloader.infrastructure.tools`

旧的 schema 内部入口 `ba_downloader.infrastructure.tools.flatbuffer_*`、`ba_downloader.infrastructure.tools.memorypack_*`、`CSParser`、`CompileToPython`、`GeneratedDumpWrapperError` 均不再支持；内部调用请迁移到 `ba_downloader.infrastructure.schema.*`。

旧的内部路径不提供 shim，包括：

- `ba_downloader.application.services.*` -> `ba_downloader.application.use_cases.*`
- `ba_downloader.application.catalog_pipeline` -> `ba_downloader.domain.services.catalog_pipeline`
- `ba_downloader.infrastructure.regions.providers.*` -> `ba_downloader.infrastructure.regions.<region>.provider`
- `ba_downloader.infrastructure.extractors.*` / `ba_downloader.infrastructure.extract.*` -> `ba_downloader.infrastructure.extraction.*`
- `ba_downloader.infrastructure.apk.*` -> `ba_downloader.infrastructure.packages.*`
- 旧 `ba_downloader.shared` 命名空间已移除；checksum 放在 `ba_downloader.infrastructure.files.checksum`，schema/table crypto 放在对应 infrastructure 模块。

## GL 特殊 payload 备注

GL `Table/` 中的 `eliminateRaid` payload 当前已经支持 raw 导出，但尚未实现语义解析。专项分析记录见：

- `docs/gl-eliminate-raid.md`

## 分支与发版

当前仓库采用 `main-only` 流程：

- `main`：唯一长期分支
- `feature/*`、`fix/*`、`docs/*`、`chore/*`：日常短期开发分支
- `release/vX.Y.Z`：正式发版短期分支
- `hotfix/*`：已发布版本的紧急修复短期分支

### 日常开发流程

开始工作前先同步主线：

```shell
git checkout main
git pull --ff-only
```

从 `main` 拉出短期分支进行开发：

```shell
git checkout -b feat/example-change
```

提交前运行本地预检：

```shell
powershell -ExecutionPolicy Bypass -File scripts/run-preflight.ps1
```

推送短期分支并创建到 `main` 的真实 PR。普通开发 PR 统一使用 squash merge，并在合并后删除源分支。

仓库设置层面应保持：

- `main` 只允许通过 PR 合并
- CI 必须通过后才能合并
- direct push / force-push 默认为关闭，管理员仅在紧急救火时例外处理

### 正式发版流程

从最新 `main` 拉出 release 分支：

```shell
git checkout main
git pull --ff-only
git checkout -b release/v2.0.1
```

在 release 分支上运行发版脚本：

```shell
powershell -ExecutionPolicy Bypass -File scripts/release.ps1
```

仅预演流程而不写入文件：

```shell
powershell -ExecutionPolicy Bypass -File scripts/release.ps1 -NonInteractive -DryRun -SkipPreflight -SkipCommit -AllowDirtyWorkingTree
```

发版脚本会：

1. 更新 `pyproject.toml` 与 `README.md` 中的版本号。
2. 重新生成 `CHANGELOG.md` 的 `Unreleased` 区块。
3. 将当前 `Unreleased` 封版为 `vX.Y.Z - YYYY-MM-DD`，并重建空的 `Unreleased`。
4. 执行完整 preflight。
5. 创建 `chore(release): prepare vX.Y.Z` 提交。

完成后，推送 `release/vX.Y.Z` 并人工创建 `release/vX.Y.Z -> main` 的 PR。PR 合并到 `main` 后，GitHub Actions 会：

1. 读取 `pyproject.toml` 的版本号。
2. 自动创建 `vX.Y.Z` tag。
3. 使用 `CHANGELOG.md` 对应版本节作为 GitHub Release 正文。

release PR 合并后应删除 `release/vX.Y.Z` 分支。

### 热修复流程

已发布版本需要补丁时，从最新 `main` 拉出 `hotfix/*` 分支修复，修复后正常 PR 合并回 `main`。需要补丁发版时，再从更新后的 `main` 拉新的 `release/vX.Y.Z+1` 分支，重复正式发版流程。
