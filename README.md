# 碧蓝档案素材下载器/Blue Archive Asset Downloader/ブルアカアッセトダウンローダー

本项目可以从不同服务器下载并读取《碧蓝档案》的相关素材，现支援中国版、国际版、日本版。

## 主要功能

- **多服务器支持**：可从中国、国际、日本三个版本的服务器下载素材。
- **多线程下载**：支持多线程快速下载。

## 素材内容

下载的文件类型包括但不限于：

- Bundles
- Media
- Tables

## 环境要求

- Python 3.6 或更高版本

## 先决条件

请确保已安装 Python，并在命令行中执行以下命令以安装必要的库：

  ```shell
  pip install -r requirements.txt
  ```
## 使用说明
使用下列命令行参数运行 `AssetsDownloader.py` 脚本（示例）：

```shell
python AssetsDownloader.py --threads 30 --version 1.8.1 --region cn --downloading-extract True --proxy http://0.0.0.0:0000 --max-retries 10
```
### 参数说明

- `--threads`, `-t` 同时下载的线程数。
- `--version`, `-v` 游戏版本号，不填则自动获取。
- `--region`, `-g` 服务器区域：`cn` (中国), `gl` (国际), `jp` (日本)。
- `--raw`, `-r` 指定原始文件输出位置。
- `--extract`, `-e` 指定解压文件输出位置。
- `--temporary`, `-m` 指定临时文件输出位置。
- `--downloading-extract`, `-d` 是否在下载时解压文件。
- `--proxy`, `-p` 设置HTTP代理。
- `--max-retries`, `-x` 下载时的最大重试次数。

## 开发计划 (TODO)

- **自动解包**：可选项，下载中自动解压文件。


## 
本项目采用 [MIT 许可证](LICENSE)。
继承自[Blue-Archive---Asset-Downloader](https://github.com/K0lb3/Blue-Archive---Asset-Downloader)。