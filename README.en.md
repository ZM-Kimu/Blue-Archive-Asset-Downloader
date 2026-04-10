<div align="center">

# Blue Archive Asset Downloader

This project downloads and extracts Blue Archive assets from multiple regions. It currently supports the CN, GL, and JP servers.
</div>


## Features

- **Multi-region support**: Download assets from the China server (蔚蓝档案), Global server (Blue Archive), and Japan server (ブルーアーカイブ).
<!-- - **Asset extraction**: Nearly complete support is available for the JP server. -->
<!-- - **CN milestone status**: `download --region cn`, `sync --region cn`, and `relation build --region cn` are currently available; `--advanced-search` is still unavailable. -->
<!-- - **JP milestone status**: `download --region jp`, `sync --region jp`, and `relation build --region jp` are currently available; `--advanced-search` is still unavailable. -->


## Resource Types

The downloader supports these resource categories:

- Bundle
- Media
- Table

<!-- Extractable resource categories include:

- Bundle (JP only)
- Media
- Table (JP only) -->

#### **Note**: Although some regions support downloading different resource versions, this tool does not guarantee that outdated resource files can still be extracted.

## Requirements

- Windows/Linux
- Python 3.10 or later
<!-- - [.NET 8/.NET 9 SDK](https://dotnet.microsoft.com/download) (required for table extraction or advanced search; the new dumper backend prefers .NET 9) -->

## Prerequisites

Make sure Python is installed, then install the required dependencies:

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
python -m ba_downloader <subcommand> [options]
```

Subcommands:

<!-- - `ba-downloader sync [options]`: Download and extract everything -->
- `ba-downloader download [options]`: Download all resources
<!-- - `ba-downloader extract [options]`: Extract previously downloaded resources -->
<!-- - `ba-downloader relation build [options]`: Build the character relation file -->

Run the full download-and-extract workflow with:

```shell
ba-downloader sync --region gl
```

Or download resources only with:

```shell
ba-downloader download --region jp
```

You can also use the module entrypoint:

```shell
python -m ba_downloader sync --region jp
```


## **Basic Parameters**
**`*`** : **required option**

| Parameter                  | Short Form | Description                                                                    | Default            | Example                       |
| -------------------------- | ---------- | ------------------------------------------------------------------------------ | ------------------ | ----------------------------- |
| **`--region`**`*`          | `-r`       | **Server region**: `cn` (China), `gl` (Global), `jp` (Japan)                   | None               | `-r jp`                       |
| `--threads`                | `-t`       | **Number of concurrent download or extraction workers**                        | `20`               | `-t 50`                       |
| `--version`                | `-v`       | **Resource version to download** (currently effective for GL only)             | None               | `-v 1.2.3`                    |
| `--platform`               | `-p`       | **Resource platform**: `windows`, `android`, `ios` (effective for JP only)     | `android`          | `-p windows`                  |
| `--raw-dir`                | `-rd`      | **Directory for raw downloaded files**                                         | `"RawData"`        | `-rd raw_folder`              |
| `--extract-dir`            | `-ed`      | **Directory for extracted output**                                             | `"Extracted"`      | `-ed output_folder`           |
| `--temp-dir`               | `-td`      | **Directory for temporary files**                                              | `"Temp"`           | `-td temp_dir`                |
| `--extract-while-download` | `-ewd`     | **Extract files while downloading** (available only for `sync`; use carefully for large resource sets) | `False`            | `--extract-while-download`    |
| `--resource-type`          | `-rt`      | **Resource types**: `table`, `media`, `bundle`, `all`                          | `all`              | `--resource-type media table` |
| `--proxy`                  | `-px`      | **HTTP proxy**                                                                 | None (system proxy) | `-px http://127.0.0.1:8080`   |
| `--max-retries`            | `-mr`      | **Maximum retry count for failed downloads**                                   | `5`                | `--max-retries 3`             |
| `--search`                 | `-s`       | **Basic search**: keywords used to filter files for download (`sync` and `download` only) |
| `--advanced-search`        | `-as`      | **Advanced search**: character-oriented filters (`sync` only; currently supported by GL only and requires a .NET environment) |

**(Advanced search is currently unsupported on CN) Supported advanced-search fields:**
- `[*]` **Character name**
- `cv` **Voice actor**
- `age` **Age**
- `height` **Height**
- `birthday` **Birthday**
- `illustrator` **Illustrator**
- `school` **School** (including but not limited to):
  - `RedWinter`, `Trinity`, `Gehenna`, `Abydos`, `Millennium`, `Arius`
  - `Shanhaijing`, `Valkyrie`, `WildHunt`, `SRT`, `SCHALE`, `ETC`
  - `Tokiwadai`, `Sakugawa`
- `club` **Club** (including but not limited to):
  - `Engineer`, `CleanNClearing`, `KnightsHospitaller`, `IndeGEHENNA`
  - `IndeMILLENNIUM`, `IndeHyakkiyako`, `IndeShanhaijing`, `IndeTrinity`
  - `FoodService`, `Countermeasure`, `BookClub`, `MatsuriOffice` ...

---
#### Different regions also support different naming styles for search. See `<Region>CharacterRelation.json` for the actual data.
- Examples:
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


## Output

- `Temp`: Stores temporary files or non-primary files, such as APK packages.
- `RawData`: Stores files downloaded from catalogs, such as Bundle, Media, and Table files.
- `Extracted`: Stores extracted output, such as Bundle, Media, Table, and Dumps files.
<!-- - `CharacterRelation.json`: Character metadata; it can be generated with `ba-downloader relation build --region <region>`. -->

JP default directories are separated by platform:
- **Example:** `--platform android`: `JP_Android_RawData` / `JP_Android_Extracted` / `JP_Android_Temp`

Example:

```shell
ba-downloader download --region jp --platform windows
```


## Notes

- `--platform` applies only to JP and is used to select JP platform-specific resources:
  - It also affects the JP default output directory prefix, such as `JP_Windows_RawData`.
- JP APK files are currently sourced from APKPure. After the Play Store updates, APKPure may take some time to synchronize. Official PC package parsing may be added later.
- Resource catalogs may be unavailable during server maintenance windows.
- A proxy may be required in some regions to download assets from specific servers.
- Bundle extraction is based on UnityPy. If you need more detailed extraction results, use [AssetRipper](https://github.com/AssetRipper/AssetRipper) or [AssetStudio](https://github.com/Perfare/AssetStudio).
<!-- - JP currently supports `download --region jp`, `sync --region jp`, and `relation build --region jp`; JP `--advanced-search` is still unavailable. -->

## Maintenance

See [docs/development.md](docs/development.md) for development, static checks, dumper backend details, submodules, and release workflow notes.

## TODO

- `v2.0.1`
  - Improve the download workflow for all three regions (CN / GL / JP)
- `v2.0.2`
  - Improve JP extraction (a key is required, and that key is currently on the server side)
  - MemoryPack support based on a `dump.cs` annotation tree
  - CN metadata extraction
- `v2.0.3`
  - New bundle extractor

## About

Blue Archive Asset Downloader v2.0.0.

✨ Powered by Codex ✨

This project is licensed under the [MIT License](LICENSE).

Parts of this project reference:
- [Blue-Archive---Asset-Downloader](https://github.com/K0lb3/Blue-Archive---Asset-Downloader)
- [Cpp2IL](https://github.com/SamboyCoding/Cpp2IL)

## Disclaimer

This repository is provided for educational and demonstration purposes only and does not host any actual game assets. Please note that all content downloaded through this project should only be used for legal and legitimate purposes. The developers are not liable for any direct or indirect loss, damage, legal liability, or other consequences arising from use of this project. Users assume all risks associated with using this project and must ensure compliance with all applicable laws and regulations. If anyone uses this project for any unauthorized or illegal activity, the developers bear no responsibility. Users are responsible for their own actions and should understand the risks involved in using this project.

“蔚蓝档案”是上海星啸网络科技有限公司的注册商标，版权所有。

「ブルーアーカイブ」は株式会社Yostarの登録商標です。著作権はすべて保有されています。

"Blue Archive" is a registered trademark of NEXON Korea Corp. & NEXON GAMES Co., Ltd. All rights reserved.
