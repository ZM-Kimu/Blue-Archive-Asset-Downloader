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

from lib.compiler import CompileToPython, CSParser
from lib.console import ProgressBar, notice, print
from lib.dumper import IL2CppDumper
from lib.encryption import convert_string, create_key
from lib.structure import CNResource, JPResource
from utils.config import Config
from utils.util import FileUtils


class BundleExtractor:
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
