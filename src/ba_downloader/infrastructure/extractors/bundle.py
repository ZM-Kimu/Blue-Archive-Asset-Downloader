import json
import multiprocessing.synchronize
import os
from collections.abc import Callable
from pathlib import Path
from queue import Empty
from typing import Any, ClassVar, Literal

from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.infrastructure.logging.console_logger import ConsoleLogger
from ba_downloader.infrastructure.logging.runtime import configure_logging


class BundleExtractor:
    MAIN_EXTRACT_TYPES: ClassVar[list[str]] = [
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
        error_count: Any | None = None,
    ) -> None:
        """Multi-thread is not allowed in UnityPy. Use multi-process."""
        configure_logging()
        extractor = BundleExtractor(context)
        try:
            while True:
                try:
                    bundle_path = tasks.get(timeout=0.1)
                except Empty:
                    break
                try:
                    extractor.extract_bundle(bundle_path, extract_types)
                except Exception as exc:  # pylint: disable=broad-exception-caught
                    extractor._increment_error_count(error_count)
                    extractor.logger.error(
                        f"Failed to extract bundle {bundle_path}: "
                        f"{extractor._format_exception(exc)}"
                    )
        except KeyboardInterrupt:
            return

    def extract_bundle(
        self,
        res_path: str,
        extract_types: list[str] | None = None,
    ) -> None:
        """Extract bundle use bundle path."""
        import UnityPy

        counter: dict[str, int] = {}
        env = UnityPy.load(res_path)
        conditional = self._build_extract_filter(extract_types)
        for obj in env.objects:
            try:
                self._extract_object(obj, counter, conditional)
            except Exception as exc:  # pylint: disable=broad-exception-caught
                self.logger.error(
                    f"Error while extracting bundle {res_path}: "
                    f"{self._format_exception(exc)}"
                )

    @staticmethod
    def _format_exception(exc: Exception) -> str:
        detail = str(exc).strip()
        if detail:
            return f"{type(exc).__name__}: {detail}"
        return type(exc).__name__

    @staticmethod
    def _increment_error_count(error_count: Any | None) -> None:
        if error_count is None:
            return
        get_lock = getattr(error_count, "get_lock", None)
        if callable(get_lock):
            with get_lock():
                error_count.value += 1
            return
        error_count.value += 1

    @staticmethod
    def _build_extract_filter(
        extract_types: list[str] | None,
    ) -> Callable[[str], bool]:
        if not extract_types:
            return lambda _: True
        return lambda obj_type: obj_type in extract_types

    def _extract_object(
        self,
        obj: Any,
        counter: dict[str, int],
        conditional: Callable[[str], bool],
    ) -> None:
        obj_type = obj.type.name
        if not obj_type or not conditional(obj_type):
            return

        data = obj.read()
        extract_folder = self._ensure_extract_folder(obj_type)
        counter.setdefault(obj_type, 0)
        self._dispatch_extraction(obj, data, obj_type, counter, extract_folder)

    def _dispatch_extraction(
        self,
        obj: Any,
        data: Any,
        obj_type: str,
        counter: dict[str, int],
        extract_folder: str,
    ) -> None:
        if obj_type in {"Texture2D", "Sprite"}:
            self._extract_image(data, extract_folder)
        elif obj_type == "AudioClip":
            self._extract_audio(data, extract_folder)
        elif obj_type == "Font":
            self._extract_font(data, extract_folder)
        elif obj_type == "TextAsset":
            self._extract_text_asset(data, extract_folder)
        elif obj_type == "MonoBehaviour":
            self._extract_monobehaviour(obj, obj_type, counter, extract_folder)
        elif obj_type == "Mesh":
            self._extract_mesh(data, extract_folder)
        else:
            self._extract_generic_object(obj, obj_type, counter, extract_folder)

    def _ensure_extract_folder(self, obj_type: str) -> str:
        extract_folder = str(Path(self.bundle_extract_folder) / obj_type)
        os.makedirs(extract_folder, exist_ok=True)
        return extract_folder

    def _extract_image(self, data: Any, extract_folder: str) -> None:
        data.image.save(str(Path(extract_folder) / f"{data.m_Name}.png"))

    def _extract_audio(self, data: Any, extract_folder: str) -> None:
        for name, sample_data in data.samples.items():
            self.__save("binary", str(Path(extract_folder) / name), sample_data)

    def _extract_font(self, data: Any, extract_folder: str) -> None:
        if not data.m_FontData:
            return
        file_name = data.m_Name + (".otf" if data.m_FontData[0:4] == b"OTTO" else ".ttf")
        self.__save("binary", str(Path(extract_folder) / file_name), data.m_FontData)

    def _extract_text_asset(self, data: Any, extract_folder: str) -> None:
        self.__save(
            "binary",
            str(Path(extract_folder) / data.m_Name),
            data.m_Script.encode("utf-8", "surrogateescape"),
        )

    def _extract_monobehaviour(
        self,
        obj: Any,
        obj_type: str,
        counter: dict[str, int],
        extract_folder: str,
    ) -> None:
        type_tree = obj.read_typetree()
        source_file = obj.assets_file.name
        name = type_tree.get("m_Name") or str(counter[obj_type])
        counter[obj_type] += 1
        sanitized_name = str(name).replace("/", "-").replace(" ", "")
        file_path = Path(extract_folder) / f"{source_file}_{sanitized_name}.json"
        self.__save("json", str(file_path), type_tree)

    def _extract_mesh(self, data: Any, extract_folder: str) -> None:
        file_path = str(Path(extract_folder) / f"{data.m_Name}.obj")
        try:
            mesh_data = data.export()
        except (AttributeError, OSError, RuntimeError, ValueError) as exc:
            raise RuntimeError(f"Cannot export mesh {data.m_Name}: {exc}") from exc
        self.__save("mesh", file_path, mesh_data)

    def _extract_generic_object(
        self,
        obj: Any,
        obj_type: str,
        counter: dict[str, int],
        extract_folder: str,
    ) -> None:
        parsed = obj.parse_as_dict()
        name = parsed.get("m_Name") or obj.container or obj.assets_file.name
        file_name = f"{obj_type}_{Path(str(name)).name}_{counter[obj_type]}.json"
        counter[obj_type] += 1
        self.__save("json", str(Path(extract_folder) / file_name), parsed)

