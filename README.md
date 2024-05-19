# 碧蓝档案素材下载器 / Blue Archive Asset Downloader / ブルアカアッセトダウンローダー

<div align="center">本项目可以从不同服务器下载并读取碧蓝档案的素材，现支援中国版、国际版、日本版。</div>

## 主要功能

- **多服务器支持**：可从中国、国际、日本三个版本的服务器下载素材。
- **多线程下载**：支持多线程快速下载。
- **国服特别版**：Apk内数据下载。

## 素材内容

下载的文件类型包括但不限于：

- Bundle
- Media
- Table

## 环境要求

- Python 3.6 或更高版本

## 先决条件

请确保已安装 Python，并安装必要的库：

```shell
pip install -r requirements.txt
```
## 使用说明
使用下列命令行参数运行 `AssetsDownloader.py` 脚本（示例）：

```shell
python AssetsDownloader.py --threads 30 --version 1.8.1 --region cn --downloading-extract True --proxy http://0.0.0.0:0000 --max-retries 10 --search azusa,ハナコ,下江小春,아지타니히후미,聖園彌香
```
## 参数说明

- `--threads`, `-t` 同时下载的线程数。
- `--version`, `-v` 游戏版本号，不填则自动获取。
- `--region`, `-g` **`*`**服务器区域：`cn` (中国), `gl` (国际), `jp` (日本)。
- `--raw`, `-r` 指定原始文件输出位置。
- `--extract`, `-e` 指定解压文件输出位置。
- `--temporary`, `-m` 指定临时文件输出位置。
- `--downloading-extract`, `-d` 是否在下载时解压文件。
- `--proxy`, `-p` 设置HTTP代理。
- `--max-retries`, `-x` 下载时的最大重试次数。
- `--search`, `-s` 指定需要检索并下载的文件的关键词，使用半角英文逗号`,`分隔。
> **`*`** :必选的选项
## TODO

- **流式解包**：下载时解开Bundle文件。
- **在线预览数据**：WebUI。


## 关于项目
本项目采用 [MIT 许可证](LICENSE)。
参照自[Blue-Archive---Asset-Downloader](https://github.com/K0lb3/Blue-Archive---Asset-Downloader)。

