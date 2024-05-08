from datetime import timedelta
import math
import re
import requests
import os
import sys
import argparse
from threading import Thread
from time import sleep, time


arguments = argparse.ArgumentParser(description="碧蓝档案素材下载器")
arguments.add_argument("--threads", "-t", type=int,
                       help="同时下载的线程数", default=20)
arguments.add_argument("--version", "-v", type=str, help="游戏版本号，不填则自动获取")
arguments.add_argument("--region", "-g", type=str,
                       help="服务器区域 cn/gl/jp", required=False, default="cn")
arguments.add_argument("--raw", "-r", type=str,
                       help="指定原始文件输出位置", default="RawData")
arguments.add_argument("--extract", "-e", type=str,
                       help="指定解压文件输出位置", default="Extracted")
arguments.add_argument("--temporary", "-m", type=str,
                       help="指定临时文件输出位置", default="Temp")
arguments.add_argument("--downloading-extract", "-d",
                       type=bool, help="是否在下载时解开文件", default=False)
arguments.add_argument("--proxy", "-p", type=str,
                       help="为下载设置HTTP代理", default="http://10.1.49.50:10111")
arguments.add_argument("--max-retries", "-x", type=int,
                       help="下载时的最大重试次数", default=5)
args = arguments.parse_args()


class Downloader():
    def __init__(self) -> None:
        self.app = "com.nexon.bluearchive"
        self.headers = {'User-Agent': 'Mozilla/5.0'}
        self.apis = {
            "cnInfo": "https://gs-api.bluearchive-cn.com/api/state",
            "gl": "https://api-pub.nexon.com/patch/v1.1/version-check",
            "jpInfo": "https://yostar-serverinfo.bluearchiveyostar.com/r67_jjjg51ngucokd90cuk4l.json",
            "jp": "https://yostar-serverinfo.bluearchiveyostar.com/r67_jjjg51ngucokd90cuk4l_3",
            "jpReserve": "https://prod-clientpatch.bluearchiveyostar.com/r62_18adige2364es3ybluha_2"
        }
        self.threads = args.threads
        self.version = args.version
        self.region = args.region.lower()
        self.rawDir = args.raw
        self.extractDir = args.extract
        self.tempDir = args.temporary
        self.isDownloadingExtract = args.downloading_extract
        self.proxy = {"http": args.proxy,
                      "https": args.proxy} if args.proxy else None
        self.retries = args.max_retries
        self.sharedCounter = 0
        self.sharedInterrupter = False
        self.sharedMessageBus = ""
        self.main()

    def main(self,) -> None:
        print("Fetching version")
        if not self.version:
            print("Version not specified. Auto fetching latest...")
            self.version = self.getLatestVersion()
        print("Fetching resource version:", self.version)
        assetFiles = self.getAssetsMetaData()
        print(f"Success to fetch. {len(assetFiles)} files in manifest.")
        apkUrl = self.getApkMetaData() if args.region == "cn" else None
        print("Updating resources...")
        self.updateResources(assetFiles, apkUrl)

    def updateResources(self, assets: list,  apkUrl: str = None) -> None:
        assetsSize = 0
        apkSize = 0
        assetsNeedUpdate = []
        Thread(target=self.progressBar, args=(len(assets),
               "Checking integrity...", "item")).start()
        for counter, asset in enumerate(assets):
            self.sharedCounter = counter + 1
            if os.path.exists(os.path.join(self.rawDir, asset["path"])) and os.path.getsize(os.path.join(self.rawDir, asset["path"])) == asset["size"]:
                continue
            assetsNeedUpdate.append(asset)
            assetsSize += asset["size"]
        self.sharedInterrupter = True
        sleep(0.2)
        print(f"\n{len(assetsNeedUpdate)} files need to download.")
        if apkUrl:
            apkPath = os.path.join(self.tempDir, apkUrl.rsplit("/", 1)[-1])
            apkSize = int(requests.head(
                apkUrl, proxies=self.proxy).headers['Content-Length'])
            if os.path.exists(apkPath) and os.path.getsize(apkPath) == apkSize:
                apkUrl = None
        self.downloadResources(assetsNeedUpdate, assetsSize, apkUrl, apkSize)

    def downloadResources(self, assets: list, assetsSize: int,  apkUrl: str = None, apkSize: int = None) -> None:
        failedFiles = []
        if len(assets) > 0:
            threads = []

            def seperateBlocks():
                for i in range(0, len(assets), math.ceil(len(assets) / self.threads)):
                    yield assets[i:i + math.ceil(len(assets) / self.threads)]
            Thread(target=self.progressBar, args=(
                assetsSize, "Downloading Assets...", "MB", 1048576)).start()

            def downloadAsset(part: list):
                for asset in part:
                    os.makedirs(os.path.join(
                        self.rawDir, asset["path"].rsplit("/", 1)[0]), exist_ok=True)
                    self.sharedMessageBus = asset["path"].rsplit("/", 1)[-1]
                    if not self.fileDownloader(asset["baseUrl"] + "/" + asset["path"], os.path.join(self.rawDir, asset["path"]), self.headers):
                        failedFiles.append(asset)
            blocks = list(seperateBlocks())
            for part in blocks:
                thread = Thread(target=downloadAsset, args=(part,))
                thread.start()
                threads.append(thread)
            [thread.join() for thread in threads]
            self.sharedInterrupter = True
        if apkUrl:
            threads = []
            apkPath = os.path.join(self.tempDir, apkUrl.rsplit("/", 1)[-1])
            os.makedirs(self.tempDir, exist_ok=True)
            chunkSize = apkSize // self.threads
            for i in range(self.threads):
                start = chunkSize * i
                end = start + chunkSize - 1 if i != self.threads - 1 else apkSize
                output = os.path.join(self.tempDir, f"chunk_{i}.dat")
                header = {"Range": f"bytes={start}-{end}"}
                thread = Thread(target=self.fileDownloader,
                                args=(apkUrl, output, header))
                threads.append(thread)
                thread.start()
            self.sharedMessageBus = apkUrl.rsplit("/", 1)[-1]
            Thread(target=self.progressBar, args=(
                apkSize, "Downloading APK...",  "MB", 1048576)).start()
            [thread.join() for thread in threads]
            self.sharedInterrupter = True
            sleep(0.2)
            with open(apkPath, "wb") as file:
                Thread(target=self.progressBar, args=(
                    self.threads, "Combinating to APK...",  "item")).start()
                for i in range(self.threads):
                    self.sharedMessageBus = f"chunk_{i}.dat"
                    self.sharedCounter += 1
                    with open(os.path.join(self.tempDir, f"chunk_{i}.dat"), "rb") as chunk:
                        file.write(chunk.read())
            self.sharedInterrupter = True
            [os.remove(os.path.join("Temp", file))
             if file.startswith("chunk") and file.endswith(".dat") else _ for _, _, files in os.walk("Temp") for file in files]

    def fileDownloader(self, url: str, target: str, header: dict, retried: int = 0) -> bool:
        counter = 0
        try:
            if retried > self.retries:
                print(f"Max retries exceeded for 5 times with file {target}.")
                return False
            response = requests.get(
                url, headers=header, stream=True, proxies=self.proxy, timeout=3)
            with open(target, "wb") as file:
                for data in response.iter_content(chunk_size=4096):
                    file.write(data)
                    self.sharedCounter += len(data)
                    counter += len(data)
            return True
        except:
            retried += 1
            self.sharedCounter -= counter
            return self.fileDownloader(url, target, header, retried)

    def progressBar(self, total: int, note: str = "", metric: str = "MB", unitConvert: int = 1):
        self.sharedInterrupter = False
        startTime = time()
        completeTime = 0
        completeData = 0
        rollCount = 0
        lastMessage = ""
        while not self.sharedInterrupter:
            if time() - completeTime > 0.5:
                percent = self.sharedCounter / total * 100
                barLength = 20
                fillLength = int(
                    round(barLength * self.sharedCounter / float(total)))
                bar = "=" * fillLength + ">" + ' ' * (barLength - fillLength)
                remainTime = timedelta(seconds=(total - self.sharedCounter) /
                                       (self.sharedCounter / (time() - startTime + 0.01) + 0.01)).seconds
                rollCount = rollCount + 1 if barLength + \
                    rollCount < len(self.sharedMessageBus) and self.sharedMessageBus == lastMessage else 0
                sys.stdout.write(
                    f"\r[{bar}]  {self.sharedMessageBus[rollCount:barLength + rollCount]}  {((self.sharedCounter - completeData) / unitConvert / (time() - completeTime + 0.01)):0.2f}  {metric}/s  {percent:.2f}%  {(remainTime // 3600):02d}:{(remainTime % 3600 // 60):02d}:{(remainTime % 60):02d}  {note}" + " " * (barLength + 20))

                sys.stdout.flush()
                completeTime = time()
                completeData = self.sharedCounter
                lastMessage = self.sharedMessageBus
            sleep(0.1)
        self.sharedCounter = 0

    def getApkMetaData(self) -> str:
        # Apk file own media and table files.
        home = "https://bluearchive-cn.com/"
        homePage = requests.get(home, proxies=self.proxy).text
        jsUrl = re.search(
            r'<script.*?crossorigin src="(.*?)"></script>', homePage).group(1)
        jsFile = requests.get(jsUrl, proxies=self.proxy).text
        apkUrl = re.search(r'http[s]?://[^\s"<>]+?\.apk',
                           jsFile, re.DOTALL).group()
        return apkUrl

    def getLatestVersion(self) -> str:
        # Spider version from official site or store.
        if self.region == "cn":
            # Fetch version from official JavaScript file.
            home = "https://bluearchive-cn.com/"
            read = requests.get(home, headers=self.headers,
                                proxies=self.proxy).text
            js = re.search(
                r'<script.*?crossorigin src="(.*?)"></script>', read).group(1)
            page = requests.get(js, proxies=self.proxy).text
            version = re.search(r'(?<=/)(\d+\.\d+\.\d+)(?=/)', page)
        elif self.region == "gl":
            # Fetch version from uptodown.
            home = requests.get(
                f"https://blue-archive-global.en.uptodown.com/android", headers=self.headers, proxies=self.proxy)
            version = re.search(r'(\d+\.\d+\.\d+)',
                                home.text, re.DOTALL)
        elif self.region == "jp":
            # Fetch version from google.
            home = requests.get(
                f"https://play.google.com/store/apps/details?id=com.YostarJP.BlueArchive", headers=self.headers, proxies=self.proxy)
            version = re.search(
                r'\b\d{1}\.\d{2}\.\d{6}\b', home.text, re.DOTALL)
        else:
            raise ValueError("Region argument doesn't match one of cn/gl/jp.")
        if version:
            version = version.group()
        else:
            raise LookupError(
                "Could not fetch the version. Configure it manually if possible.")
        return version

    def getAssetsMetaData(self) -> list:
        # Using to fetch the API of static files.
        assets = []
        try:
            if self.region == "cn":
                # CN version using unique API. Different version number to seperate files. Now only bundles able discrover.
                info = requests.get(self.apis["cnInfo"], headers={
                                    "APP-VER": self.version, "PLATFORM-ID": "1", "CHANNEL-ID": "2"}, proxies=self.proxy).json()
                resources = requests.get(info["AddressablesCatalogUrlRoots"][0] + "/AssetBundles/Catalog/" +
                                         info["ResourceVersion"] + "/Android/bundleDownloadInfo.json", headers=self.headers, proxies=self.proxy).json()
                for res in resources["BundleFiles"]:
                    assets.append({"baseUrl": info["AddressablesCatalogUrlRoots"][0],
                                   "path": "AssetBundles/Android/" + res["Name"], "size": res["Size"]})
            elif self.region == "gl":
                # GL version using unique API. All files list in manifest.
                info = requests.post(self.apis["gl"], json={"market_game_id": "com.nexon.bluearchive", "market_code": "playstore",
                                                            "curr_build_version": self.version, "curr_build_number": self.version.split(".")[-1]}, headers=self.headers, proxies=self.proxy).json()
                resources = requests.get(
                    info["patch"]["resource_path"], headers=self.headers, proxies=self.proxy).json()
                for res in resources["resources"]:
                    assets.append({"baseUrl": info["patch"]["resource_path"].rsplit("/", 1)[0],
                                   "path": res["resource_path"], "size": res["resource_size"]})
            elif self.region == "jp":
                # JP version using non-unique API. Files seperate in different folder.
                info = requests.get(
                    self.apis["jpInfo"], headers=self.headers, proxies=self.proxy).json()
                baseUrl = info["ConnectionGroups"][0]["OverrideConnectionGroups"][-1]["AddressablesCatalogUrlRoot"]
                resources = requests.get(
                    baseUrl + "/TableBundles/TableCatalog.json", headers=self.headers, proxies=self.proxy)
                if resources.headers.get("Content-Type") != "application/json":
                    print("Latest version unavailable for TableBundles. Using older...")
                    resources = requests.get(
                        self.apis["jpReserve"] + "/TableBundles/TableCatalog.json", headers=self.headers, proxies=self.proxy)
                for res in resources.json()["Table"].values():
                    assets.append({"baseUrl": baseUrl + "/TableBundles",
                                   "path": res["Name"], "size": res["Size"]})
                resources = requests.get(
                    baseUrl + "/MediaResources/MediaCatalog.json", headers=self.headers, proxies=self.proxy)
                if resources.headers.get("Content-Type") != "application/json":
                    print(
                        "Latest version unavailable for MediaResources. Using older...")
                    resources = requests.get(
                        self.apis["jpReserve"] + "/MediaResources/MediaCatalog.json", headers=self.headers, proxies=self.proxy)
                for res in resources.json()["Table"].values():
                    assets.append({"baseUrl": baseUrl + "/MediaResources",
                                   "path": res["path"], "size": res["Bytes"]})
                resources = requests.get(
                    baseUrl + "/Android/bundleDownloadInfo.json", headers=self.headers, proxies=self.proxy)
                if resources.headers.get("Content-Type") != "application/json":
                    print("Latest version unavailable for AssetBundles. Using older...")
                    resources = requests.get(
                        self.apis["jpReserve"] + "/Android/bundleDownloadInfo.json", headers=self.headers, proxies=self.proxy)
                for res in resources.json()["BundleFiles"]:
                    assets.append({"baseUrl": baseUrl + "/Android",
                                   "path": res["Name"], "size": res["Size"]})
            return assets
        except Exception as err:
            print("Error when fetching resources list:", err)
            if len(assets) == 0:
                raise FileNotFoundError("Cannot pull the manifest.")


if __name__ == "__main__":
    Downloader()
