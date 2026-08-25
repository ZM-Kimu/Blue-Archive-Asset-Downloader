<div align="center">

# Blue Archive Asset Downloader 

本项目可以从不同服务器下载并提取碧蓝档案的素材，现支援中国服、国际服、日本服。

<a href="docs/README.en.md">English</a>

</div>


## 资源类型

下载的文件类型包括：

- Bundle
- Media
- Table

可提取的文件类型包括：

- Bundle
- Media
- Table

## 环境要求

- Windows/Linux
- [Python UV 环境管理器](https://github.com/astral-sh/uv) 或 Python 3.11 及更高版本
- [.NET 10 SDK](https://dotnet.microsoft.com/download)

## 先决条件

如果以源码方式运行，建议使用带 submodule 的 clone 流程：

```shell
git clone --recurse-submodules https://github.com/ZM-Kimu/Blue-Archive-Asset-Downloader
cd Blue-Archive-Asset-Downloader
uv sync
```

- 若本地缺失 Cpp2IL、AssetRipper 或 SharpZipLib submodule，相关流程会尝试下载并校验对应源码包。

请确保已安装 Python，并安装必要的库：

```shell
uv sync
```

或者：

```shell
pip install -e .
```

## 使用说明
命令结构如下：

```shell
ba-downloader <subcommand> [options]
```

子命令：

- `ba-downloader assets sync [options]`: 下载并解开内容
- `ba-downloader assets download [options]`: 仅下载内容
- `ba-downloader assets extract [options]`: 解开已下载的内容
- `ba-downloader index build [options]`: 构建角色信息索引
- `ba-downloader server start [options]`: 启动本地 HTTP API

使用下列命令运行完整下载与提取流程（示例）：

```shell
ba-downloader assets sync --region jp
```

或者，使用以下命令仅下载资源而不进行提取（示例）：

```shell
ba-downloader assets download --region jp
```

也可以使用模块入口：

```shell
python -m ba_downloader assets sync --region jp
```


## HTTP API

```shell
uv sync --extra api
ba-downloader server start --host 127.0.0.1
```

详细协议见 [HTTP API 文档](docs/http-api.md)。

## **基本参数**
**`*`** :**必选的选项**
| 参数              | 适用命令                  | 说明                                      | 默认值                          | 示例                            |
| ----------------- | ------------------------- | ----------------------------------------- | ------------------------------- | ------------------------------- |
| **`--region`**`*` | `assets *`、`index build` | **服务器区域**：`cn`、`gl`、`jp`          | 无                              | `--region jp`                   |
| `--workspace`     | `assets *`、`index build` | 工作区根目录                              | 当前目录                        | `--workspace D:\BAAD`           |
| `--platform`      | `assets *`、`index build` | `windows`、`android`、`ios`（仅 JP 生效） | `android`                       | `--platform windows`            |
| `--proxy`         | `assets *`、`index build` | HTTP 代理地址                             | 无                              | `--proxy http://127.0.0.1:8080` |
| `--max-retries`   | `assets *`、`index build` | 请求失败后的最大重试次数                  | `5`                             | `--max-retries 3`               |
| `--sqlcipher-key` | `assets *`、`index build` | SQLCipher raw ![key](docs/kei_icon.png)   | （神必）                        | `--sqlcipher-key <64hex>`       |
| `--concurrency`   | `assets *`、`index build` | 并发 worker 数                            | `30`                            | `--concurrency 50`              |
| `--resources`     | `assets *`                | 逗号分隔的 `table`、`media`、`bundle`     | 全部                            | `--resources table,media`       |
| `--filter`        | `assets *`                | 资源或角色过滤条件，可以重复              | 无                              | `--filter "name~伊吹"`          |
| `--host`          | `server start`            | HTTP API 监听地址                         | `0.0.0.0`                       | `--host 127.0.0.1`              |
| `--port`          | `server start`            | HTTP API 端口                             | `9230` 至 `9239` 中首个可用端口 | `--port 9230`                   |

CLI 仅支持以上长参数。运行具体命令并附加 `--help` 可查看当前安装版本的准确参数。

`--filter` 使用 `<字段><操作符><候选值>`：`~` 表示不区分大小写的包含匹配，`=` 表示不区分大小写的精确匹配。重复多个 `--filter` 使用 AND；同一 filter 内以逗号分隔的候选值使用 OR。`character-id`、`age` 与 `height` 只支持 `=` 和非负整数。

可用字段包括：
- `path` **资源路径**
- `type` **资源类型**
- `character-id` **角色 ID**
- `name` **角色名称**
- `dev-name` **开发名称**
- `alias` **文件别名**
- `cv` **声优**
- `age` **年龄**
- `height` **身高**
- `birthday` **生日**
- `illustrator` **作画者**
- `school` **所属学园**
- `club` **所属社团**

---
#### 不同服务器支持各自的角色名称与文件别名，具体内容请参照 `indexes/characters.json`。
- 示例：
  > japan
  >```sh
  >ba-downloader assets sync --region jp --filter "name~プラナ,生徒会長"
  >```

  > japan with conditions（两个条件必须同时满足）
  >```sh
  >ba-downloader assets sync --region jp --filter "school=Trinity" --filter "height=151"
  >```

  > global
  >```sh
  >ba-downloader assets sync --region gl --filter "name~貝雅特里榭,ยูเมะ,mika"
  >```

  > china
  >```sh
  >ba-downloader assets sync --region cn --filter "name~伊吹,心奈,黑服"
  >```

- 资源路径检索：
  > package name only
  >```sh
  >ba-downloader assets sync --region jp --filter "path~aris,ch0070,shiroko"
  >```


## 默认输出
`--workspace` 默认为当前目录，输出固定存放在 `<workspace>/<region>/<platform>/`：
- `raw/{tables,media,bundles}`: 存储经由 Catalog 下载的文件。
- `extracted`: 存储已提取的 Bundle、Media、Table、schema 与 dumps。
- `indexes/characters.json`: 角色信息索引，可通过 `ba-downloader index build --region <region>` 全量生成。
- `.state`: 临时内部运行时、缓存、临时文件、日志与 manifest。

资源平台示例：

```shell
ba-downloader assets download --region jp --platform windows
```

## 使用须知
- JP/GL的APK文件来自于APKPure，在PlayStore已经更新后，APKPure可能需要一些时间来同步版本。
- 当各服务器处于维护时间时，可能会无法获取资源目录。
- 在某些地区可能需要使用代理服务器以下载特定服务器的游戏资源。
- 由于各类接口频繁变动，不建议直接调用内部方法。
- 在进行全量 `asset sync` 时，各区服建议预留 `50GB` 的可用存储空间。

## TODO
- `v3.1.0`
  - WebUI
  
## 关于项目
Blue Archive Asset Downloader v3.0.0

✨ 技术支持：Codex ✨

技术协助鸣谢：
- [北野桜奈](https://github.com/KitanoSakurana)

部分内容参照自：
- [Blue-Archive---Asset-Downloader](https://github.com/K0lb3/Blue-Archive---Asset-Downloader)
- [Cpp2IL](https://github.com/SamboyCoding/Cpp2IL)

使用了以下 C# 依赖：
- [AssetRipper](https://github.com/AssetRipper/AssetRipper)
- [Cpp2IL](https://github.com/SamboyCoding/Cpp2IL)
- [SharpZipLib](https://github.com/icsharpcode/SharpZipLib)


本项目采用 [MIT 许可证](LICENSE)。

## 免责声明 / Disclaimer
该仓库仅供学习和展示用途，不托管任何实际资源。请注意，所有通过本项目下载的内容均应仅用于合法和正当的目的。开发者不对任何人因使用本项目而可能引发的直接或间接的损失、损害、法律责任或其他后果承担任何责任。用户在使用本项目时需自行承担风险，并确保遵守所有相关法律法规。如果本项目被用以从事任何未经授权或非法的活动，开发者对此不承担任何责任。用户应对自身的行为负责，并了解使用本项目可能带来的任何风险。

This project is intended solely for educational and demonstrative purposes and does not provide any actual resources. Please note that all content downloaded through this project should only be used for legal and legitimate purposes. The developers are not liable for any direct or indirect loss, damage, legal liability, or other consequences that may arise from the use of this project. Users assume all risks associated with the use of this project and must ensure compliance with all relevant laws and regulations. If anyone uses this project for any unauthorized or illegal activities, the developers bear no responsibility. Users are responsible for their own actions and should understand the risks involved in using this project.

“蔚蓝档案”是上海星啸网络科技有限公司的注册商标，版权所有。

「ブルーアーカイブ」は株式会社Yostarの登録商標です。著作権はすべて保有されています。

"Blue Archive" is a registered trademark of NEXON Korea Corp. & NEXON GAMES Co., Ltd. All rights reserved.
