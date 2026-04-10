# 开发与维护说明

本文档面向仓库维护者，不面向普通使用者。

## 开发环境

- Python 3.10 或更高版本
- `.NET 8` 或 `.NET 9` SDK
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
- `gl`：保持使用 legacy `Il2CppDumper`
- `cn`：内部使用 metadata-only `cn_metadata_exporter` backend（当前尚未对用户开放）

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
