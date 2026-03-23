import concurrent.futures
import math
import os
import struct
import subprocess
import zlib
from concurrent.futures import ThreadPoolExecutor
from keyword import kwlist
from queue import Queue
from threading import Event, Lock, Thread
from time import sleep
from typing import Any, Callable, Generator, Iterable, Literal, Protocol
from zipfile import ZipFile

import UnityPy
from UnityPy.files.File import ObjectReader

from lib.console import ProgressBar, notice, print
from lib.downloader import FileDownloader
from lib.structure import Resource, ResourceItem


class ZipUtils:
    @staticmethod
    def extract_zip(
        zip_path: str | list[str],
        dest_dir: str,
        *,
        keywords: list[str] | None = None,
        zips_dir: str = "",
        password: bytes = bytes(),
        progress_bar: bool = True,
    ) -> list[str]:
        """Extracts specific files from a zip archive(s) to a destination directory.

        Args:
            zip_path (str | list[str]): Path(s) to the zip file(s).
            dest_dir (str): Directory where files will be extracted.
            keywords (list[str], optional): List of keywords to filter files for extraction. Defaults to None.
            zips_dir (str, optional): Base directory for relative paths when zip_path is a list. Defaults to "".
            progress_bar (str, optional): Create a progress bar during extract. Defaults to False.


        Returns:
            list[str]: List of extracted file paths.
        """
        if progress_bar:
            print(f"Extracting files from {zip_path} to {dest_dir}...")
        extract_list: list[str] = []
        zip_files = []

        if isinstance(zip_path, str):
            zip_files = [zip_path]
        elif isinstance(zip_path, list):
            zip_files = [os.path.join(zips_dir, p) for p in zip_path]

        os.makedirs(dest_dir, exist_ok=True)

        if progress_bar:
            bar = ProgressBar(len(extract_list), "Extract...", "items")
        for zip_file in zip_files:
            try:
                with ZipFile(zip_file, "r") as z:
                    z.setpassword(password)
                    if keywords:
                        extract_list = [
                            item for k in keywords for item in z.namelist() if k in item
                        ]
                        for item in extract_list:
                            try:
                                z.extract(item, dest_dir)
                            except Exception as e:
                                notice(str(e))
                            if progress_bar:
                                bar.increase()
                    else:
                        z.extractall(dest_dir)

            except Exception as e:
                notice(f"Error processing file '{zip_file}': {e}")
        if progress_bar:
            bar.stop()
        return extract_list

    # Used to parse the area where the EOCD (End of Central Directory) of the compressed file's central directory is located.
    @staticmethod
    def parse_eocd_area(data: bytes) -> tuple[int, int]:
        eocd_signature = b"\x50\x4b\x05\x06"
        eocd_offset = data.rfind(eocd_signature)
        if eocd_offset == -1:
            raise EOFError("Cannot read the eocd of file.")
        eocd = data[eocd_offset : eocd_offset + 22]
        _, _, _, _, _, cd_size, cd_offset, _ = struct.unpack("<IHHHHIIH", eocd)
        return cd_offset, cd_size

    # Used to parse the files contained in the central directory. Use for common apk.
    @staticmethod
    def parse_central_directory_data(data: bytes) -> list:
        file_headers = []
        offset = 0
        while offset < len(data):
            if data[offset : offset + 4] != b"\x50\x4b\x01\x02":
                raise BufferError("Cannot parse the central directory of file.")
            pack = struct.unpack("<IHHHHHHIIIHHHHHII", data[offset : offset + 46])

            uncomp_size = pack[9]
            file_name_length = pack[10]
            extra_field_length = pack[11]
            file_comment_length = pack[12]
            local_header_offset = pack[16]
            file_name = data[offset + 46 : offset + 46 + file_name_length].decode(
                "utf8"
            )

            file_headers.append(
                {"path": file_name, "offset": local_header_offset, "size": uncomp_size}
            )
            offset += 46 + file_name_length + extra_field_length + file_comment_length

        return file_headers

    @staticmethod
    def download_and_decompress_file(
        apk_url: str, target_path: str, header_part: bytes, start_offset: int
    ) -> bool:
        """Request partial data from an online compressed file and then decompress it."""
        try:
            header = struct.unpack("<IHHHHHIIIHH", header_part[:30])
            _, _, _, compression, _, _, _, comp_size, _, file_name_len, extra_len = (
                header
            )
            data_start = start_offset + 30 + file_name_len + extra_len
            data_end = data_start + comp_size
            compressed_data = FileDownloader(
                apk_url,
                headers={"Range": f"bytes={data_start}-{data_end - 1}"},
            )
            return ZipUtils.decompress_file_part(
                compressed_data, target_path, compression
            )
        except:
            return False

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


