from __future__ import annotations

import base64
import json
import os
from os import path
from typing import Any

from ba_downloader.infrastructure.schema.crypto import convert_string, create_key
from ba_downloader.infrastructure.unity import UnityAssetReader


class JPServerInfoExtractor:
    def decode_server_url(self, data: bytes) -> str:
        ciphers = {
            "ServerInfoDataUrl": "X04YXBFqd3ZpTg9cKmpvdmpOElwnamB2eE4cXDZqc3ZgTg==",
            "DefaultConnectionGroup": "tSrfb7xhQRKEKtZvrmFjEp4q1G+0YUUSkirOb7NhTxKfKv1vqGFPEoQqym8=",
            "SkipTutorial": "8AOaQvLC5wj3A4RC78L4CNEDmEL6wvsI",
            "Language": "wL4EWsDv8QX5vgRaye/zBQ==",
        }
        b64_data = base64.b64encode(data).decode()
        json_str = convert_string(b64_data, create_key("GameMainConfig"))
        obj = json.loads(json_str)
        encrypted_url = obj[ciphers["ServerInfoDataUrl"]]
        return convert_string(encrypted_url, create_key("ServerInfoDataUrl"))

    def find_server_info(self, data_root: str) -> tuple[str, str]:
        url = version = ""
        for directory, _, files in os.walk(data_root):
            for file_name in files:
                file_path = path.join(directory, file_name)
                if url_obj := UnityAssetReader.search_objects(
                    file_path, ["TextAsset"], ["GameMainConfig"], True
                ):
                    url = self.decode_server_url(self._script_bytes(url_obj[0].read()))

                if version_obj := UnityAssetReader.search_objects(
                    file_path, ["PlayerSettings"]
                ):
                    try:
                        version = str(version_obj[0].read().bundleVersion)
                    except (AttributeError, OSError, RuntimeError, ValueError):
                        version = "unavailable"

                if url and version:
                    return url, version

        return url, version

    @staticmethod
    def _script_bytes(text_asset: Any) -> bytes:
        return text_asset.m_Script.encode("utf-8", "surrogateescape")
