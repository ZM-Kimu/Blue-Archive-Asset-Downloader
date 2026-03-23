# 当前重构报告

## 1. 摘要

截至 2026-03-23，项目已经完成核心架构重构，主运行时链路已切换到 v2 分层结构：

- `cli`
- `application`
- `domain`
- `infrastructure`
- `shared`

当前状态属于“高质量过渡态”：

- 运行时代码已基本符合严格分层设计
- 旧运行时目录已不再被主链路引用
- 仓库内仍保留 `legacy/` 适配层与少量历史目录残留
- 因此，当前尚未达到“最终冻结、完全清理后的最佳实践终态”

## 2. 当前阶段

### Phase 1: 包化与 CLI 迁移

已完成

### Phase 2: 分层架构落地

已完成

### Phase 3: Runtime Context / Port 抽象显式化

已完成

### Phase 4: HTTP / 下载 / 日志 / 进度稳定化

已完成

### Phase 5: 新旧资源链路与 provider 适配收敛

进行中

### Phase 6: 物理目录清理、遗留目录删除、文档冻结

未完成

## 3. 当前是否达到最佳实践

### 已达到最佳实践的部分

- 运行时代码的主要依赖方向已明确
- `application` 负责用例编排
- `domain` 负责模型、端口、异常
- `infrastructure` 负责具体实现
- `shared` 仅保留纯工具能力
- HTTP、下载、日志、进度条、提取器、工具链已基本归位

### 尚未达到最佳实践终态的部分

- 仍存在 `legacy/` 兼容适配层
- 仓库中仍保留 `lib/`、`regions/` 等历史目录残留
- `shared/` 下仍有大量仅剩缓存的历史子目录
- `README.md` 与当前实现状态尚未完全同步
- 当前工作区仍处于活跃变更状态，尚未冻结

## 4. 各目录状态

| 路径 | 状态 | 说明 |
|---|---|---|
| `src/ba_downloader/cli` | 已完成 | v2 CLI 主入口 |
| `src/ba_downloader/application` | 基本完成 | 已有服务层与 catalog pipeline |
| `src/ba_downloader/domain` | 基本完成 | 端口、模型、异常已成型；仍存在 `resource` / `asset` 并存 |
| `src/ba_downloader/infrastructure` | 基本完成 | 主运行时实现已归位 |
| `src/ba_downloader/infrastructure/regions/providers` | 进行中 | 已迁移，但仍通过 `legacy.py` 适配旧链路 |
| `src/ba_downloader/infrastructure/download` | 已完成 | 新下载执行层 |
| `src/ba_downloader/infrastructure/http` | 已完成 | 新 HTTP client |
| `src/ba_downloader/infrastructure/logging` | 已完成 | logging runtime 与高亮器 |
| `src/ba_downloader/infrastructure/progress` | 已完成 | rich progress 层 |
| `src/ba_downloader/infrastructure/extractors` | 已完成 | 提取器已归位 |
| `src/ba_downloader/infrastructure/tools` | 已完成 | codegen / dump / probe 已迁移 |
| `src/ba_downloader/infrastructure/storage` | 已完成 | SQLite 读取已归位 |
| `src/ba_downloader/infrastructure/unity` | 已完成 | Unity 读取已归位 |
| `src/ba_downloader/legacy` | 临时保留 | 当前迁移过渡层，不是终态 |
| `src/ba_downloader/shared` | 待清理 | 当前真正活跃的主要是 `shared/crypto` |
| `src/ba_downloader/lib` | 应删除 | 只剩物理残留 |
| `src/ba_downloader/regions` | 应删除 | 只剩物理残留 |
| `tests` | 状态良好 | 已覆盖架构与核心链路 |

## 5. 当前技术判断

当前项目已经完成“架构重构”本身，但尚未完成“仓库收尾”。

更准确地说：

- 如果问题是“核心分层是否已经到位”，答案是“是”
- 如果问题是“仓库是否已经整理为最终最佳实践形态”，答案是“还没有”

## 6. 当前建议的下一步

1. 冻结并确认 `legacy/` 是否仍需继续存在
2. 清理 `lib/`、`regions/`、`shared/*` 中仅剩缓存的历史目录
3. 统一 `resource` 与 `asset` 的最终模型边界
4. 更新 `README.md`，让功能状态与当前实现一致
5. 在完成一轮真实 smoke test 后，再做一次结构冻结提交

## 7. 当前验证状态

已验证：

```bash
python -m compileall src/ba_downloader tests
uv run pytest -q
```

结果：

- `compileall` 通过
- `pytest` 通过：`37 passed`
