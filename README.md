# Blue Archive Asset Downloader 

<div align="center">
本项目可以从不同服务器下载并提取碧蓝档案的素材，现支援中国服、国际服、日本服。</div>


## 主要功能

- **多服务器支持**：可从中国(蔚蓝档案)、国际(Blue Archive)、日本(ブルーアーカイブ)三个服务器下载素材。
- **资源解开**：在日本服务器中包含几乎完整的支持。
- **JP 阶段成果**：当前 `download --region jp`、`sync --region jp`、`relation build --region jp` 已可用；`--advanced-search` 仍未开放。


## 资源类型

下载的文件类型包括：

- Bundle
- Media
- Table

提取的文件类型包括：

- Bundle(仅JP)
- Media
- Table(仅JP)

#### **注意**：尽管部分区域支持下载不同版本的资源，但是该程序不保证能够提取过时版本的资源文件。

## 环境要求

- Windows/Linux
- Python 3.10 或更高版本
- [.NET8/.NET9 SDK](https://dotnet.microsoft.com/download)(提取table或使用高级检索时必须安装；新 dumper backend 优先使用 .NET9) 

## 先决条件

请确保已安装 Python，并安装必要的库：

```shell
uv sync
```

或者：

```shell
pip install -e .
```

## 使用说明
使用下列命令运行完整下载与提取流程（示例）：

```shell
ba-downloader sync --region gl
```

或者，使用以下命令仅下载资源而不进行提取（示例）：

```shell
ba-downloader download --region jp
```

也可以使用模块入口：

```shell
python -m ba_downloader sync --region jp
```


## **基本参数**
**`*`** :**必选的选项**
| 参数                       | 缩&nbsp;写 | 说明                                                                      | 默认值             | 示例                          |
| -------------------------- | ---------- | ------------------------------------------------------------------------- | ------------------ | ----------------------------- |
| **`--region`**`*`          | `-r`       | **服务器区域**：`cn`（中国）、`gl`（国际）、`jp`（日本）                  | 无                 | `-r jp`                       |
| `--threads`                | `-t`       | **同时下载或解压的线程数**                                                | `20`               | `-t 50`                       |
| `--version`                | `-v`       | **需要下载的资源的版本号**（主要用于国际服务器）                          | 无                 | `-v 1.2.3`                    |
| `--platform`               | `-p`       | **JP bundle 平台**：`windows`、`android`、`ios`（仅 JP 生效）             | `android`          | `-p windows`                  |
| `--raw-dir`                | `-rd`      | **指定未处理文件的位置**                                                  | `"RawData"`        | `-rd raw_folder`              |
| `--extract-dir`            | `-ed`      | **指定已提取文件的位置**                                                  | `"Extracted"`      | `-ed output_folder`           |
| `--temp-dir`               | `-td`      | **指定临时文件的位置**                                                    | `"Temp"`           | `-td temp_dir`                |
| `--extract-while-download` | `-ewd`     | **是否在下载时便提取文件**（⚠较慢，在资源数量多于500时请勿使用）          | `False`            | `--extract-while-download`    |
| `--resource-type`          | `-rt`      | **资源类型**：`table`、`media`、`bundle`、`all`                           | `all`              | `--resource-type media table` |
| `--proxy`                  | `-px`      | **设置 HTTP 代理**                                                        | 无（使用系统代理） | `-px http://127.0.0.1:8080`   |
| `--max-retries`            | `-mr`      | **下载失败时的最大重试次数**                                              | `5`                | `--max-retries 3`             |
| `--search`                 | `-s`       | **普通检索**，指定需要检索并下载的文件关键词（`sync` 与 `download` 可用） |
| `--advanced-search`        | `-as`      | **高级检索**，指定角色关键词（仅 `sync` 命令可用，需要.NET8环境）         |

**(CN服务器目前不支持高级检索)高级检索支持的检索条件：**
- `[*]` **角色名称**
- `cv` **声优**
- `age` **年龄**
- `height` **身高**
- `birthday` **生日**
- `illustrator` **作画者**
- `school` **所属学园**（包括但不限于）：
  - `RedWinter`、`Trinity`、`Gehenna`、`Abydos`、`Millennium`、`Arius`
  - `Shanhaijing`、`Valkyrie`、`WildHunt`、`SRT`、`SCHALE`、`ETC`
  - `Tokiwadai`、`Sakugawa`
- `club` **所属社团**（包括但不限于）：
  - `Engineer`、`CleanNClearing`、`KnightsHospitaller`、`IndeGEHENNA`
  - `IndeMILLENNIUM`、`IndeHyakkiyako`、`IndeShanhaijing`、`IndeTrinity`
  - `FoodService`、`Countermeasure`、`BookClub`、`MatsuriOffice` ...

---
#### 并且，在不同的服务器中亦支持不同的名称检索方式，具体内容请参照`CharacterRelation.json`。
- 示例：
  > sync
  >```sh
  >ba-downloader sync --region gl -as 貝雅特里榭 ยูเมะ ibuki
  >```

  <!--
  > japan
  >```sh
  >ba-downloader sync --region jp -as yume 百合園セイア 호시노 cv=小倉唯 height=153 birthday=2/19 illustrator=YutokaMizu school=Arius club=GameDev
  >```
  -->

  > package name only
  >```sh
  >ba-downloader sync --region jp -s aris ch0070 shiroko
  >```


## 输出
- `Temp`: 存储临时文件或非主要文件。如：Apk文件等。
- `RawData`: 存储经由Catalog下载的文件。如：Bundle、Media、Table等。
- `Extracted`: 存储已提取的文件。如：Bundle、Media、Table与Dumps等。
- `CharacterRelation.json`: 角色信息，可通过 `ba-downloader relation build --region <region>` 生成。

JP 默认目录会按平台隔离：
- `--platform android`: `JP_Android_RawData` / `JP_Android_Extracted` / `JP_Android_Temp`
- `--platform windows`: `JP_Windows_RawData` / `JP_Windows_Extracted` / `JP_Windows_Temp`
- `--platform ios`: `JP_iOS_RawData` / `JP_iOS_Extracted` / `JP_iOS_Temp`

示例：

```shell
ba-downloader download --region jp --platform windows
python -m ba_downloader extract --region jp --platform ios
```


## 使用须知
- 当前 dumper backend 策略为：
  - `jp`：默认使用 `cpp2il_custom` backend（后端失败不回退到 legacy dumper）
  - `gl` / `cn`：保持使用 legacy `Il2CppDumper` backend
- 如果以源码方式运行并希望固定 Cpp2IL 依赖，请使用子模块：
  - `git clone --recurse-submodules <repo-url>`
  - `git submodule update --init --recursive`
- `pip` 安装场景下若缺失 `third_party/Cpp2IL`，程序会自动下载固定 commit 的 Cpp2IL 源码到本地工具缓存（`./.ba-downloader/tools/`）。
- `--platform` 仅对 JP 生效，用于切换 JP bundle 路径：
  - `windows -> Windows_PatchPack`
  - `android -> Android_PatchPack`
  - `ios -> iOS_PatchPack`
  - 在 `cn/gl` 上显式传入时只会提示已忽略。
- 下载阶段默认使用自适应并发调节（AIMD），会在 `timeout`、`403/429` 或连接异常后自动下调并发；默认下载空闲超时为 `600s`。
- JP的APK文件来自于APKPure，在PlayStore已经更新后，APKPure可能需要一些时间来同步版本。
- 当各服务器处于维护时间时，可能会无法获取资源目录。
- 在某些地区可能需要使用代理服务器以下载特定服务器的游戏资源。
- Bundle文件的提取基于UnityPy，如希望更加详细的内容请使用[AssetRipper](https://github.com/AssetRipper/AssetRipper)或[AssetStudio](https://github.com/Perfare/AssetStudio)
- JP 当前支持 `download --region jp`、`sync --region jp`、`relation build --region jp`；JP `--advanced-search` 仍暂不可用。

## 开发与发布
- 本地可使用交互式发版脚本准备版本号、README 与 `CHANGELOG.md`：

```shell
powershell -ExecutionPolicy Bypass -File scripts/release.ps1
```

- 当前流程为：
  - 在 `dev` 上准备版本与 changelog
  - 手动创建 `dev -> main` 的 pull request
  - 合并到 `main` 后，由 GitHub Actions 自动创建 tag 与 GitHub Release

- 仅预演流程而不写入文件：

```shell
powershell -ExecutionPolicy Bypass -File scripts/release.ps1 -NonInteractive -DryRun -SkipPreflight -SkipCommit -AllowDirtyWorkingTree
```

<!--
## TODO
- `v1.0`
  - **完善CN/GL** - 43%

- **Memory Pack** - 30%
-->

## 关于项目
Blue Archive Asset Downloader v2.0.0.

✨ 技术支持：Codex ✨

本项目采用 [MIT 许可证](LICENSE)。

部分内容参照自：
- [Blue-Archive---Asset-Downloader](https://github.com/K0lb3/Blue-Archive---Asset-Downloader)
- [Cpp2IL](https://github.com/SamboyCoding/Cpp2IL)

## 免责声明 / Disclaimer
该仓库仅供学习和展示用途，不托管任何实际资源。请注意，所有通过本项目下载的内容均应仅用于合法和正当的目的。开发者不对任何人因使用本项目而可能引发的直接或间接的损失、损害、法律责任或其他后果承担任何责任。用户在使用本项目时需自行承担风险，并确保遵守所有相关法律法规。如果有人使用本项目从事任何未经授权或非法的活动，开发者对此不承担任何责任。用户应对自身的行为负责，并了解使用本项目可能带来的任何风险。
This project is intended solely for educational and demonstrative purposes and does not provide any actual resources. Please note that all content downloaded through this project should only be used for legal and legitimate purposes. The developers are not liable for any direct or indirect loss, damage, legal liability, or other consequences that may arise from the use of this project. Users assume all risks associated with the use of this project and must ensure compliance with all relevant laws and regulations. If anyone uses this project for any unauthorized or illegal activities, the developers bear no responsibility. Users are responsible for their own actions and should understand the risks involved in using this project.

“蔚蓝档案”是上海星啸网络科技有限公司的注册商标，版权所有。
「ブルーアーカイブ」は株式会社Yostarの登録商標です。著作権はすべて保有されています。
"Blue Archive" is a registered trademark of NEXON Korea Corp. & NEXON GAMES Co., Ltd. All rights reserved.
