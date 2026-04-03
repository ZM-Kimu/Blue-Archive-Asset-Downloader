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
- `uv run pylint --rcfile .pylintrc src/ba_downloader scripts`
- `uv run pytest -q`

## Dumper 与 Cpp2IL 说明

当前 dumper backend 策略：

- `jp`：默认使用 `cpp2il_custom`
- `gl` / `cn`：保持使用 legacy `Il2CppDumper`

如果以源码方式运行并希望固定 Cpp2IL 依赖，请使用子模块：

```shell
git clone --recurse-submodules <repo-url>
git submodule update --init --recursive
```

`pip` 安装场景下如果缺失 `third_party/Cpp2IL`，程序会自动下载固定 commit 的 Cpp2IL 源码到本地工具缓存：

- `./.ba-downloader/tools/`

## 分支与发版

当前分支策略：

- `dev`：开发分支
- `main`：发布分支
- `deprecated`：旧历史归档分支

本地可使用交互式发版脚本准备版本号、`README.md` 与 `CHANGELOG.md`：

```shell
powershell -ExecutionPolicy Bypass -File scripts/release.ps1
```

仅预演流程而不写入文件：

```shell
powershell -ExecutionPolicy Bypass -File scripts/release.ps1 -NonInteractive -DryRun -SkipPreflight -SkipCommit -AllowDirtyWorkingTree
```

当前发版流程：

1. 在 `dev` 上准备版本与 changelog。
2. 手动创建 `dev -> main` 的 pull request。
3. 合并到 `main` 后，由 GitHub Actions 自动创建 tag 与 GitHub Release。
