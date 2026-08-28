<div align="center">

# Blue Archive Asset Downloader

This project downloads and extracts Blue Archive assets from different servers. It currently supports the China, Global, and Japan servers.

<a href="../README.md">中文</a>

</div>


## Resource Types

Downloadable file types include:

- Bundle
- Media
- Table

Extractable file types include:

- Bundle
- Media
- Table

## Requirements

- Windows/Linux
- [Python UV environment manager](https://github.com/astral-sh/uv) or Python 3.11 and later
- [.NET 10 SDK](https://dotnet.microsoft.com/download)

## Prerequisites

When running from source, cloning with submodules is recommended:

```shell
git clone --recurse-submodules https://github.com/ZM-Kimu/Blue-Archive-Asset-Downloader
cd Blue-Archive-Asset-Downloader
uv sync
```

- If the Cpp2IL, AssetRipper, or SharpZipLib submodule is missing locally, the corresponding workflow will attempt to download and verify its source archive.

Make sure Python is installed, then install the required libraries:

```shell
uv sync
# Or:
pip install -e .
```

The optional UnityPy backend is recommended for Bundle extraction on low-memory systems:

```shell
uv sync --extra unitypy
# Or:
pip install -e ".[unitypy]"
```

## Usage

The command structure is:

```shell
ba-downloader <subcommand> [options]
```

Subcommands:

- `ba-downloader assets sync [options]`: Download and extract content
- `ba-downloader assets download [options]`: Download content only
- `ba-downloader assets extract [options]`: Extract downloaded content
- `ba-downloader index build [options]`: Build the character information index
- `ba-downloader server start [options]`: Start the local HTTP API

Run the complete download and extraction workflow with:

```shell
ba-downloader assets sync --region jp
```

Or download resources without extracting them:

```shell
ba-downloader assets download --region jp
```

You can also use the module entry point:

```shell
python -m ba_downloader assets sync --region jp
```


## HTTP API

```shell
uv sync --extra api
ba-downloader server start --host 127.0.0.1
```

See the [HTTP API documentation](http-api.md) for the detailed protocol.

## **Basic Parameters**

| Parameter            | Commands                  | Description                                      | Default                                         | Example                         |
| -------------------- | ------------------------- | ------------------------------------------------ | ----------------------------------------------- | ------------------------------- |
| **`--region`**       | `assets *`, `index build` | **Server region**: `cn`, `gl`, or `jp`           | None                                            | `--region jp`                   |
| `--workspace`        | `assets *`, `index build` | Workspace root                                   | Current directory                               | `--workspace D:\BAAD`           |
| `--platform`         | `assets *`, `index build` | `windows`, `android`, or `ios` (JP only)         | `android`                                       | `--platform windows`            |
| `--proxy`            | `assets *`, `index build` | HTTP proxy URL                                   | None                                            | `--proxy http://127.0.0.1:8080` |
| `--max-retries`      | `assets *`, `index build` | Maximum retries after a request failure          | `5`                                             | `--max-retries 3`               |
| `--sqlcipher-key`    | `assets *`, `index build` | SQLCipher raw ![key](kei_icon.png)               | (mysterious)                                    | `--sqlcipher-key <64hex>`       |
| `--concurrency`      | `assets *`, `index build` | Concurrent worker count                          | `30`                                            | `--concurrency 50`              |
| `--resources`        | `assets *`                | Comma-separated `table`, `media`, and `bundle`   | All                                             | `--resources table,media`       |
| `--bundle-handler`   | `assets sync/extract`     | Bundle extractor: `assetripper` or `unitypy`     | `assetripper`                                   | `--bundle-handler unitypy`      |
| `--filter`           | `assets *`                | Resource or character filter; may be repeated    | None                                            | `--filter "name~伊吹"`          |
| `--host`             | `server start`            | HTTP API bind address                            | `0.0.0.0`                                       | `--host 127.0.0.1`              |
| `--port`             | `server start`            | HTTP API port                                    | First available port from `9230` through `9239` | `--port 9230`                   |

The CLI supports only the long options listed above. Run a specific command with `--help` to see the exact parameters supported by the installed version.

`--filter` uses `<field><operator><candidate>`. `~` performs case-insensitive containment matching, while `=` performs case-insensitive exact matching. Repeated `--filter` options use AND; comma-separated candidates within one filter use OR. `character-id`, `age`, and `height` support only `=` with non-negative integers.

When filters are used, dependencies between Bundles are not processed. Therefore, only the key assets for the selected characters are extracted.

Available fields include:

- `path` **Resource path**
- `type` **Resource type**
- `character-id` **Character ID**
- `name` **Character name**
- `dev-name` **Developer name**
- `alias` **File alias**
- `cv` **Voice actor**
- `age` **Age**
- `height` **Height**
- `birthday` **Birthday**
- `illustrator` **Illustrator**
- `school` **School**
- `club` **Club**

---

#### Each server supports its own character names and file aliases. See `indexes/characters.json` for the exact contents.

- Examples:
  > japan
  >```sh
  >ba-downloader assets sync --region jp --filter "name~arona,プラナ,生徒会長"
  >```

  > japan with conditions (both conditions must match)
  >```sh
  >ba-downloader assets sync --region jp --filter "school=Trinity" --filter "height=151"
  >```

  > global
  >```sh
  >ba-downloader assets sync --region gl --filter "name~貝雅特里榭,ยูเมะ,mika"
  >```

  > china
  >```sh
  >ba-downloader assets sync --region cn --filter "name~伊吹,心奈,切里诺"
  >```

- Resource path search:
  > package name only
  >```sh
  >ba-downloader assets sync --region jp --filter "path~aris,ch0070,shiroko"
  >```


## Default Output

`--workspace` defaults to the current directory. Output is always stored under `<workspace>/<region>/<platform>/`:

- `raw/{tables,media,bundles}`: Files downloaded through the Catalog.
- `extracted`: Extracted Bundles, Media, Tables, schemas, and dumps.
- `indexes/characters.json`: Character information index, which can be fully generated with `ba-downloader index build --region <region>`.
- `.state`: Temporary internal runtime data, caches, temporary files, logs, and manifests.

Resource platform example:

```shell
ba-downloader assets download --region jp --platform windows
```

## Notes

- JP/GL APK files come from APKPure. After the Play Store is updated, APKPure may need some time to synchronize the version.
- Resource catalogs may be unavailable while a server is under maintenance.
- Some regions may require a proxy server to download resources from specific game servers.
- Because the various interfaces change frequently, directly calling internal methods is not recommended.
- Reserve `50GB` of free storage for a full `asset sync` in any region.
- When extracting Bundles with AssetRipper, the host should have at least 8GB of RAM and at least 12GB of pagefile/swap. AssetRipper mode provides more complete asset structures and models with embedded animations.

## TODO

- `v3.1.0`
  - WebUI

## About

Blue Archive Asset Downloader v3.0.0

✨ Technical support: Codex ✨

Technical acknowledgments:

- [KitanoSakurana](https://github.com/KitanoSakurana)

Some content is based on:

- [Blue-Archive---Asset-Downloader](https://github.com/K0lb3/Blue-Archive---Asset-Downloader)
- [Cpp2IL](https://github.com/SamboyCoding/Cpp2IL)

This project uses the following C# dependencies:

- [AssetRipper](https://github.com/AssetRipper/AssetRipper)
- [Cpp2IL](https://github.com/SamboyCoding/Cpp2IL)
- [SharpZipLib](https://github.com/icsharpcode/SharpZipLib)

This project is licensed under the [MIT License](../LICENSE).

## Disclaimer

This repository is intended solely for learning and demonstration and does not host any actual resources. All content downloaded through this project must be used only for lawful and legitimate purposes. The developers accept no liability for any direct or indirect loss, damage, legal liability, or other consequences arising from use of this project. Users assume all risks associated with its use and must ensure compliance with all applicable laws and regulations. The developers accept no responsibility if this project is used for any unauthorized or illegal activity. Users are responsible for their own actions and should understand the risks associated with using this project.

This project is intended solely for educational and demonstrative purposes and does not provide any actual resources. Please note that all content downloaded through this project should only be used for legal and legitimate purposes. The developers are not liable for any direct or indirect loss, damage, legal liability, or other consequences that may arise from the use of this project. Users assume all risks associated with the use of this project and must ensure compliance with all relevant laws and regulations. If anyone uses this project for any unauthorized or illegal activities, the developers bear no responsibility. Users are responsible for their own actions and should understand the risks involved in using this project.

“蔚蓝档案”是上海星啸网络科技有限公司的注册商标，版权所有。

「ブルーアーカイブ」は株式会社Yostarの登録商標です。著作権はすべて保有されています。

"Blue Archive" is a registered trademark of NEXON Korea Corp. & NEXON GAMES Co., Ltd. All rights reserved.