class UnityUtils:
    @staticmethod
    def search_unity_pack(
        pack_path: str,
        data_type: list | None = None,
        data_name: list | None = None,
        condition_connect: bool = False,
        read_obj_anyway: bool = False,
    ) -> list[ObjectReader] | None:
        """Search specified data from unity pack.

        Args:
            pack_path (str): File path.
            data_type (list | None, optional): Data types to search. Defaults to None.
            data_name (list | None, optional): Data name to search. Defaults to None.
            condition_connect (bool, optional): Connect data type and data name as unique condition. Defaults to False.
            read_obj_anyway (bool, optional): Data type does not match but read data name anyway. Defaults to False.

        Returns:
            list[UnityPy.environment.ObjectReader] | None: A list of UnityPy object.
        """
        data_list: list[ObjectReader] = []
        type_passed = False
        try:
            env = UnityPy.load(pack_path)
            for obj in env.objects:
                if data_type and obj.type.name in data_type:
                    if condition_connect:
                        type_passed = True
                    else:
                        data_list.append(obj)
                if read_obj_anyway or type_passed:
                    data = obj.read()
                    if data_name and data.m_Name in data_name:
                        if not (condition_connect or type_passed):
                            continue
                        data_list.append(obj)
        except:
            pass
        return data_list


class FileUtils:
    @staticmethod
    def find_files(
        directory: str,
        keywords: list[str],
        absolute_match: bool = False,
        sequential_match: bool = False,
    ) -> list[str]:
        """Retrieve files from a given directory based on specified keywords of file name.

        Args:
            directory (str): The directory to search for files.
            keywords (list[str]): A list of keywords to match file names.
            absolute_match (bool, optional): If True, matches file names exactly with the keywords. If False, performs a partial match (i.e., checks if any keyword is a substring of the file name). Defaults to False.
            sequential_match (bool, optional): If True, the final list will be matched sequentially based on the order of the provided keywords. If a keyword has multiple values, only one will be retained. A keyword that no result to be retrieved will correspond to a None value. Defaults to False.
        Returns:
            list[str]: A list of file paths that match the specified criteria.
        """
        paths = []
        for dir_path, _, files in os.walk(directory):
            for file in files:
                if absolute_match and file in keywords:
                    paths.append(os.path.join(dir_path, file))
                elif not absolute_match and any(
                    keyword in file for keyword in keywords
                ):
                    paths.append(os.path.join(dir_path, file))

        if not sequential_match:
            return paths

        sorted_paths = []
        # Sequential match part.
        for key in keywords:
            for p in paths:
                if key in p:
                    sorted_paths.append(p)
                    break

        return sorted_paths


class CommandUtils:
    @staticmethod
    def run_command(
        *commands: str,
        cwd: str | None = None,
    ) -> tuple[bool, str]:
        """
        Executes a shell command and returns whether it succeeded.

        Args:
            *commands (str): Command and its arguments as separate strings.

        Returns:
            tuple (bool, str): True if the command succeeded, False otherwise. And error string.
        """
        try:
            subprocess.run(
                list(commands),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                text=True,
                cwd=cwd,
                encoding="utf8",
            )
            return True, ""
        except Exception as e:
            err = f"Command failed while excute command '{' '.join(list(commands))}' with error: {e}."
            return False, err


class ResourceUtils:
    @staticmethod
    def filter_type(resource: Resource, resource_type: list[str]) -> Resource:
        """Filter the necessary item from the resource_type specified in the Config"""
        if len(resource_type) == 3:
            return resource

        filtered_res = Resource()
        for res in resource:
            if res.resource_type.name in resource_type:
                filtered_res.add_item(res)

        return filtered_res

    @staticmethod
    def search_name(resource: Resource, keywords: list[str]) -> Resource:
        """Search for the specified item in the resource by keywords."""
        results = Resource()

        searched_list: list[ResourceItem] = []
        for keyword in keywords:
            searched_list += resource.search_resource("path", keyword)

        unique_res: dict = {res.path: res for res in searched_list}
        for searched in unique_res.values():
            results.add_item(searched)

        return results


# Used to search for specific keywords in the characters mapping and associate additional keywords with the searched keyword.
def full_text_filter(keywords: str, character_map: dict, content_list: list) -> list:
    print(f'Searching for mapping data with version {character_map["version"]}...')

    new_contents = []
    keyword_list = keywords.split(",").copy()
    key_mapping = character_map["keyword_mapping"]
    file_mapping = character_map["source_file_mapping"]

    for keyword in keyword_list.copy():
        for key in key_mapping:
            if keyword.lower() in key_mapping[key].lower():
                keyword_list.append(key.lower())

    for keyword in keyword_list.copy():
        for file in file_mapping:
            if keyword.lower() in file_mapping[file].lower():
                keyword_list.append(file.lower())

    for content in content_list:
        for keyword in keyword_list:
            if keyword.lower() in content["path"].lower():
                new_contents.append(content)

    return new_contents


