import re
import requests
import os
import sys
import argparse
from AssetBatchConverter import extract_assets
from threading import Thread
from time import sleep
import UnityPy


arguments = argparse.ArgumentParser(description="碧蓝档案素材下载器")
arguments.add_argument("--threads", "-t", type=int,
                       help="同时下载的线程数", default=20)
arguments.add_argument("--version", "-v", type=str, help="游戏版本号，不填则自动获取")
arguments.add_argument("--legion", "-l", type=str,
                       help="服务器区域 cn/gl/jp", required=True)
arguments.add_argument("--raw", "-r", type=str,
                       help="指定原始文件输出位置", default="RawData")
arguments.add_argument("--extract", "-e", type=str,
                       help="指定解压文件输出位置", default="Extracted")
arguments.add_argument("--downloading-extract", "-d",
                       type=bool, help="是否在下载时解压", default=False)


GLOBALWAIT = 2
if len(sys.argv) >= 5:
    GLOBALTHREADS = int(sys.argv[sys.argv.index("-t")+1])
    GLOBALWAIT = int(sys.argv[sys.argv.index("-w")+1])


ROOT = os.path.dirname(os.path.realpath(__file__))
RAW = os.path.join(ROOT, "raw")
EXT = os.path.join(ROOT, "extracted")
VERSION = os.path.join(ROOT, "version.txt")


appId = "com.nexon.bluearchive"


def main():
    args = arguments.parse_args()

    print("Fetching version")
    version = args.version
    if not args.version:
        print("Version not specified. Auto fetching...")
        version = getAPKVersion(args.legion)
    print(version)

    print("Fetch latest resource version")

    try:
        check = version_check(appId, build_version=version)
    except Exception as e:
        print("error during resource version request")
        print("updating apk settings")
        version = update_apk_version(appId, path)
        check = version_check(appId, build_version=version)

    print("Updating resources/assets")
    update_resources(check["patch"]["resource_path"])


def version_check(app_id: str, api_version: str = "v1.1", build_version: str = "1.35.115378"):
    req = requests.post(
        f"https://api-pub.nexon.com/patch/{api_version}/version-check",
        json={
            "market_game_id": app_id,
            "language": "en",
            "advertising_id": "00000000-0000-0000-0000-000000000000",
            "market_code": "playstore",
            "country": "US",
            "sdk_version": "187",  # doesn't seem to matter
            "curr_build_version": build_version,
            "curr_build_number": int(build_version.rsplit(".", 1)[1]),
            "curr_patch_version": 0,
        },
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 5.1.1; SM-A908N Build/LMY49I)",
            "Host": "api-pub.nexon.com",
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip",
        },
    )
    res = req.json()

    # latest_build_version = res["latest_build_version"]
    # latest_build_number = res["latest_build_number"]
    # if latest_build_version != build_version or latest_build_number != build_number:
    #    return version_check(api_version, latest_build_version, latest_build_number)
    return res


def update_resources(resource_path, lang="en"):
    # 1. get resource data
    req = requests.get(resource_path)
    res = req.json()

    # 2. update resources
    resource_main_url = resource_path.rsplit("/", 1)[0]
    tick = 0
    for resource in res["resources"]:
        # {
        # "group": "group2",
        # "resource_path": "JA/group2/e392fcd3de13100b67589ef873b1f6d4.bundle",
        # "resource_size": 25206,
        # "resource_hash": "42092be2cf4d14381107205e40ab08b1"
        # },
        now_percent = tick*100/len(res["resources"])
        print("="*(round(now_percent)//5)+"-"*((100-round(now_percent))//5),
              f"{round(now_percent,1)}%", "in", "100%")
        Thread(target=update_resource, args=(
            resource_main_url, resource,)).start()
        tick += 1
        if tick % GLOBALTHREADS == 0:
            sleep(GLOBALWAIT)


def update_resource(resource_main_url, resource):
    url = f"{resource_main_url}/{resource['resource_path']}"
    if url.endswith(".bundle"):
        raw_path = os.path.join(RAW, *resource["resource_path"].split("/"))
    else:
        raw_path = os.path.join(EXT, *resource["resource_path"].split("/"))
    os.makedirs(os.path.dirname(raw_path), exist_ok=True)

    if not (
        os.path.exists(raw_path)
        and os.path.getsize(raw_path) == resource["resource_size"]
    ):
        print(raw_path)
        data = False
        while True:
            try:
                data = requests.get(url).content
            except Exception as err:
                print(err)
                print(f"Error occurent when downloading {raw_path}, retry...")
            if data != False:
                if len(data) == resource["resource_size"]:
                    break
        with open(raw_path, "wb") as f:
            f.write(data)

        # Unity BundleFile
        if url.endswith(".bundle"):
            try:
                extract_assets(data)
            except Exception as e:
                print(e)
                print("failed to extract bundle")
                print(url)
                print(resource["resource_path"])
                raise e
            # extract with UnityPy


def update_apk_version(apk_id, path):
    print("downloading latest apk from QooApp")
    apk_data = download_QooApp_apk(apk_id)
    with open(os.path.join(path, "current.apk"), "wb") as f:
        f.write(apk_data)
    print("extracing app_version and api_version")
    version = extract_apk_version(apk_data)
    with open(VERSION, "wt") as f:
        f.write(version)

    return version


def extract_apk_version(apk_data):
    from zipfile import ZipFile
    import io
    import re

    with io.BytesIO(apk_data) as stream:
        with ZipFile(stream) as zip:
            # devs are dumb shit and keep moving the app version around
            with zip.open("assets/bin/Data/globalgamemanagers", "r") as f:
                env = UnityPy.load(f)
                for obj in env.objects:
                    if obj.type.name == "PlayerSettings":
                        build_version = re.search(
                            b"\d+?\.\d+?\.\d+", obj.get_raw_data()
                        )[0].decode()
                        return build_version
            # smali\com\nexon\pub\bar\q.smali has the v1.1 for Nexus


def getAPKVersion(legion: str):
    if legion == "cn":
        home = "https://bluearchive-cn.com/"
        read = requests.get(home).content.decode("utf8")
        js = re.search(
            r'<script.*?crossorigin src="(.*?)"></script>', read).group(1)
        page = requests.get(js).content.decode("utf8")
        version = re.search(r'/(\d+\.\d+\.\d+)/', page).group().strip("/")
        
    return version


if __name__ == "__main__":
    main()
