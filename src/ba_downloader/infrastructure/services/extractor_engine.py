import multiprocessing
import os
import time
from multiprocessing import Queue, freeze_support
from os import path

from ba_downloader.extractors.bundle import BundleExtractor
from ba_downloader.extractors.media import MediaExtractor
from ba_downloader.extractors.table import TableExtractor
from ba_downloader.lib.compiler import CompileToPython, CSParser
from ba_downloader.lib.console import ProgressBar, bar_increase, bar_text, notice, print
from ba_downloader.lib.dumper import IL2CppDumper
from ba_downloader.utils.config import Config
from ba_downloader.utils.util import FileUtils, TaskManager


class FlatbufferExtractor:
    DUMP_PATH = "Dumps"
    IL2CPP_NAME = "libil2cpp.so"
    METADATA_NAME = "global-metadata.dat"

    @property
    def fb_data_dir(self) -> str:
        return path.join(Config.extract_dir, "FlatData")

    @property
    def dump_cs_file_path(self) -> str:
        return path.join(Config.extract_dir, self.DUMP_PATH, "dump.cs")

    def dump(self) -> None:
        save_path = Config.temp_dir
        dumper = IL2CppDumper()
        print("Downloading il2cpp-dumper...")
        dumper.get_il2cpp_dumper(save_path)

        il2cpp_path = FileUtils.find_files(Config.temp_dir, [self.IL2CPP_NAME], True)
        metadata_path = FileUtils.find_files(Config.temp_dir, [self.METADATA_NAME], True)

        if not (il2cpp_path and metadata_path):
            raise FileNotFoundError(
                "Cannot find il2cpp binary file or global-metadata file. Make sure exist."
            )

        abs_il2cpp_path = path.abspath(il2cpp_path[0])
        abs_metadata_path = path.abspath(metadata_path[0])
        extract_path = path.abspath(path.join(Config.extract_dir, self.DUMP_PATH))

        print("Try to dump il2cpp...")
        dumper.dump_il2cpp(extract_path, abs_il2cpp_path, abs_metadata_path, Config.retries)
        notice("Dump il2cpp binary file successfully.")

    def compile(self) -> None:
        print("Parsing dump.cs...")
        parser = CSParser(self.dump_cs_file_path)
        enums = parser.parse_enum()
        structs = parser.parse_struct()

        print("Generating flatbuffer python dump files...")
        compiler = CompileToPython(enums, structs, self.fb_data_dir)
        compiler.create_enum_files()
        compiler.create_struct_files()
        compiler.create_module_file()
        compiler.create_dump_dict_file()


class BundlesExtractor:
    @staticmethod
    def extract() -> None:
        bundle_folder = path.join(Config.raw_dir, "Bundle")
        if not path.exists(bundle_folder):
            return

        freeze_support()
        extractor = BundleExtractor()
        queue: multiprocessing.queues.Queue[str] = Queue()
        bundles = os.listdir(bundle_folder)
        for bundle in bundles:
            queue.put(path.join(bundle_folder, bundle))

        with ProgressBar(len(bundles), "Extracting bundle...", "items") as bar:
            processes = [
                multiprocessing.Process(
                    target=extractor.multiprocess_extract_worker,
                    args=(queue, extractor.MAIN_EXTRACT_TYPES),
                )
                for _ in range(5)
            ]
            for process in processes:
                process.start()

            try:
                while not queue.empty():
                    bar.set_progress_value(bar.total - queue.qsize())
                    time.sleep(0.1)
                notice("Extract bundles successfully.")
            except KeyboardInterrupt:
                notice("Bundle extract task has been canceled.", "error")
                for process in processes:
                    process.kill()


class MediasExtractor:
    def __init__(self) -> None:
        self.extractor = MediaExtractor()

    def __extract_worker(self, task_manager: TaskManager) -> None:
        while not (task_manager.tasks.empty() or task_manager.stop_task):
            zip_path = task_manager.tasks.get()
            bar_text(path.basename(zip_path))
            self.extractor.extract_zip(zip_path)
            task_manager.tasks.task_done()
            bar_increase()

    def extract_zips(self) -> None:
        media_folder = path.join(Config.raw_dir, "Media")
        if not path.exists(media_folder):
            return

        files = FileUtils.find_files(media_folder, [".zip"])
        with ProgressBar(len(files), "Extracting media...", "items"):
            with TaskManager(8, Config.max_threads, self.__extract_worker) as extract_task:
                extract_task.set_cancel_callback(
                    notice,
                    "Media extract task has been canceled.",
                    "error",
                )
                extract_task.import_tasks(files)
                extract_task.run()


class TablesExtractor(TableExtractor):
    def __init__(self) -> None:
        table_folder = path.join(Config.raw_dir, "Table")
        table_extract_folder = path.join(Config.extract_dir, "Table")
        super().__init__(table_folder, table_extract_folder, f"{Config.extract_dir}.FlatData")

    def __extract_worker(self, task_manager: TaskManager) -> None:
        while not (task_manager.stop_task or task_manager.tasks.empty()):
            table_file = task_manager.tasks.get()
            ProgressBar.item_text(table_file)
            self.extract_table(table_file)
            task_manager.tasks.task_done()
            ProgressBar.increase()

    def extract_tables(self) -> None:
        if not path.exists(self.table_file_folder):
            return

        os.makedirs(self.extract_folder, exist_ok=True)
        table_files = os.listdir(self.table_file_folder)
        with ProgressBar(len(table_files), "Extracting Table file...", "items"):
            with TaskManager(Config.threads, Config.max_threads, self.__extract_worker) as extract_task:
                extract_task.set_cancel_callback(
                    notice,
                    "Table extract task has been canceled.",
                    "error",
                )
                extract_task.import_tasks(table_files)
                extract_task.run()
