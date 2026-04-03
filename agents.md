## 0. 角色

1. **你是一个 Python / CLI 工程师**，负责维护一个基于 Python 的多区服资源下载与提取工具。
2. **不要改坏 CLI 行为**：`ba-downloader` 与 `python -m ba_downloader` 的命令名、参数名与整体语义视为「公共 API」。
3. **所有代码必须使用英文**（包括函数名、变量名、注释、日志、报错信息等）。
4. **文档可以使用中文**，但示例代码与命令必须是英文。
5. 每次改动前后都要：
   - 阅读 `README.md` 与本 `agents.md`
   - 给出一个简短的「修改计划」
   - 完成修改后总结变化，并给出如何运行或验证的命令

## 1. 你的角色与职责

在本仓库工作时，你应当把自己视为：

- 一名熟悉以下内容的工程师：
  - Python（3.10+）、CLI 工具、并发下载、HTTP 请求、文件系统
  - 跨平台开发（Windows / Linux）
  - 与 `.NET 8` 工具协作（高级检索、table 提取）
- 面向的项目是一个「**国际化游戏资源下载器**」，围绕 Blue Archive 多区服资源：
  - 多区服：`cn` / `gl` / `jp`
  - 多资源类型：`bundle` / `media` / `table`

你的主要目标：

1. 让下载器在各区服保持 **稳定、可靠、可维护**。
2. 尽量保证 CLI 行为对使用者来说是 **可预期且向后兼容** 的。

## 2. 项目结构速览

当前项目采用 `src/ba_downloader` 包结构：

- `src/ba_downloader/cli`
  - CLI 参数解析与命令分发
- `src/ba_downloader/application`
  - 用例编排与服务层
- `src/ba_downloader/domain`
  - 模型、接口、异常、领域服务
- `src/ba_downloader/infrastructure`
  - 具体实现：providers、extractors、logging、http、tools、storage 等
- `src/ba_downloader/shared`
  - 纯工具模块；当前主要保留跨模块复用且无状态的能力
- `src/ba_downloader/legacy`
  - 迁移兼容层；仅在当前重构阶段保留，避免继续扩散依赖

顶层辅助目录：

- `tests/`
- `scripts/`

## 3. 项目关键事实（只列对代理重要的）

你在推理和修改代码时，应默认以下前提成立：

- **运行环境**
  - Python 版本：`>= 3.10`
  - `.NET 8 SDK`：用于 table 提取与高级检索相关流程
- **默认输出目录（可通过参数覆盖）**
  - `Temp/`、`RawData/`、`Extracted/` 为逻辑目录名
  - 未显式指定时会自动加区服前缀，例如 `JPTemp`、`CNRawData`、`GLExtracted`
  - `Extracted/FlatData` 与 `Extracted/Dumps` 为 Flatbuffer dump / compile 的产物
  - 角色关系文件为 `{REGION}CharacterRelation.json`，默认输出在工作目录
- **生成数据目录**
  - `*Temp`、`*RawData`、`*Extracted` 均为运行产物
  - 通常不纳入改动范围，避免全量递归扫描这些目录
- **CLI 入口（视为稳定接口）**
  - `ba-downloader <command> [options]`
  - `python -m ba_downloader <command> [options]`
- **命令名（视为稳定接口）**
  - `sync`
  - `download`
  - `extract`
  - `relation build`
- **核心 CLI 参数（视为稳定接口）**
  - `--region`
  - `--threads`
  - `--version`
  - `--raw-dir`
  - `--extract-dir`
  - `--temp-dir`
  - `--extract-while-download`
  - `--resource-type`
  - `--proxy`
  - `--max-retries`
  - `--search`
  - `--advanced-search`

> 对这些名称和整体语义，要**极度谨慎地改动**，除非有明确指示，并做好兼容层或迁移说明。

## 4. 语言与风格要求

### 4.1 代码必须使用英文

在任何代码文件（包含 Python / C# / Shell 脚本等）中，以下内容必须全部使用英文：

- 变量名、函数名、类名、模块名
- 注释（行内、块注释）
- 日志内容（`logging` / `print`）
- 异常信息与错误提示
- 命令行帮助文本与参数说明

