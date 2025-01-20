import json
import os
import re
from os import path

from lib.console import notice, print
from lib.diagnosis import is_dotnet_sdk_version_equal
from lib.downloader import FileDownloader
from utils.config import Config
from utils.util import extract_zip, find_files, run_command

IL2CPP_ZIP = "https://github.com/Perfare/Il2CppDumper/archive/refs/heads/master.zip"
DUMP_PATH = "Dumps"
IL2CPP_FOLDER = "Il2CppDumper-master"


class FlatBufferDumper:
    def __init__(self):
        pass

    def main(self) -> None:
        notice("Verify environment...")
        if not is_dotnet_sdk_version_equal(8):
            raise FileNotFoundError(
                "Error: .NET8 SDK is not installed or 'dotnet' is not in the PATH or .NET major version is not 8. Download it from: https://dotnet.microsoft.com/download",
            )
        il2cpp_path = self.get_il2cpp_dumper()
        self.dump_il2cpp(il2cpp_path)

    def get_il2cpp_dumper(self) -> str:
        notice("Download il2cpp-dumper...")
        zip_name = "il2cpp-dumper.zip"
        FileDownloader(IL2CPP_ZIP).save_file(path.join(Config.temp_dir, zip_name))
        extract_zip(path.join(Config.temp_dir, zip_name), Config.temp_dir)

        if config_path := find_files(
            path.join(Config.temp_dir, IL2CPP_FOLDER), ["config.json"], True
        ):
            with open(
                config_path[0],
                "r+",
                encoding="utf8",
            ) as config:
                il2cpp_config: dict = json.load(config)
                il2cpp_config["RequireAnyKey"] = False
                il2cpp_config["GenerateDummyDll"] = False
                config.seek(0)
                config.truncate()
                json.dump(il2cpp_config, config)

            return path.dirname(config_path[0])

        raise FileNotFoundError(
            "Cannot find config file. Make sure il2cpp-dumper exsist."
        )

    def dump_il2cpp(self, project_work_directory: str) -> None:
        notice("Try to dump il2cpp...")
        libil2cpp_binary_path = find_files(Config.temp_dir, ["libil2cpp.so"], True)
        global_metadata_path = find_files(
            Config.temp_dir, ["global-metadata.dat"], True
        )
        if not (libil2cpp_binary_path and global_metadata_path):
            raise FileNotFoundError(
                "Cannot find il2cpp binary file or global-metadata file. Make sure exist."
            )

        abs_il2cpp_bin_path = path.abspath(libil2cpp_binary_path[0])
        abs_global_meta_path = path.abspath(global_metadata_path[0])

        extract_path = path.abspath(path.join(Config.extract_dir, DUMP_PATH))

        os.makedirs(extract_path, exist_ok=True)

        if not run_command(
            "dotnet",
            "run",
            "--framework",
            "net8.0",
            abs_il2cpp_bin_path,
            abs_global_meta_path,
            extract_path,
            cwd=project_work_directory,
        ):
            raise RuntimeError(
                "Error occurred during dump the lib2cpp file. Retry might solve this issue."
            )

        notice("Dump il2cpp binary file successfully.")


class FlatBufferConvertion:
    re_struct = re.compile(
        r"""struct (\w+) \{
(.+?)
\}
""",
        re.M | re.S,
    )
    re_field = re.compile(r"public (.+?) (.+?) = (-?\d+);")

    reEnum = re.compile(
        r"""
                        public enum (\w+) \{(.+?)\}""",
        re.S,
    )
