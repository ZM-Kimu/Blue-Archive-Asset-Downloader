import argparse
import json
import math
import os
import re
import struct
import sys
import zlib
from datetime import timedelta
from threading import Thread
from time import sleep, time

import requests

from AssetExtractor import Extractor

# Commandline Arguments
parser = argparse.ArgumentParser(description="碧蓝档案素材下载器")
parser.add_argument("--threads", "-t", type=int, help="同时下载的线程数", default=20)
parser.add_argument(
    "--version", "-v", type=str, help="游戏版本号，不填则自动获取", default=None
)
parser.add_argument(
    "--region", "-g", type=str, help="服务器区域 cn/gl/jp", required=False, default="cn"
)
parser.add_argument(
    "--raw", "-r", type=str, help="指定原始文件输出位置", default="RawData"
)
parser.add_argument(
    "--extract", "-e", type=str, help="指定解压文件输出位置", default="Extracted"
)
parser.add_argument(
    "--temporary", "-m", type=str, help="指定临时文件输出位置", default="Temp"
)
parser.add_argument(
    "--downloading-extract", "-d", type=bool, help="是否在下载时解开文件", default=False
)
parser.add_argument(
    "--proxy",
    "-p",
    type=str,
    help="为下载设置HTTP代理",
    default="http://10.1.49.50:10111",
)
parser.add_argument(
    "--max-retries", "-x", type=int, help="下载时的最大重试次数", default=5
)
parser.add_argument(
    "--search", "-s", type=str, help="搜索含有指定关键词的文件", default=None
)

args = parser.parse_args()


class Configuration:
    def __init__(self, config) -> None:
        self.threads = config.threads
        self.version = config.version
        self.region = config.region.lower()
        self.raw_dir = config.raw
        self.extract_dir = config.extract
        self.temp_dir = config.temporary
        self.download_and_extract = config.downloading_extract
        self.search = config.search
        self.proxy = (
            {"http": config.proxy, "https": config.proxy} if config.proxy else None
        )
        self.retries = config.max_retries
        self.shared_counter = 0
        self.shared_interrupter = False
        self.shared_message = ""
        with open("CharactersMapping.json", "r", encoding="utf8") as f:
            self.charactersMapping = json.load(f)
        self.extractor = Extractor(self)