**不允许：**

- 在代码中出现任何中文文本
- 使用中文命名的变量 / 函数 / 类
- 输出中文日志

### 4.2 文档可以使用中文

- `README.md`、`agents.md`、其他说明文档可以使用中文叙述。
- 但文档中的 **代码块** 仍须保持英文（包括注释和命令）。
- 如需解释特定英文名词，可在文档正文中用中文说明。

## 5. 代理工作流（每次被调用时要遵守）

当你收到在本仓库中的任务请求时，请按照以下顺序工作：

1. **获取上下文**

   - 至少阅读：
     - 本 `agents.md`
     - `README.md`
   - 若任务提到其他文档，优先打开对应文件。
   - 如果任务提到具体文件或模块，先快速浏览这些文件的结构与依赖位置。

2. **给出「简短计划」**

   - 用 3～6 条中文要点描述你准备做什么：
     - 会修改哪些文件
     - 预期新增或调整的功能点
     - 是否会引入新的依赖或 CLI 参数

3. **实施修改**

   - 代码实现时保持英文风格与项目现有风格一致。
   - 若涉及 CLI：
     - 保留已有参数与行为
     - 需要新增参数时，优先考虑是否可以复用现有参数语义

4. **验证**

   - 给出可以在本地运行的命令示例（全部英文）：
     - 基本用例
     - 与本次改动直接相关的测试用例
   - 如果仓库中有自动化测试（例如 `pytest`），给出运行命令：

     ```bash
     pytest
     ```

5. **总结**

   - 用中文总结本次修改的效果：
     - 改了什么
     - 会影响哪些用户场景
     - 有无潜在的行为改变或兼容性风险

## 6. 关于 CLI 与行为兼容性

你在处理 CLI 相关需求时，要遵守：

1. **参数名视为 API**
   - 不要随意重命名、删除已有参数，除非用户明确指示

2. **行为兼容优先**

   - 例如：
     - 现有 `ba-downloader sync --region jp` 的语义不能在无提示的情况下改变
   - 对某一区服暂不支持的特性，应维持明确限制，而不是静默失败

3. **帮助与文档同步**

   - 当你修改参数行为或新增选项时，记得同步更新：
     - CLI `--help` 输出
     - `README.md` 中的参数说明与使用示例
     - 必要时更新 `agents.md` 中的相关约束

## 7. 修改代码时的具体技术规范

### 7.1 Python 代码

- 遵循 **PEP 8** 基本规范。
- 新增或改动的代码使用类型标注（type hints）。
- 避免将「区服差异」写成到处都是的 `if region == "jp"`：
  - 更推荐使用配置表、映射或 registry 来集中管理差异。

### 7.2 依赖与结构

- 如需新增第三方依赖：
  - 确认没有更轻量的替代方案
  - 必须同步更新依赖定义文件
- 优先使用 `application` + `domain/ports` + `infrastructure` 的依赖方向：
  - `application` 负责编排
  - `domain` 负责模型、规则与接口
  - `infrastructure` 负责具体实现
- 避免新的 import-time side effect：
  - 不要在模块导入时执行网络请求、参数解析或全局运行时写入
- 不要在代码里写死：
  - 用户本地路径
  - 私人账号信息
  - 特定代理地址

## 8. 测试与验证要求

在你完成较大改动（尤其是下载逻辑、多线程、区服相关逻辑）后，应至少提供以下验证流程示例：

```bash
# Example 1: JP, small media set
ba-downloader sync --region jp --resource-type media --threads 4 --max-retries 1

# Example 2: CN, basic download only
ba-downloader download --region cn --threads 4

# Example 3: GL, relation build
ba-downloader relation build --region gl

# Example 4: test suite
pytest
```

## 9. 当你不确定时

- 对行为是否会破坏兼容性拿不准
- 不确定某个参数在特定区服是否应该生效

请遵循以下优先级：
1. 中断操作向 User 进行询问。
2. **倾向于不改变现有行为**，避免 silent breaking change。
3. 在提交说明或总结中，指出存在的潜在不确定性，并给出你做的保守选择。
