# Blue Archive Asset Downloader

<div align="center">本项目可以从不同服务器下载并解开碧蓝档案的素材，现支援中国服、国际服、日本服。</div>


## 主要功能

- **多服务器支持**：可从中国(蔚蓝档案)、国际(Blue Archive)、日本(ブルーアーカイブ)三个服务器下载素材。
- **资源解开**：在日本服务器中包含几乎完整的支持。


## 资源类型

下载的文件类型包括：

- Bundle
- Media
- Table

解开的文件类型包括：

- Bundle(仅JP)
- Media
- Table(仅JP)

## 环境要求

- Python 3.10 或更高版本
- [.NET8](https://dotnet.microsoft.com/download)(解开table或使用高级检索时必须启用)

## 先决条件

请确保已安装 Python，并安装必要的库：
- 在安装UnityPy时，需要安装C++构建库，如您不希望安装，亦可使用[其他工具](#使用须知)。下载时解开的功能依赖该库。
```shell
pip install -r requirements.txt
```
## 使用说明
使用下列命令行参数运行 `main.py` 脚本（示例）：

```shell
python main.py --threads 30 --region jp --proxy http://0.0.0.0:0000
```
<!-- -as azusa,ハナコ,下江小春,아지타니히후미,聖園彌香 -->
## 参数说明

- `--region`, `-g` `*`服务器区域：`cn` (中国), `gl` (国际), `jp` (日本)。
- `--threads`, `-t` 同时下载的线程数。
- `--version`, `-v` 游戏版本号（仅支持国际服务器）。
- `--raw`, `-r` 指定原始文件位置。
- `--extract`, `-e` 指定解压文件位置。
- `--temporary`, `-m` 指定临时文件位置。
<!-- - `--downloading-extract`, `-de` 是否在下载时解开文件。 -->
- `--proxy`, `-p` 设置HTTP代理。
- `--max-retries`, `-x` 下载时的最大重试次数。
<!-- - `--search`, `-s` 普通检索，指定需要检索并下载的文件的关键词，使用半角英文逗号`,`分隔。 -->
<!-- - `--advance-search`, `-as` 高级检索，指定需要检索并下载的角色关键字，使用半角英文逗号`,`分隔。 -->

> **`*`** :必选的选项

## 输出
- `Temp`: 存储临时文件或非主要文件。如：Apk文件等。
- `RawData`: 存储经由目录下载的文件。如：Bundle、Media、Table等。
- `Extract`: 存储已解开的文件。如：Bundle、Media、Table与Dumps等。

## TODO

- **流式解包**：下载时解开文件。- 75%
- **角色检索**：包名检索或基于任何名称的检索。- 36%
- **Memory Pack** - 30%
- **完善CN/GL**
- **一些bug**


## 使用须知
- JP的APK文件来自于APKPure，在PlayStore已经更新后，APKPure可能需要一些时间来同步版本。
- 当各服务器处于维护时间时，可能会无法获取资源目录。
- 在某些地区可能需要使用代理服务器以下载特定区域的游戏资源。
- Bundle文件的解开基于UnityPy，如希望更加详细的内容请使用[AssetRipper](https://github.com/AssetRipper/AssetRipper)或[AssetStudio](https://github.com/Perfare/AssetStudio)


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