class Utils:
    @staticmethod
    def create_thread(
        target_func: Any, thread_pool: list[Thread], *args, **kwargs
    ) -> None:
        thread = Thread(target=target_func, args=args, kwargs=kwargs)
        thread.start()
        thread_pool.append(thread)

    @staticmethod
    def convert_name_to_available(variable_name: str) -> str:
        """Convert varaible name to suitable with python.

        Args:
            variable_name (str): Name.

        Returns:
            str: Available string in python.
        """
        if not variable_name:
            return "_"
        if variable_name[0].isdigit():
            variable_name = "_" + variable_name
        if variable_name in kwlist:
            variable_name = f"{variable_name}_"
        return variable_name

    # Used to split a list into a specified number of parts and return a generator.
    @staticmethod
    def seperate_list_as_blocks(
        content: list, block_num: int
    ) -> Generator[list, Any, None]:
        for i in range(0, len(content), math.ceil(len(content) / block_num)):
            yield content[i : i + math.ceil(len(content) / block_num)]


class TemplateString:
    """
    Template string generator.

    :Example:
    .. code-block:: python
        CONSTANT = TemplateString("What%s a %s %s.")
        CONSTANT("", "fast", "fox")
        "What a fast fox."
    """

    def __init__(self, template: str) -> None:
        self.template = template

    def __call__(self, *args: Any) -> str:
        return self.template % args


class TaskManager:
    class TaskManagerWorkerProtocol(Protocol):
        def __call__(
            self, task_manager: "TaskManager", *args: Any, **kwargs: Any
        ) -> None: ...

    def __init__(
        self,
        target_workers: int,
        max_workers: int,
        worker: TaskManagerWorkerProtocol,
        tasks: Queue[Any] = Queue(),
    ) -> None:
        """A simplified thread pool manager.

        Args:
            max_workers (int): Maximum number of threads to use.
            worker (Callable[..., None]): The worker function executed by each thread.
        """
        self.target_workers = target_workers
        self.max_workers = max_workers
        self.worker = worker
        self.tasks = tasks
        self.stop_task = False
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.futures: list[concurrent.futures.Future] = []
        self.lock = Lock()
        self.event = Event()
        self.conditional_event = Event()
        self.__cancel_callback: tuple[Callable, tuple] | None = None
        self.__pool_condition: Callable = lambda: self.tasks.empty() or self.stop_task
        self.__force_exit = False

    def __enter__(self) -> "TaskManager":
        """Start the worker pool."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Shutdown the worker pool."""
        is_force = self.stop_task or self.__force_exit
        self.executor.shutdown(wait=not is_force, cancel_futures=is_force)

    def __set_conditions(self, func: Callable | None = None) -> None:
        if not func:
            self.__pool_condition = lambda: self.tasks.empty() or self.stop_task
        else:
            self.__pool_condition = func

    def add_worker(self, *args: Any) -> None:
        """Add a task to the worker queue."""
        # Worker must have TaskManager instance at first parameter.
        future = self.executor.submit(self.worker, self, *args)
        self.futures.append(future)

    def increase_worker(self, num: int = 1) -> None:
        """Increase worker with exsist worker parameters."""
        self.target_workers += num

    def set_cancel_callback(self, callback: Callable[..., None], *args) -> None:
        """Set a callback for task canceled."""
        self.__cancel_callback = (callback, args)

    def set_force_shutdown(self, force: bool = True) -> None:
        """Set is or not shutdown without wait."""
        self.__force_exit = force

    def set_relation(
        self, mode: Literal["shut", "constraint"], master_manager: "TaskManager"
    ) -> None:
        """Set a relation to another task by a flag. Use to control task stop condition.

        Args:
            mode (Literal[&quot;shut&quot;, &quot;constraint&quot;]):
                "shut": When the master manager is running, the constrained manager will wait for the master manager to declare termination, but this does not affect the task processing of the constrained manager.
            master_manager (TaskManager): _description_
        """
        if mode == "shut":
            self.conditional_event = master_manager.event
            self.__set_conditions(
                lambda: self.stop_task
                or (self.tasks.empty() and self.conditional_event.is_set())
            )

    def import_tasks(self, tasks: Iterable[Any]) -> None:
        """Import tasks from iterable sequency and set to instance task

        Args:
            tasks (Iterable[Any]): Any iterable elements.
        """
        queue_tasks: Queue[Any] = Queue()
        for task in tasks:
            queue_tasks.put(task)
        self.tasks = queue_tasks

    def run_without_block(self, *worker_args: Any) -> Thread:
        """Same as run and without block."""
        thread = Thread(target=self.run, args=worker_args, daemon=True)
        thread.start()
        return thread

    def run(self, *worker_args: Any) -> None:
        """Start worker and give parameters to worker."""
        try:
            while not self.__pool_condition():
                while len(self.futures) < self.target_workers:
                    self.add_worker(*worker_args)
                self.futures = [f for f in self.futures if not f.done()]
                sleep(0.1)

        except KeyboardInterrupt:
            if self.__cancel_callback:
                self.__cancel_callback[0](*self.__cancel_callback[1])
            self.stop_task = True
            while not self.tasks.empty():
                self.tasks.get()
                self.tasks.task_done()
            self.executor.shutdown(wait=False, cancel_futures=True)
        finally:
            self.event.set()
            if not self.__force_exit:
                for future in self.futures:
                    future.result()

    def done(self) -> None:
        """Finish thread pool manually."""
        self.__exit__(None, None, None)
