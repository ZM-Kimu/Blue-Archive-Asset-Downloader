import base64
import json
import os
import struct
import zlib
from io import BytesIO
from json import dump
from os import path
from threading import Thread
from time import sleep, time
from typing import Any, Literal
from zipfile import ZipFile

import UnityPy

from utils.console import ProgressBar, notice, print
from utils.resource_structure import CNResource, JPResource
from utils.table_encrypt import convert_string, create_key

I8: str = "b"
I32: str = "i"
I64: str = "q"
BOOL: str = "?"


class Extractor:

    @staticmethod
    def extract_zip(
        zip_path: str | list[str],
        dest_dir: str,
        *,
        keywords: list[str] | None = None,
        zip_dir: str = "",
    ) -> list[str]:
        """Extracts specific files from a zip archive(s) to a destination directory.

        Args:
            zip_path (str | list[str]): Path(s) to the zip file(s).
            dest_dir (str): Directory where files will be extracted.
            keywords (list[str], optional): List of keywords to filter files for extraction. Defaults to None.
            zip_dir (str, optional): Base directory for relative paths. Defaults to "".

        Returns:
            list[str]: List of extracted file paths.
        """

        print(f"Extracting files from {zip_path} to {dest_dir}...")
        extract_list = []
        zip_files = []

        if isinstance(zip_path, str):
            zip_files = [zip_path]
        elif isinstance(zip_path, list):
            zip_files = [path.join(zip_dir, p) for p in zip_path]

        os.makedirs(dest_dir, exist_ok=True)

        for zip_file in zip_files:
            try:
                with ZipFile(zip_file, "r") as z:
                    if keywords:
                        extract_list = [
                            item for k in keywords for item in z.namelist() if k in item
                        ]
                    else:
                        extract_list = z.namelist()

                    with ProgressBar(len(extract_list), "Extract...", "items") as bar:
                        for item in extract_list:
                            try:
                                z.extract(item, dest_dir)
                            except Exception as e:
                                notice(e)
                            bar.increase()
            except Exception as e:
                notice(f"Error processing file '{zip_file}': {e}")

        return extract_list

    @staticmethod
    def decompress_file_part(compressed_data_part, file_path, compress_method) -> bool:
        """Decompress pure compressed data. Return True if saved to path."""
        try:
            if compress_method == 8:  # Deflate compression
                decompressor = zlib.decompressobj(-zlib.MAX_WBITS)
                decompressed_data = decompressor.decompress(compressed_data_part)
                decompressed_data += decompressor.flush()
            else:
                decompressed_data = compressed_data_part
            with open(file_path, "wb") as file:
                file.write(decompressed_data)
            return True
        except:
            return False

    @staticmethod
    def filter_unity_pack(
        pack_path: str,
        data_type: list | None = None,
        data_name: list | None = None,
        condition_connect: bool = False,
        read_obj_anyway: bool = False,
    ) -> list[UnityPy.environment.ObjectReader] | None:
        data_list: list[UnityPy.environment.ObjectReader] = []
        data_passed: bool = False
        try:
            env = UnityPy.load(pack_path)
            for obj in env.objects:
                if data_type and obj.type.name in data_type:
                    if condition_connect:
                        data_passed = True
                    else:
                        data_list.append(obj)
                if read_obj_anyway or data_passed:
                    data = obj.read()
                    if data_name and data.name in data_name:
                        if not (condition_connect or data_passed):
                            continue
                        data_list.append(obj)
        except:
            pass
        return data_list

    @staticmethod
    def decode_server_url(data: bytes) -> str:
        """
        Decodes the server URL from the given data.

        Args:
            data (bytes): Binary data to decode.

        Returns:
            str: Decoded server URL.
        """
        decrypt = {
            "ServerInfoDataUrl": "X04YXBFqd3ZpTg9cKmpvdmpOElwnamB2eE4cXDZqc3ZgTg==",
            "DefaultConnectionGroup": "tSrfb7xhQRKEKtZvrmFjEp4q1G+0YUUSkirOb7NhTxKfKv1vqGFPEoQqym8=",
            "SkipTutorial": "8AOaQvLC5wj3A4RC78L4CNEDmEL6wvsI",
            "Language": "wL4EWsDv8QX5vgRaye/zBQ==",
        }
        b64_data = base64.b64encode(data).decode()
        json_str = convert_string(b64_data, create_key("GameMainConfig"))
        obj = json.loads(json_str)
        encrypted_url = obj[decrypt["ServerInfoDataUrl"]]
        url = convert_string(encrypted_url, create_key("ServerInfoDataUrl"))
        return url


