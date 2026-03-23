import multiprocessing
import multiprocessing.context
import multiprocessing.queues
import multiprocessing.synchronize
import os
import time
from multiprocessing import Queue, freeze_support
from os import path

from lib.compiler import CompileToPython, CSParser
from lib.console import ProgressBar, bar_increase, bar_text, notice, print
from lib.dumper import IL2CppDumper
from utils.config import Config
from utils.util import FileUtils, TaskManager
from xtractor.bundle import BundleExtractor
from xtractor.media import MediaExtractor
from xtractor.table import TableExtractor


class FlatbufferExtractor:
    DUMP_PATH = "Dumps"
    IL2CPP_NAME = "libil2cpp.so"
    METADATA_NAME = "global-metadata.dat"

    FB_DATA_DIR = path.join(Config.extract_dir, "FlatData")
    DUMP_CS_FILE_PATH = path.join(Config.extract_dir, DUMP_PATH, "dump.cs")

    def dump(self) -> None:
        """Dump unity lib from il2cpp.so and global-metadata.dat"""
        save_path = Config.temp_dir
        dumper = IL2CppDumper()
        print("Downloading il2cpp-dumper...")
        dumper.get_il2cpp_dumper(save_path)

        il2cpp_path = FileUtils.find_files(Config.temp_dir, [self.IL2CPP_NAME], True)
        metadata_path = FileUtils.find_files(
            Config.temp_dir, [self.METADATA_NAME], True
        )

        if not (il2cpp_path and metadata_path):
            raise FileNotFoundError(
                "Cannot find il2cpp binary file or global-metadata file. Make sure exist."
            )
        abs_il2cpp_path = path.abspath(il2cpp_path[0])
        abs_metadata_path = path.abspath(metadata_path[0])

        extract_path = path.abspath(path.join(Config.extract_dir, self.DUMP_PATH))

        print("Try to dump il2cpp...")
        dumper.dump_il2cpp(
            extract_path, abs_il2cpp_path, abs_metadata_path, Config.retries
        )
        notice("Dump il2cpp binary file successfully.")

    def compile(self) -> None:
        """Compile python callable module from dump file"""
        print("Parsing dump.cs...")
        parser = CSParser(self.DUMP_CS_FILE_PATH)
        enums = parser.parse_enum()
        structs = parser.parse_struct()

        print("Generating flatbuffer python dump files...")
        compiler = CompileToPython(enums, structs, self.FB_DATA_DIR)
        compiler.create_enum_files()
        compiler.create_struct_files()
        compiler.create_module_file()
        compiler.create_dump_dict_file()


class BundlesExtractor:
    @staticmethod
    def extract() -> None:
        """Extract bundles."""
        if not path.exists(BundleExtractor.BUNDLE_FOLDER):
            return
        freeze_support()
        extractor = BundleExtractor()
        queue: multiprocessing.queues.Queue = Queue()
        bundles = os.listdir(extractor.BUNDLE_FOLDER)
        for bundle in bundles:
            queue.put(path.join(extractor.BUNDLE_FOLDER, bundle))
        with ProgressBar(len(bundles), "Extracting bundle...", "items") as bar:
            processes = [
                multiprocessing.Process(
                    target=extractor.multiprocess_extract_worker,
                    args=(queue, extractor.MAIN_EXTRACT_TYPES),
                )
                for _ in range(5)
            ]
            for p in processes:
                p.start()
            try:
                while not queue.empty():
                    bar.set_progress_value(bar.total - queue.qsize())
                    time.sleep(0.1)
                notice("Extract bundles successfully.")
            except KeyboardInterrupt:
                notice("Bundle extract task has been canceled.", "error")
                for p in processes:
                    p.kill()


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
        """Extract all media zips from media folder."""
        extractor = MediaExtractor()
        if not path.exists(extractor.MEDIA_FOLDER):
            return
        files = FileUtils.find_files(extractor.MEDIA_FOLDER, [".zip"])
        with ProgressBar(len(files), "Extracting media...", "items"):
            with TaskManager(8, Config.max_threads, self.__extract_worker) as e_zips:
                e_zips.set_cancel_callback(
                    notice, "Media extract task has been canceled.", "error"
                )
                e_zips.import_tasks(files)
                e_zips.run()


class TablesExtractor(TableExtractor):
    TABLE_FOLDER = path.join(Config.raw_dir, "Table")
    TABLE_EXTRACT_FOLDER = path.join(Config.extract_dir, "Table")

    def __init__(self) -> None:
        super().__init__(
            self.TABLE_FOLDER,
            self.TABLE_EXTRACT_FOLDER,
            f"{Config.extract_dir}.FlatData",
        )

    def __extract_worker(self, task_manager: TaskManager) -> None:
        while not (task_manager.stop_task or task_manager.tasks.empty()):
            table_file = task_manager.tasks.get()
            ProgressBar.item_text(table_file)
            self.extract_table(table_file)
            table_file = task_manager.tasks.task_done()
            ProgressBar.increase()

    def extract_tables(self) -> None:
        """Extract table with multi-thread"""
        if not path.exists(self.TABLE_FOLDER):
            return
        os.makedirs(self.TABLE_EXTRACT_FOLDER, exist_ok=True)
        table_files = os.listdir(self.TABLE_FOLDER)
        with ProgressBar(len(table_files), "Extracting Table file...", "items"):
            with TaskManager(
                Config.threads, Config.max_threads, self.__extract_worker
            ) as e_task:
                e_task.set_cancel_callback(
                    notice, "Table extract task has been canceled.", "error"
                )
                e_task.import_tasks(table_files)
                e_task.run()


if __name__ == "__main__":
    if Config.region == "cn":
        BundlesExtractor().extract()
    if Config.region == "jp":
        if "table" in Config.resource_type:
            TablesExtractor().extract_tables()
        if "bundle" in Config.resource_type:
            BundlesExtractor.extract()
        if "media" in Config.resource_type:
            MediasExtractor().extract_zips()
