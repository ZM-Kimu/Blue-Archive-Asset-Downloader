import os
import zlib
from threading import Thread
from time import sleep, time
from zipfile import ZipFile


class Extractor:

    def __init__(self, dl) -> None:
        self.downloader = dl

    def extractApkFile(self, apk_path) -> None:
        with ZipFile(os.path.join(apk_path), "r") as zip:
            files = [
                item if item.startswith("assets/") else None for item in zip.namelist()
            ]
            Thread(
                target=self.downloader.progressBar,
                args=(len(files), "Extracting APK...", "items"),
            ).start()
            for item in files:
                self.downloader.shared_counter += 1
                self.downloader.shared_message = item
                if item and not (
                    os.path.exists(os.path.join(self.downloader.raw_dir, item))
                    and zip.getinfo(item).file_size
                    == os.path.getsize(os.path.join(self.downloader.raw_dir, item))
                ):
                    zip.extract(item, self.downloader.raw_dir)
            self.downloader.shared_interrupter = True
            sleep(0.2)

    def extractBundleFile(self, bundles_path: str | list) -> None:
        if isinstance(bundles_path, list):
            for bundle in bundles_path:
                pass
        elif isinstance(bundles_path, str):
            for path, _, files in os.walk(bundles_path):
                for file in files:
                    if file.endswith(".bundle"):
                        bundle_file = os.path.join(path, file)
    def decompressFilePart(self,compressed_data_part, file_path, compress_method) -> bool:
        """ Decompress pure compressed data. """
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

    def cc(self):

        asset_type = {
            "image": ["Sprite", "Texture2D"],
            "text": ["TextAsset"],
            "shader": ["Shader"],
            "monoBehaviour": ["MonoBehaviour"],
            "mesh": ["Mesh"],
            "font": ["Font"],
            "audio": ["AudioClip"],
        }

        root = "Extract"
        os.makedirs(root, exist_ok=True)
        [
            os.makedirs(os.path.join(root, path), exist_ok=True)
            for types in asset_type.values()
            for path in types
        ]
        prefix = "Extract"
        for path, _, files in os.walk("RawData"):
            for file in files:
                if file.endswith(".bundle"):
                    file_path = os.path.join(path, file)
                    env = UnityPy.load(file_path)
                    for obj in env.objects:
                        if obj.type.name in asset_type["image"]:
                            data = obj.read()
                            dest, _ = os.path.splitext(
                                os.path.join(prefix, obj.type.name, data.name)
                            )
                            data.image.save(dest + ".png")
                        elif obj.type.name in asset_type["text"]:
                            data = obj.read()
                            with open(
                                os.path.join(
                                    prefix, obj.type.name, data.name), "wb"
                            ) as file:
                                file.write(bytes(data.script))
                        elif obj.type.name in asset_type["monoBehaviour"] and False:
                            print(obj.name, env.file.name, obj.read().name)
                            if obj.serialized_type.nodes:
                                tree = obj.read_typetree()
                                path = os.path.join(
                                    prefix, obj.type.name, f"{
                                        tree['m_Name']}.json"
                                )
                                with open(path, "wt", encoding="utf8") as file:
                                    json.dump(
                                        tree, file, ensure_ascii=False, indent=4)
                            else:
                                data = obj.read()
                                path = os.path.join(
                                    prefix, obj.type.name, data.name)
                                with open(path, "wb") as file:
                                    file.write(data.raw_data)
                        elif obj.type.name in asset_type["audio"]:
                            for name, data in obj.read().samples.items():
                                path = os.path.join(
                                    prefix, obj.type.name, name)
                                with open(path, "wb") as file:
                                    file.write(data)