class AssetExtractor:
    @staticmethod
    def extract_resource(resource_path: str | list, dest_dir: str):
        resources = []
        res_type = [
            "Texture2D",
            "Sprite",
            "AudioClip",
            "TextAsset",
            "MonoBehaviour",
            "Shader",
            "Mesh",
            "Font",
        ]

        for type in res_type:
            os.makedirs(os.path.join(dest_dir, type), exist_ok=True)

        if isinstance(resource_path, str):
            resources.append(resource_path)
        else:
            resources = resource_path
        with ProgressBar(len(resources), "Extract bundle...", "items") as bar:
            for res in resources:
                try:
                    bar.increase()
                    env = UnityPy.load(res)

                    for obj in env.objects:
                        if (obj_type := obj.type.name) in res_type:
                            data = obj.read()

                            bar.item_text(path.split(res)[-1])

                            match obj_type:
                                case "Texture2D":
                                    image = data.image
                                    image.save(
                                        os.path.join(
                                            dest_dir, "Texture2D", f"{data.name}.png"
                                        )
                                    )

                                case "AudioClip":
                                    for name, data in data.samples.items():
                                        with open(
                                            os.path.join(
                                                dest_dir, "AudioClip", f"{name}.wav"
                                            ),
                                            "wb",
                                        ) as f:
                                            f.write(data)
                                case "TextAsset":
                                    text = data.text
                                    with open(
                                        os.path.join(
                                            dest_dir, "TextAsset", f"{data.name}.wav"
                                        ),
                                        "wb",
                                    ) as f:
                                        f.write(text)
                                case "MonoBehaviour":
                                    if obj.serialized_type.nodes:
                                        tree = obj.read_typetree()
                                        with open(
                                            os.path.join(
                                                dest_dir,
                                                "MonoBehaviour",
                                                f'{tree["m_Name"]}.json',
                                            ),
                                            "wt",
                                            encoding="utf8",
                                        ) as f:
                                            dump(tree, f, ensure_ascii=False, indent=4)
                                    else:
                                        data = obj.read()
                                        with open(
                                            os.path.join(
                                                dest_dir, data.name, data.name
                                            ),
                                            "wb",
                                        ) as f:
                                            f.write(data.raw_data)
                            # elif obj.type.name in asset_type["audio"]:
                            #     for name, data in obj.read().samples.items():
                            #         path = os.path.join(prefix, obj.type.name, name)
                            #         with open(path, "wb") as file:
                            #             file.write(data)
                except:
                    continue


class CNCatalogDecoder:
    media_types = {1: "ogg", 2: "mp4", 3: "jpg", 4: "png", 5: "acb", 6: "awb"}

    @staticmethod
    def decode_to_manifest(
        raw_data: bytes,
        container: CNResource,
        type: Literal["bundle", "table", "media"],
    ) -> dict[str, object]:
        """Used to decode bytes file to readable data structure. Data will return decoded and add to container.

        Args:
            raw_data (bytes): Binary data.
            container (CNResource): Container to storage manifest.
            type (Literal[&quot;table&quot;, &quot;media&quot;]): Data type.

        Returns:
            dict([str, object]): Manifest list.
        """
        manifest: dict[str, object] = {}
        data = BytesIO(raw_data)

        if type == "bundle":
            bundle_data = json.loads(raw_data)
            for item in bundle_data["BundleFiles"]:
                CNCatalogDecoder.__decode_bundle_manifest(item, container)

        if type == "media":
            while item := data.readline():
                key, obj = CNCatalogDecoder.__decode_media_manifest(item, container)
                manifest[key] = obj

        if type == "table":
            table_data: dict = json.loads(raw_data).get("Table", {})
            for file, item in table_data.items():
                key, obj = CNCatalogDecoder.__decode_table_manifest(
                    file, item, container
                )
                manifest[key] = obj

        return manifest

    @classmethod
    def __decode_bundle_manifest(
        cls, data: dict, container: CNResource
    ) -> tuple[str, dict[str, object]]:
        container.add_bundle_resource(
            data["Name"],
            data["Size"],
            data["Crc"],
            data["IsPrologue"],
            data["IsSplitDownload"],
        )

        return data["Name"], {
            "name": data["Name"],
            "size": data["Size"],
            "md5": data["Crc"],
            "is_prologue": data["IsPrologue"],
            "is_split_download": data["IsSplitDownload"],
        }

    @classmethod
    def __decode_media_manifest(
        cls, data: bytes, container: CNResource
    ) -> tuple[str, dict[str, object]]:
        path, md5, media_type_str, size_str, _ = data.decode().split(",")

        media_type = int(media_type_str)
        size = int(size_str)

        if media_type in cls.media_types.keys():
            path += f".{cls.media_types[media_type]}"
        else:
            print(f"Unidentifiable media type {media_type}.")
        file_url_path = md5[:2] + "/" + md5

        container.add_media_resource(file_url_path, path, media_type, size, md5)

        file_path, file_name = os.path.split(path)
        return file_url_path, {
            "path": file_path,
            "file_name": file_name,
            "type": media_type,
            "bytes": size,
            "md5": md5,
        }

    @classmethod
    def __decode_table_manifest(
        cls, key: str, item: dict, container: CNResource
    ) -> tuple[str, dict[str, object]]:

        path: str = item["Name"]
        md5: str = item["Crc"]
        size: int = item["Size"]
        includes: list = item["Includes"]

        size = int(size)
        file_url_path = md5[:2] + "/" + md5

        container.add_table_resource(file_url_path, path, size, md5, includes)

        return key, {
            "name": item["Name"],
            "size": item["Size"],
            "crc": item["Crc"],
            "includes": item["Includes"],
        }