class Downloader(Configuration):
    def __init__(self, config) -> None:
        super().__init__(config)
        self.app = "com.nexon.bluearchive"
        self.headers = {"User-Agent": "Mozilla/5.0"}
        self.apis = {
            "cnInfo": "https://gs-api.bluearchive-cn.com/api/state",
            "gl": "https://api-pub.nexon.com/patch/v1.1/version-check",
            "jpInfo": "https://yostar-serverinfo.bluearchiveyostar.com/r67_jjjg51ngucokd90cuk4l.json",
            "jp": "https://yostar-serverinfo.bluearchiveyostar.com/r67_jjjg51ngucokd90cuk4l_3",
            "jpReserve": "https://prod-clientpatch.bluearchiveyostar.com/r62_18adige2364es3ybluha_2",
        }

    def main(self) -> None:
        print("Fetching version info...")
        if not self.version:
            print("Version not specified. Auto fetching latest version...")
            self.version = self.getLatestVersion()
        print(f"Current resource version: {self.version}")
        asset_files = self.getAssetsMetadata()
        print(f"Success to fetch. {len(asset_files)} files in manifest.")
        apk_url = self.getApkMetaData() if args.region == "cn" else None
        print("Updating resources...")
        self.updateResources(asset_files, apk_url)
        print("\nResources have been downloaded to your computer.")

    def updateResources(self, assets: list, apk_url: str = "") -> None:
        assets_size = 0
        apk_size = 0
        assets_to_update = []
        if self.search:
            assets=self.full_text_filter(assets)
            print(f'Found {len(assets)} files match to "{self.search}" from manifest.')
        Thread(
            target=self.progressBar,
            args=(len(assets), "Checking integrity...", "items"),
        ).start()
        for index, asset in enumerate(assets):
            self.shared_counter = index + 1
            asset_path = os.path.join(self.raw_dir, asset["path"])
            if (
                os.path.exists(asset_path)
                and os.path.getsize(asset_path) == asset["size"]
            ):
                continue
            assets_to_update.append(asset)
            assets_size += asset["size"]
        self.shared_interrupter = True
        sleep(0.2)
        print(f"\n{len(assets_to_update)} files needs to download.")
        if apk_url:
            apk_path = os.path.join(self.temp_dir, apk_url.rsplit("/", 1)[-1])
            apk_size = int(
                requests.head(apk_url, proxies=self.proxy, timeout=10).headers[
                    "Content-Length"
                ]
            )
            if os.path.exists(apk_path) and os.path.getsize(apk_path) == apk_size:
                apk_url = None
            # self.downloadResources(assets_to_update, assets_size)
        if self.search:
            self.downloadFromRemoteApk(apk_url, apk_size, self.search)
        else:
            self.downloadApk(apk_url, apk_size)
            self.extractor.extractApkFile(apk_path)

    def __seperate_list_as_blocks(self, assets: list, block_num: int):
        for i in range(0, len(assets), math.ceil(len(assets) / block_num)):
            yield assets[i : i + math.ceil(len(assets) / block_num)]

    def full_text_filter(self, contents) -> list:
        keywords = self.search.split(",").copy()
        print(f"Searching mapping data for {self.charactersMapping["version"]}...")
        new_contents = []
        key_mapping=self.charactersMapping["keyword_mapping"]
        for keyword in keywords.copy():
            for key in key_mapping:
                if keyword.lower() in key_mapping[key].lower():
                    keywords.append(key.lower())
        file_mapping=self.charactersMapping["source_file_mapping"]
        for keyword in keywords.copy():
            for file in file_mapping:
                if keyword.lower() in file_mapping[file].lower():
                    keywords.append(file.lower())
        for content in contents:
            for keyword in keywords:
                if keyword.lower() in content["path"].lower():
                    new_contents.append(content)
        return new_contents

    def downloadResources(
        self, assets: list, assets_size: int, retries: int = 0
    ) -> None:
        """
        Download resources from asset manifest.
        """
        failed_files = []
        if assets:
            threads = []
            Thread(
                target=self.progressBar,
                args=(assets_size, "Downloading Assets...", "MB", 1048576),
            ).start()

            def downloadAsset(part: list):
                for asset in part:
                    os.makedirs(
                        os.path.join(self.raw_dir, asset["path"].rsplit("/", 1)[0]),
                        exist_ok=True,
                    )
                    self.shared_message = asset["path"].rsplit("/", 1)[-1]
                    if not self.fileDownloader(
                        asset["baseUrl"] + "/" + asset["path"],
                        os.path.join(self.raw_dir, asset["path"]),
                        self.headers,
                    ):
                        failed_files.append(asset)

            asset_blocks = list(self.__seperate_list_as_blocks(assets, self.threads))
            for block in asset_blocks:
                thread = Thread(target=downloadAsset, args=(block,))
                thread.start()
                threads.append(thread)
            [thread.join() for thread in threads]
            self.shared_interrupter = True
            sleep(0.2)
            if failed_files:
                if retries > self.retries:
                    print(
                        f"\nMax retries exceeded for {self.retries} times with retring failed files."
                    )
                    return
                print("Retry for failed files.")
                self.downloadResources(
                    failed_files,
                    sum(file["size"] for file in failed_files),
                    retries + 1,
                )

    def downloadApk(self, apk_url: str, apk_size: int) -> None:
        if apk_url:
            threads = []
            apk_path = os.path.join(self.temp_dir, apk_url.rsplit("/", 1)[-1])
            os.makedirs(self.temp_dir, exist_ok=True)
            chunk_size = apk_size // self.threads
            for i in range(self.threads):
                start = chunk_size * i
                end = start + chunk_size - 1 if i != self.threads - 1 else apk_size
                output = os.path.join(self.temp_dir, f"chunk_{i}.dat")
                header = {"Range": f"bytes={start}-{end}"}
                thread = Thread(
                    target=self.fileDownloader, args=(apk_url, output, header)
                )
                thread.start()
                threads.append(thread)
            self.shared_message = apk_url.rsplit("/", 1)[-1]
            Thread(
                target=self.progressBar,
                args=(apk_size, "Downloading APK...", "MB", 1048576),
            ).start()
            [thread.join() for thread in threads]
            self.shared_interrupter = True
            sleep(0.2)
            with open(apk_path, "wb") as file:
                Thread(
                    target=self.progressBar,
                    args=(self.threads, "Combinating to APK...", "items"),
                ).start()
                for i in range(self.threads):
                    self.shared_message = f"chunk_{i}.dat"
                    self.shared_counter += 1
                    chunk_path = os.path.join(self.temp_dir, f"chunk_{i}.dat")
                    with open(chunk_path, "rb") as chunk:
                        file.write(chunk.read())
                    os.remove(chunk_path)
            self.shared_interrupter = True

    def __create_threads(self, target_func, thread_pool: list, *args: tuple) -> None:
        thread = Thread(target=target_func, args=args)
        thread.start()
        thread_pool.append(thread)

    def __parse_apk_eocd(self, data):
        eocd_signature = b"\x50\x4b\x05\x06"
        eocd_offset = data.rfind(eocd_signature)
        if eocd_offset == -1:
            raise EOFError("Cannot read the eocd of Apk file.")
        eocd = data[eocd_offset : eocd_offset + 22]
        _, _, _, _, _, cd_size, cd_offset, _ = struct.unpack("<IHHHHIIH", eocd)
        return cd_offset, cd_size

    def __parse_apk_central_directory(self, data):
        file_headers = []
        offset = 0
        while offset < len(data):
            if data[offset : offset + 4] != b"\x50\x4b\x01\x02":
                print(f"Invalid signature at offset {offset}")
                break
            pack = struct.unpack("<IHHHHHHIIIHHHHHII", data[offset : offset + 46])
            uncomp_size = pack[9]
            file_name_length = pack[10]
            extra_field_length = pack[11]
            file_comment_length = pack[12]
            local_header_offset = pack[16]
            file_name = data[offset + 46 : offset + 46 + file_name_length].decode(
                "utf8"
            )
            file_headers.append(
                {
                    "path": file_name,
                    "offset": local_header_offset,
                    "size": uncomp_size,
                    "extraSize": file_name_length
                    + file_comment_length
                    + extra_field_length
                    + 30,
                }
            )
            offset += 46 + file_name_length + extra_field_length + file_comment_length
        return file_headers

    def __download_decompress_file(
        self, apk_url: str, target_path: str, header_part: bytes, start_offset: int
    ) -> bool:
        """Request compressed data of file and extract it."""
        try:
            header = struct.unpack("<IHHHHHIIIHH", header_part[:30])
            _, _, _, compression, _, _, _, comp_size, _, file_name_len, extra_len = (
                header
            )
            data_start = start_offset + 30 + file_name_len + extra_len
            data_end = data_start + comp_size
            compressed_data = self.fileDownloader(
                apk_url,
                True,
                {"Range": f"bytes={data_start}-{data_end - 1}"},
            )
            return self.extractor.decompressFilePart(
                compressed_data, target_path, compression
            )
        except:
            return False

    def downloadFromRemoteApk(
        self,
        apk_url: str,
        apk_size: int,
        target_keyword: str = "",
        retries: int = 0,
        retrying_files: list = [],
    ) -> None:
        failed_files = []
        threads = []
        target_header = []
        eocd_part = self.fileDownloader(
            apk_url,
            True,
            {"Range": f"bytes={apk_size - min(4096, apk_size)}-{apk_size - 1}"},
        )
        cd_offset, cd_size = self.__parse_apk_eocd(eocd_part)
        if cd_offset is not None and cd_size is not None:
            central_directory = self.fileDownloader(
                apk_url, True, {"Range": f"bytes={cd_offset}-{cd_offset + cd_size - 1}"}
            )
            if central_directory:
                file_headers = self.__parse_apk_central_directory(central_directory)
                target_header = self.full_text_filter(file_headers)
                print(
                    f'Found {len(target_header)} files match to "{target_keyword}" from Apk.'
                )
        target_header += retrying_files
        if target_header:
            Thread(
                target=self.progressBar,
                args=(
                    len(target_header),
                    "Downloading specified assets...",
                    "items",
                ),
            ).start()

            def downloadAsset(part) -> None:
                for asset in part[0]:
                    self.shared_message = asset["path"]
                    file_path = os.path.join(self.raw_dir, asset["path"])
                    os.makedirs(
                        file_path.rsplit("/", 1)[0],
                        exist_ok=True,
                    )
                    if (
                        os.path.exists(file_path)
                        and os.path.getsize(file_path)
                        == asset["size"] - asset["extraSize"]
                    ):
                        continue
                    header_part = self.fileDownloader(
                        apk_url,
                        True,
                        {"Range": f'bytes={asset["offset"]}-{asset["offset"] + 350}'},
                    )
                    is_compressed = self.__download_decompress_file(
                        apk_url,
                        file_path,
                        header_part,
                        asset["offset"],
                    )
                    if not is_compressed:
                        failed_files.append(asset)
                    self.shared_counter += 1

            asset_blocks = list(
                self.__seperate_list_as_blocks(target_header, self.threads)
            )

        for block in asset_blocks:
            self.__create_threads(downloadAsset, threads, (block,))
        [thread.join() for thread in threads]
        self.shared_interrupter = True
        sleep(0.2)
        if failed_files:
            if retries > self.retries:
                print(
                    f"\nMax retries exceeded for {self.retries} times with retring failed files."
                )
                return
            print("Retry for failed files.")
            self.downloadFromRemoteApk(
                apk_url, apk_size, target_keyword, retries + 1, failed_files
            )

    def fileDownloader(
        self, url: str, target: str | bool, headers: dict, retried: int = 0
    ):
        """
        Download the file resource.
        :param: url
        :param: target
        Which directory you want to save the file when receive string.
        This function will just return resource data if it is True.
        :param: headers
        Headers for request url.
        :param: retried
        """
        counter = 0
        try:
            if retried > self.retries:
                print(
                    f"\nMax retries exceeded for {self.retries} times with file {target}."
                )
                return False
            response = requests.get(
                url,
                headers=headers,
                stream=isinstance(target, str),
                proxies=self.proxy,
                timeout=3,
            )
            if isinstance(target, str):
                with open(target, "wb") as file:
                    start_time = time()
                    for chunk in response.iter_content(chunk_size=4096):
                        file.write(chunk)
                        self.shared_counter += len(chunk)
                        counter += len(chunk)
                        if counter < 4096 * (time() - start_time):
                            raise ConnectionError("Too slow to download. Reset...")
                return True
            if target is True:
                return response.content
        except:
            self.shared_counter -= counter
            return self.fileDownloader(url, target, headers, retried + 1)

    def progressBar(
        self, total: int, note: str = "", unit: str = "MB", unit_size: int = 1
    ) -> None:
        self.shared_interrupter = False
        start_time = time()
        last_update_time = 0
        data_size_since_last_update = 0
        rolling_position = 0
        last_message = ""
        while not self.shared_interrupter:
            if time() - last_update_time > 0.5:
                percent = self.shared_counter / total * 100
                bar_length = 20
                filled_length = int(
                    round(bar_length * self.shared_counter / float(total))
                )
                bar = "=" * filled_length + ">" + " " * (bar_length - filled_length)
                remaining_time = timedelta(
                    seconds=(total - self.shared_counter)
                    / (self.shared_counter / (time() - start_time + 0.01) + 0.01)
                ).seconds
                rolling_position = (
                    rolling_position + 1
                    if bar_length + rolling_position < len(self.shared_message)
                    and self.shared_message == last_message
                    else 0
                )
                sys.stdout.write(
                    f"\r[{bar}]  {self.shared_message[rolling_position:bar_length + rolling_position]}  {((self.shared_counter - data_size_since_last_update) / unit_size / (time() - last_update_time + 0.01)):0.2f} {unit}/s  {percent:.2f}%  {(remaining_time // 3600):02d}:{(remaining_time % 3600 // 60):02d}:{(remaining_time % 60):02d}  {note}"
                    + " " * (bar_length + 20)
                )
                sys.stdout.flush()
                last_update_time = time()
                data_size_since_last_update = self.shared_counter
                last_message = self.shared_message
            sleep(0.1)
        self.shared_counter = 0

    def getApkMetaData(self) -> str:
        # Apk file own media and table files.
        home_url = "https://bluearchive-cn.com/"
        response = requests.get(home_url, proxies=self.proxy, timeout=10)
        response.raise_for_status()
        js_url = re.search(
            r'<script.*?crossorigin src="(.*?)"></script>', response.text
        ).group(1)
        js_response = requests.get(js_url, proxies=self.proxy, timeout=10)
        js_response.raise_for_status()
        apk_url = re.search(
            r'http[s]?://[^\s"<>]+?\.apk', js_response.text, re.DOTALL
        ).group()
        return apk_url

    def getLatestVersion(self) -> str:
        # Spider version from official site or store.
        if self.region == "cn":
            # Fetch version from official JavaScript file.
            url = "https://bluearchive-cn.com/"
            response = requests.get(
                url, headers=self.headers, proxies=self.proxy, timeout=10
            ).text
            js_url = re.search(
                r'<script.*?crossorigin src="(.*?)"></script>', response
            ).group(1)
            js_response = requests.get(js_url, proxies=self.proxy, timeout=10).text
            version = re.search(r"(?<=/)(\d+\.\d+\.\d+)(?=/)", js_response)
        elif self.region == "gl":
            # Fetch version from uptodown.
            response = requests.get(
                "https://blue-archive-global.en.uptodown.com/android",
                headers=self.headers,
                proxies=self.proxy,
                timeout=10,
            )
            version = re.search(r"(\d+\.\d+\.\d+)", response.text, re.DOTALL)
        elif self.region == "jp":
            # Fetch version from google.
            response = requests.get(
                "https://play.google.com/store/apps/details?id=com.YostarJP.BlueArchive",
                headers=self.headers,
                proxies=self.proxy,
                timeout=10,
            )
            version = re.search(r"\b\d{1}\.\d{2}\.\d{6}\b", response.text, re.DOTALL)
        else:
            raise ValueError("Region argument doesn't match one of cn/gl/jp.")
        if version:
            version = version.group()
        else:
            raise LookupError(
                "Could not fetch the version. Configure it manually if possible."
            )
        return version

    def getAssetsMetadata(self) -> list:
        # Using to fetch the API of static files.
        assets = []
        try:
            if self.region == "cn":
                # CN version using unique API. Different version number to seperate files. Now only bundles able discrover.
                info = requests.get(
                    self.apis["cnInfo"],
                    headers={
                        "APP-VER": self.version,
                        "PLATFORM-ID": "1",
                        "CHANNEL-ID": "2",
                    },
                    proxies=self.proxy,
                    timeout=10,
                ).json()
                resources = requests.get(
                    info["AddressablesCatalogUrlRoots"][0]
                    + "/AssetBundles/Catalog/"
                    + info["ResourceVersion"]
                    + "/Android/bundleDownloadInfo.json",
                    headers=self.headers,
                    proxies=self.proxy,
                    timeout=10,
                ).json()
                for res in resources["BundleFiles"]:
                    assets.append(
                        {
                            "baseUrl": info["AddressablesCatalogUrlRoots"][0],
                            "path": "AssetBundles/Android/" + res["Name"],
                            "size": res["Size"],
                        }
                    )
            elif self.region == "gl":
                # GL version using unique API. All files list in manifest.
                info = requests.post(
                    self.apis["gl"],
                    json={
                        "market_game_id": "com.nexon.bluearchive",
                        "market_code": "playstore",
                        "curr_build_version": self.version,
                        "curr_build_number": self.version.split(".")[-1],
                    },
                    headers=self.headers,
                    proxies=self.proxy,
                    timeout=10,
                ).json()
                resources = requests.get(
                    info["patch"]["resource_path"],
                    headers=self.headers,
                    proxies=self.proxy,
                    timeout=10,
                ).json()
                for res in resources["resources"]:
                    assets.append(
                        {
                            "baseUrl": info["patch"]["resource_path"].rsplit("/", 1)[0],
                            "path": res["resource_path"],
                            "size": res["resource_size"],
                        }
                    )
            elif self.region == "jp":
                # JP version using non-unique API. Files seperate in different folder.
                info = requests.get(
                    self.apis["jpInfo"],
                    headers=self.headers,
                    proxies=self.proxy,
                    timeout=10,
                ).json()
                baseUrl = info["ConnectionGroups"][0]["OverrideConnectionGroups"][-1][
                    "AddressablesCatalogUrlRoot"
                ]
                # Table
                for index, api in enumerate([baseUrl, self.apis["jpReserve"]]):
                    resources = requests.get(
                        api + "/TableBundles/TableCatalog.json",
                        headers=self.headers,
                        proxies=self.proxy,
                        timeout=10,
                    )
                    if resources.headers.get("Content-Type") != "application/json":
                        if index == 1:
                            print("TableBundles now unavailable. Skip...")
                        else:
                            print(
                                "Latest version unavailable for TableBundles. Using older..."
                            )
                    else:
                        for res in resources.json()["Table"].values():
                            assets.append(
                                {
                                    "baseUrl": baseUrl + "/TableBundles",
                                    "path": res["Name"],
                                    "size": res["Size"],
                                }
                            )
                        break

                # Media
                for index, api in enumerate([baseUrl, self.apis["jpReserve"]]):
                    resources = requests.get(
                        api + "/MediaResources/MediaCatalog.json",
                        headers=self.headers,
                        proxies=self.proxy,
                        timeout=10,
                    )
                    if resources.headers.get("Content-Type") != "application/json":
                        if index == 1:
                            print("MediaResources now unavailable. Skip...")
                        else:
                            print(
                                "Latest version unavailable for MediaResources. Using older..."
                            )
                    else:
                        for res in resources.json()["Table"].values():
                            assets.append(
                                {
                                    "baseUrl": baseUrl + "/MediaResources",
                                    "path": res["path"],
                                    "size": res["Bytes"],
                                }
                            )
                        break
                # Bundles
                for index, api in enumerate([baseUrl, self.apis["jpReserve"]]):
                    resources = requests.get(
                        api + "/Android/bundleDownloadInfo.json",
                        headers=self.headers,
                        proxies=self.proxy,
                        timeout=10,
                    )
                    if resources.headers.get("Content-Type") != "application/json":
                        if index == 1:
                            print("AssetBundles now unavailable. Skip...")
                        else:
                            print(
                                "Latest version unavailable for AssetBundles. Using older..."
                            )
                    else:
                        for res in resources.json()["BundleFiles"]:
                            assets.append(
                                {
                                    "baseUrl": baseUrl + "/Android",
                                    "path": res["Name"],
                                    "size": res["Size"],
                                }
                            )
                        break
        except Exception as err:
            print("Error when fetching resources list:", err)
            if not assets:
                raise FileNotFoundError("Cannot pull the manifest.")
        return assets


if __name__ == "__main__":
    config = args
    downloader = Downloader(config)
    downloader.main()
