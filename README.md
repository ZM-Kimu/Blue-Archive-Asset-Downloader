# Blue Archive Asset Downloader 

<div align="center">
本项目可以从不同服务器下载并提取碧蓝档案的素材，现支援中国服、国际服、日本服。</div>


## 主要功能

- **多服务器支持**：可从中国(蔚蓝档案)、国际(Blue Archive)、日本(ブルーアーカイブ)三个服务器下载素材。
- **资源解开**：在日本服务器中包含几乎完整的支持。


## 资源类型

下载的文件类型包括：

- Bundle
- Media
- Table

提取的文件类型包括：

- Bundle(仅JP)
- Media
- Table(仅JP)

## 环境要求

- Windows/Linux
- Python 3.10 或更高版本
- [.NET8](https://dotnet.microsoft.com/download)(提取table或使用高级检索时必须启用) 

## 先决条件

请确保已安装 Python，并安装必要的库：
```shell
pip install -r requirements.txt
```

## 使用说明
使用下列命令行参数运行 `main.py` 脚本以进行下载与提取（示例）：

```shell
python main.py --region jp 
```
或者，使用以下命令以仅下载资源而不进行提取（示例）：

```shell
python downloader.py --region jp
```


## **基本参数**
**`*`** :**必选的选项**
| 参数                    | 缩写  | 说明                                                                            | 默认值             | 示例                            |
| ----------------------- | ----- | ------------------------------------------------------------------------------- | ------------------ | ------------------------------- |
| **`--region`**`*`       | `-g`  | **服务器区域**：`cn`（中国）、`gl`（国际）、`jp`（日本）                        | 无                 | `-g jp`                         |
| `--threads`             | `-t`  | **同时下载或解压的线程数**                                                      | `20`               | `-t 50`                         |
| `--version`             | `-v`  | **需要下载的资源的版本号**（仅支持国际服务器）                                  | 无                 | `--version 1.2.3`               |
| `--raw`                 | `-r`  | **指定未处理文件的位置**                                                        | `"RawData"`        | `--raw raw_folder`              |
| `--extract`             | `-e`  | **指定已提取文件的位置**                                                        | `"Extracted"`      | `--extract output_folder`       |
| `--temporary`           | `-m`  | **指定临时文件的位置**                                                          | `"Temp"`           | `--temporary temp_dir`          |
| `--downloading-extract` | `-de` | **是否在下载时便提取文件**（⚠较慢，在资源数量多于500时请勿使用）                | `False`            | `--downloading-extract`         |
| `--resource-type`       | `-rt` | **资源类型**：`table`、`media`、`bundle`、`all`                                 | `all`              | `--resource-type media table`   |
| `--proxy`               | `-p`  | **设置 HTTP 代理**                                                              | 无（使用系统代理） | `--proxy http://127.0.0.1:8080` |
| `--max-retries`         | `-mr` | **下载失败时的最大重试次数**                                                    | `5`                | `--max-retries 3`               |
| `--search`              | `-s`  | **普通检索**，指定需要检索并下载的文件的关键词，使用空格分隔。                  |
| `--advance-search`      | `-as` | **高级检索**，指定所有需要检索并下载的角色关键字，使用空格分隔，需要.NET8环境。 |

**高级检索支持的检索条件(仅JP)：**
- `[*]` **名称**
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

-  示例 
```sh
  -as yume 百合園セイア 호시노 cv=小倉唯 height=153 birthday=2/19 illustrator=YutokaMizu school=Arius club=GameDev #属性检索
```
```sh
  -s aris ch0070 shiroko #包名检索
```


## 输出
- `Temp`: 存储临时文件或非主要文件。如：Apk文件等。
- `RawData`: 存储经由Catalog下载的文件。如：Bundle、Media、Table等。
- `Extracted`: 存储已提取的文件。如：Bundle、Media、Table与Dumps等。


## 使用须知
- JP的APK文件来自于APKPure，在PlayStore已经更新后，APKPure可能需要一些时间来同步版本。
- 当各服务器处于维护时间时，可能会无法获取资源目录。
- 在某些地区可能需要使用代理服务器以下载特定服务器的游戏资源。
- Bundle文件的提取基于UnityPy，如希望更加详细的内容请使用[AssetRipper](https://github.com/AssetRipper/AssetRipper)或[AssetStudio](https://github.com/Perfare/AssetStudio)

## TODO

- **Memory Pack** - 30%
- **完善CN/GL**
- **一些bug**

## 关于项目
本项目采用 [MIT 许可证](LICENSE)。

部分内容参照自：
- [Blue-Archive---Asset-Downloader](https://github.com/K0lb3/Blue-Archive---Asset-Downloader)
- [Il2CppDumper](https://github.com/Perfare/Il2CppDumper/tree/master)
- [BlueArchiveDownloaderJP](https://github.com/fiseleo/BlueArchiveDownloaderJP)
- [BA-AD](https://github.com/Deathemonic/BA-AD)

## 免责声明 / Disclaimer
该仓库仅供学习和展示用途，不托管任何实际资源。请注意，所有通过本项目下载的内容均应仅用于合法和正当的目的。开发者不对任何人因使用本项目而可能引发的直接或间接的损失、损害、法律责任或其他后果承担任何责任。用户在使用本项目时需自行承担风险，并确保遵守所有相关法律法规。如果有人使用本项目从事任何未经授权或非法的活动，开发者对此不承担任何责任。用户应对自身的行为负责，并了解使用本项目可能带来的任何风险。
This project is intended solely for educational and demonstrative purposes and does not provide any actual resources. Please note that all content downloaded through this project should only be used for legal and legitimate purposes. The developers are not liable for any direct or indirect loss, damage, legal liability, or other consequences that may arise from the use of this project. Users assume all risks associated with the use of this project and must ensure compliance with all relevant laws and regulations. If anyone uses this project for any unauthorized or illegal activities, the developers bear no responsibility. Users are responsible for their own actions and should understand the risks involved in using this project.

“蔚蓝档案”是上海星啸网络科技有限公司的注册商标，版权所有。
「ブルーアーカイブ」は株式会社Yostarの登録商標です。著作権はすべて保有されています。
"Blue Archive" is a registered trademark of NEXON Korea Corp. & NEXON GAMES Co., Ltd. All rights reserved.