class JPCatalogDecoder:

    class Reader:
        def __init__(self, initial_bytes) -> None:
            self.io = BytesIO(initial_bytes)

        def read(self, fmt: str) -> Any:
            return struct.unpack(fmt, self.io.read(struct.calcsize(fmt)))[0]

        def read_string(self) -> str:
            return self.io.read(self.read(I32)).decode(
                encoding="utf-8", errors="replace"
            )

        def read_table_includes(self) -> list[str]:
            size = self.read(I32)
            if size == -1:
                return []
            self.read(I32)
            includes = []
            for i in range(size):
                includes.append(self.read_string())
                if i != size - 1:
                    self.read(I32)
            return includes

    @staticmethod
    def decode_to_manifest(
        raw_data: bytes, container: JPResource, type: Literal["table", "media"]
    ) -> dict[str, object]:
        """Used to decode bytes file to readable data structure. Data will return decoded and add to container.

        Args:
            raw_data (bytes): Binary data.
            container (JPResource): Container to storage manifest.
            type (Literal[&quot;table&quot;, &quot;media&quot;]): Data type.

        Returns:
            dict([str, object]): Manifest list.
        """
        data = JPCatalogDecoder.Reader(raw_data)

        manifest: dict[str, object] = {}

        data.read(I8)
        item_num = data.read(I32)

        for _ in range(item_num):
            if type == "media":
                key, obj = JPCatalogDecoder.__decode_media_manifest(data, container)
            else:
                key, obj = JPCatalogDecoder.__decode_table_manifest(data, container)
            manifest[key] = obj
        return manifest

    @classmethod
    def __decode_media_manifest(
        cls, data: Reader, container: JPResource
    ) -> tuple[str, dict[str, object]]:
        data.read(I32)
        key = data.read_string()
        data.read(I8)
        data.read(I32)
        path = data.read_string()
        data.read(I32)
        file_name = data.read_string()
        bytes = data.read(I64)
        crc = data.read(I64)
        is_prologue = data.read(BOOL)
        is_split_download = data.read(BOOL)
        media_type = data.read(I32)

        container.add_media_resource(
            key, path, file_name, media_type, bytes, crc, is_prologue, is_split_download
        )

        return key, {
            "path": path,
            "file_name": file_name,
            "type": media_type,
            "bytes": bytes,
            "crc": crc,
            "is_prologue": is_prologue,
            "is_split_download": is_split_download,
        }

    @classmethod
    def __decode_table_manifest(
        cls, data: Reader, container: JPResource
    ) -> tuple[str, dict[str, object]]:
        data.read(I32)
        key = data.read_string()
        data.read(I8)
        data.read(I32)
        name = data.read_string()
        size = data.read(I64)
        crc = data.read(I64)
        is_in_build = data.read(BOOL)
        is_changed = data.read(BOOL)
        is_prologue = data.read(BOOL)
        is_split_download = data.read(BOOL)
        includes = data.read_table_includes()

        container.add_table_resource(
            key,
            name,
            size,
            crc,
            is_in_build,
            is_changed,
            is_prologue,
            is_split_download,
            includes,
        )

        return key, {
            "name": name,
            "size": size,
            "crc": crc,
            "is_in_build": is_in_build,
            "is_changed": is_changed,
            "is_prologue": is_prologue,
            "is_split_download": is_split_download,
            "includes": includes,
        }
