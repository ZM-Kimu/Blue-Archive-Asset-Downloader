<div align="center">

# Blue Archive Asset Downloader

This project downloads and extracts Blue Archive assets from different servers. It currently supports CN, GL, and JP.

<a href="../README.md">中文</a>

</div>


## Resource Types

Downloadable file types:

- Bundle
- Media
- Table

Extractable file types:

- Bundle
- Media
- Table

## Requirements

- Windows/Linux
- Python UV environment manager or Python 3.10 and later
- [.NET10 SDK (for extracting table data)](https://dotnet.microsoft.com/download)

## Prerequisites

When running from source, use a clone flow with submodules:

```shell
git clone --recurse-submodules https://github.com/ZM-Kimu/Blue-Archive-Asset-Downloader
cd Blue-Archive-Asset-Downloader
uv sync
```

- If `third_party/Cpp2IL` is missing locally, some dumper flows will try to download the source automatically.

Make sure Python is installed, then install the required libraries:

```shell
uv sync
```

Or:

```shell
pip install -e .
```

## Usage

The command structure is:

```shell
ba-downloader <subcommand> [options]
```

Subcommands:

- `ba-downloader sync [options]`: Download and extract all content
- `ba-downloader download [options]`: Download all content
- `ba-downloader extract [options]`: Extract downloaded content
- `ba-downloader character-index build [options]`: Build the character information index

Run the full download and extraction flow with:

```shell
ba-downloader sync --region jp
```

Or download resources without extracting them:

```shell
ba-downloader download --region jp
```

You can also use the module entry point:

```shell
python -m ba_downloader sync --region jp
```


## **Basic Parameters**

**`*`**: **required option**

| Parameter                  | Short Form | Description                                                                                       | Default             | Example                       |
| -------------------------- | ---------- | ------------------------------------------------------------------------------------------------- | ------------------- | ----------------------------- |
| **`--region`**`*`          | `-r`       | **Server region**: `cn` (China), `gl` (Global), `jp` (Japan)                                      | None                | `-r jp`                       |
| `--threads`                | `-t`       | **Number of concurrent download or extraction workers**                                           | `20`                | `-t 50`                       |
| `--platform`               | `-p`       | **Resource platform**: `windows`, `android`, `ios` (JP only)                                      | `android`           | `-p windows`                  |
| `--raw-dir`                | `-rd`      | **Location for raw files**                                                                        | `"RawData"`         | `-rd raw_folder`              |
| `--extract-dir`            | `-ed`      | **Location for extracted files**                                                                  | `"Extracted"`       | `-ed output_folder`           |
| `--temp-dir`               | `-td`      | **Location for temporary files**                                                                  | `"Temp"`            | `-td temp_dir`                |
| `--extract-while-download` | `-ewd`     | **Extract files while downloading** (only available for `sync`; slower and should be used carefully with many resources) | `False`             | `--extract-while-download`    |
| `--resource-type`          | `-rt`      | **Resource type**: `table`, `media`, `bundle`, `all`                                              | `all`               | `--resource-type media table` |
| `--proxy`                  | `-px`      | **HTTP proxy**                                                                                    | None (system proxy) | `-px http://127.0.0.1:8080`   |
| `--max-retries`            | `-mr`      | **Maximum retry count for failed downloads**                                                      | `5`                 | `--max-retries 3`             |
| `--sqlcipher-key-hex`      | `-kei`     | **SQLCipher raw key**                                                                             | Unspecified         | `-kei <64hex>`                |
| `--search`                 | `-s`       | **Basic search**, file keywords for searching, downloading, or extracting (`sync`, `download`, and `extract` are supported) | None                | `-s aris shiroko`             |
| `--advanced-search`        | `-as`      | **Advanced search**, character information terms (requires a .NET environment)                    | None                | `-as yume cv=小倉唯`          |

`--search` and `--advanced-search` are mutually exclusive. Searches use Any matching. The concrete `school` and `club` enums can be checked in `FlatBufferData`.

Advanced-search fields:

- `[*]` **Character name**
- `cv` **Voice actor**
- `age` **Age**
- `height` **Height**
- `birthday` **Birthday**
- `illustrator` **Illustrator**
- `school` **School**:
  - `RedWinter`, `Trinity`, `Gehenna`, `Abydos`, `Millennium`, `Arius` ...
- `club` **Club**:
  - `Engineer`, `CleanNClearing`, `KnightsHospitaller`, `IndeGEHENNA`
  - `FoodService`, `Countermeasure`, `BookClub`, `MatsuriOffice` ...

---

#### Different servers support different name search forms. See `<Region>CharacterIndex.json` for details.

- Examples:
  > japan
  >```sh
  >ba-downloader sync --region jp -as yume 百合園セイア 호시노
  >```

  > japan with conditions (characters matching any condition)
  >```sh
  >ba-downloader sync --region jp -as cv=小倉唯 height=153 birthday=2/19 illustrator=YutokaMizu school=Arius club=GameDev
  >```

  > global
  >```sh
  >ba-downloader sync --region gl -as 貝雅特里榭 ยูเมะ mika
  >```

  > china
  >```sh
  >ba-downloader sync --region cn -as 伊吹 心奈 黑服
  >```

- Basic search:
  > package name only
  >```sh
  >ba-downloader sync --region jp -s aris ch0070 shiroko
  >```


## Default Output

- `Temp`: Stores temporary or non-primary files, such as APK files.
- `RawData`: Stores files downloaded from catalogs, such as Bundle, Media, and Table files.
- `Extracted`: Stores extracted files, such as Bundle, Media, Table, and Dumps files.
- `CharacterIndex.json`: Character information index. It can be generated with `ba-downloader character-index build --region <region>`, or generated automatically by adding `-as`.

Resource platform example:

```shell
ba-downloader download --region jp --platform windows
```


## Notes

- `--platform` only applies to JP and selects the JP resource platform.
- GL and JP APK files come from APKPure. After the Play Store updates, APKPure may need some time to synchronize the version.
- Resource catalogs may be unavailable during server maintenance windows.
- Some regions may require a proxy server to download game resources from specific servers.
- Bundle extraction is based on UnityPy. For more detailed results, use [AssetRipper](https://github.com/AssetRipper/AssetRipper) or [AssetStudio](https://github.com/Perfare/AssetStudio).
- Extraction methods change often, so interfaces may change frequently. Directly calling internal methods is not recommended.

## TODO

- `v3.0.0`
  - New Bundle extractor
  - Web API/Web UI

## About

Blue Archive Asset Downloader v2.3.0.

✨ Technical support: Codex ✨

Technical acknowledgments:

- [KitanoSakurana](https://github.com/KitanoSakurana)

Some content is based on:

- [Blue-Archive---Asset-Downloader](https://github.com/K0lb3/Blue-Archive---Asset-Downloader)
- [Cpp2IL](https://github.com/SamboyCoding/Cpp2IL)

This project uses the [MIT License](../LICENSE).

## Disclaimer

This repository is for learning and demonstration purposes only and does not host any actual resources. All content downloaded through this project should be used only for legal and legitimate purposes. The developers are not liable for any direct or indirect loss, damage, legal liability, or other consequence arising from use of this project. Users use this project at their own risk and must comply with all relevant laws and regulations. If anyone uses this project for unauthorized or illegal activities, the developers bear no responsibility. Users are responsible for their own actions and should understand the risks involved in using this project.

“蔚蓝档案” is a registered trademark of Shanghai Xingxiao Network Technology Co., Ltd. All rights reserved.

「ブルーアーカイブ」は株式会社Yostarの登録商標です。著作権はすべて保有されています。

"Blue Archive" is a registered trademark of NEXON Korea Corp. & NEXON GAMES Co., Ltd. All rights reserved.
