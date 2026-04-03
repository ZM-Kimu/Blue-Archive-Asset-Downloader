import json
import multiprocessing.synchronize
import os
from pathlib import Path
from queue import Empty
from typing import Any, Literal

from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.infrastructure.logging.console_logger import ConsoleLogger


class BundleExtractor:
    MAIN_EXTRACT_TYPES = [
        "Texture2D",
        "Sprite",
        "AudioClip",
        "Font",
        "TextAsset",
        "Mesh",
    ]

    def __init__(
        self,
        context: RuntimeContext,
        logger: LoggerPort | None = None,
    ) -> None:
        self.context = context
        self.logger = logger or ConsoleLogger()

    @property
    def bundle_extract_folder(self) -> str:
        return str(Path(self.context.extract_dir) / "Bundle")

    def __save(
        self, type: Literal["json", "binary", "mesh"], path: str, data: Any
    ) -> None:
        if type == "json":
            with open(path, "w", encoding="utf8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        elif type == "binary":
            with open(path, "wb") as f:
                f.write(data)
        elif type == "mesh":
            with open(path, "w", encoding="utf8", newline="") as f:
                f.write(data)

    @staticmethod
    def multiprocess_extract_worker(
        tasks: multiprocessing.Queue,
        context: RuntimeContext,
        extract_types: list[str] | None,
    ) -> None:
        """Multi-thread is not allowed in UnityPy. Use multi-process."""
        extractor = BundleExtractor(context)
        while True:
            try:
                bundle_path = tasks.get(timeout=0.1)
            except Empty:
                break
            try:
                extractor.extract_bundle(bundle_path, extract_types)
            except Exception as e:
                extractor.logger.error(f"Unexpected error occurred: {e}")

    def extract_bundle(
        self,
        res_path: str,
        extract_types: list[str] | None = None,
    ) -> None:
        """Extract bundle use bundle path."""
        import UnityPy

        counter: dict[str, int] = {}
        env = UnityPy.load(res_path)
        conditional = (
            (lambda x: x in extract_types) if extract_types else lambda _: True
        )
        for obj in env.objects:
            try:
                if (obj_type := obj.type.name) and conditional(obj_type):
                    data = obj.read()
                    extract_folder = str(Path(self.bundle_extract_folder) / obj_type)
                    os.makedirs(extract_folder, exist_ok=True)
                    counter[obj_type] = counter.get(obj_type, 0)
                    match obj_type:
                        case "Texture2D" | "Sprite":
                            image = data.image
                            image.save(str(Path(extract_folder) / f"{data.m_Name}.png"))

                        case "AudioClip":
                            for name, sample_data in data.samples.items():
                                file_path = str(Path(extract_folder) / name)
                                self.__save("binary", file_path, sample_data)

                        case "Font":
                            if data.m_FontData:
                                file_name = data.m_Name + (
                                    ".otf"
                                    if data.m_FontData[0:4] == b"OTTO"
                                    else ".ttf"
                                )
                                file_path = str(Path(extract_folder) / file_name)
                                self.__save("binary", file_path, data.m_FontData)

                        case "TextAsset":
                            file_path = str(Path(extract_folder) / f"{data.m_Name}")
                            self.__save(
                                "binary",
                                file_path,
                                data.m_Script.encode("utf-8", "surrogateescape"),
                            )

                        case "MonoBehaviour":
                            type_tree = obj.read_typetree()
                            source_file = obj.assets_file.name
                            name = type_tree.get("m_Name", None)
                            if not name:
                                name = str(counter[obj_type])
                                counter[obj_type] += 1
                            name = name.replace("/", "-")
                            file_path = str(Path(extract_folder) / f"{source_file}_{name}.json")
                            file_path = file_path.replace(" ", "")
                            self.__save("json", file_path, type_tree)

                        case "Mesh":
                            file_path = str(Path(extract_folder) / f"{data.m_Name}.obj")
                            try:
                                mesh_data = data.export()
                                self.__save("mesh", file_path, mesh_data)
                            except Exception as e:
                                raise RuntimeError(
                                    f"Cannot export mesh {data.m_Name}: {e}"
                                ) from e

                        case _:
                            parsed = obj.parse_as_dict()
                            name = (
                                parsed.get("m_Name", None)
                                or obj.container
                                or obj.assets_file.name
                            )
                            name = f"{obj_type}_{Path(name).name}_{counter[obj_type]}.json"
                            counter[obj_type] += 1
                            file_path = str(Path(extract_folder) / name)
                            self.__save("json", file_path, parsed)
            except Exception as e:
                self.logger.error(f"Error while extracting bundle {res_path}: {e}")

