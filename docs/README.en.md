<div align="center">

# Blue Archive Asset Downloader

This project downloads and extracts Blue Archive assets from multiple regions. It currently supports the CN, GL, and JP servers.

<a href="../README.md">中文</a>

</div>


<!-- ## Features
- **Asset extraction**: Nearly complete support is available for the JP server.
- **CN milestone status**: `download --region cn`, `sync --region cn`, and `relation build --region cn` are currently available; `--advanced-search` is still unavailable.
- **JP milestone status**: `download --region jp`, `sync --region jp`, and `relation build --region jp` are currently available; `--advanced-search` is still unavailable. -->


## Resource Types

Downloadable resource categories:

- Bundle
- Media
- Table

Extractable resource categories:

- Bundle
- Media
- Table (partially unavailable)

#### **Note**: Although some regions support downloading different resource versions, this tool does not guarantee that outdated resource files can still be extracted.

## Requirements

- Windows/Linux
- Python 3.10 or later
- [.NET10 SDK](https://dotnet.microsoft.com/download) (install for table extraction)

## Prerequisites

When running from source, use a clone flow that includes submodules:

```shell
git clone --recurse-submodules https://github.com/ZM-Kimu/Blue-Archive-Asset-Downloader
cd Blue-Archive-Asset-Downloader
uv sync
```

- If `third_party/Cpp2IL` is missing locally, some dumper flows will try to download the source automatically.

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
```

Subcommands:

- `ba-downloader sync [options]`: Download and extract all resources
- `ba-downloader download [options]`: Download all resources
- `ba-downloader extract [options]`: Extract existing raw resources
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
**`*`**: **required option**

| Parameter                  | Short Form | Description                                                                                       | Default             | Example                       |
| -------------------------- | ---------- | ------------------------------------------------------------------------------------------------- | ------------------- | ----------------------------- |
| **`--region`**`*`          | `-r`       | **Server region**: `cn` (China), `gl` (Global), `jp` (Japan)                                      | None                | `-r jp`                       |
| `--threads`                | `-t`       | **Number of concurrent download or extraction workers**                                           | `20`                | `-t 50`                       |
| `--version`                | `-v`       | **Resource version to download** (effective for GL only)                                          | None                | `-v 1.2.3`                    |
| `--platform`               | `-p`       | **Resource platform**: `windows`, `android`, `ios` (effective for JP only)                        | `android`           | `-p windows`                  |
| `--raw-dir`                | `-rd`      | **Directory for raw downloaded files**                                                            | `"RawData"`         | `-rd raw_folder`              |
| `--extract-dir`            | `-ed`      | **Directory for extracted output**                                                                | `"Extracted"`       | `-ed output_folder`           |
| `--temp-dir`               | `-td`      | **Directory for temporary files**                                                                 | `"Temp"`            | `-td temp_dir`                |
| `--extract-while-download` | `-ewd`     | **Extract files while downloading** (available only for `sync`; use carefully for large datasets) | `False`             | `--extract-while-download`    |
| `--resource-type`          | `-rt`      | **Resource types**: `table`, `media`, `bundle`, `all`                                             | `all`               | `--resource-type media table` |
| `--proxy`                  | `-px`      | **HTTP proxy**                                                                                    | None (system proxy) | `-px http://127.0.0.1:8080`   |
| `--max-retries`            | `-mr`      | **Maximum retry count for failed downloads**                                                      | `5`                 | `--max-retries 3`             |
| `--search`                 | `-s`       | **Basic search**: keywords used to filter files for download (`sync` and `download` only)         |

<!-- | `--advanced-search`        | `-as`      | **Advanced search**: character-oriented filters (`sync` only; currently supported by GL only and requires a .NET environment) | -->

<!-- **Advanced-search fields (currently unsupported on CN):**
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
- Example:
  > sync
  >```sh
  >ba-downloader sync --region gl -as 貝雅特里榭 ยูเมะ ibuki
  >``` -->

  <!--
  > japan
  >```sh
  >ba-downloader sync --region jp -as yume 百合園セイア 호시노 cv=小倉唯 height=153 birthday=2/19 illustrator=YutokaMizu school=Arius club=GameDev
  >```
  -->
- Basic search:
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

- `--platform` applies only to JP and selects JP platform-specific resources.
- JP APK files are currently sourced from APKPure. After the Play Store updates, APKPure may take some time to synchronize. Official PC package parsing may be added later.
- Resource catalogs may be unavailable during server maintenance windows.
- A proxy may be required in some regions to download assets from specific servers.
- Bundle extraction is based on UnityPy. If you need more detailed extraction results, use [AssetRipper](https://github.com/AssetRipper/AssetRipper) or [AssetStudio](https://github.com/Perfare/AssetStudio).

## TODO

- `v2.2.0`
  - Improve JP extraction (requires a key)
  - Add a new bundle extractor

## About

Blue Archive Asset Downloader v2.1.0.

✨ Powered by Codex ✨

This project is licensed under the [MIT License](../LICENSE).

Parts of this project reference:
- [Blue-Archive---Asset-Downloader](https://github.com/K0lb3/Blue-Archive---Asset-Downloader)
- [Cpp2IL](https://github.com/SamboyCoding/Cpp2IL)

## Disclaimer

This repository is provided for educational and demonstration purposes only and does not host any actual game assets. Please note that all content downloaded through this project should only be used for legal and legitimate purposes. The developers are not liable for any direct or indirect loss, damage, legal liability, or other consequences arising from use of this project. Users assume all risks associated with using this project and must ensure compliance with all applicable laws and regulations. If anyone uses this project for any unauthorized or illegal activity, the developers bear no responsibility. Users are responsible for their own actions and should understand the risks involved in using this project.

“蔚蓝档案” is a registered trademark of Shanghai Xingxiao Network Technology Co., Ltd. All rights reserved.

「ブルーアーカイブ」は株式会社Yostarの登録商標です。著作権はすべて保有されています。

"Blue Archive" is a registered trademark of NEXON Korea Corp. & NEXON GAMES Co., Ltd. All rights reserved.
