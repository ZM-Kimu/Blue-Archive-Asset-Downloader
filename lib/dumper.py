"""Dump il2cpp file to csharp file."""

import json
import os
from os import path

from lib.diagnosis import is_dotnet_sdk_version_equal
from lib.downloader import FileDownloader
from utils.util import CommandUtils, FileUtils, ZipUtils

IL2CPP_ZIP = "https://github.com/Perfare/Il2CppDumper/archive/refs/heads/master.zip"
IL2CPP_FOLDER = "Il2CppDumper-master"
ZIP_NAME = "il2cpp-dumper.zip"


class IL2CppDumper:

    def __init__(self) -> None:
        self.project_dir = ""

        if not is_dotnet_sdk_version_equal(8):
            raise FileNotFoundError(
                "Error: .NET8 SDK is not installed or 'dotnet' is not in the PATH or .NET major version is not 8. Download it from: https://dotnet.microsoft.com/download",
            )

    def get_il2cpp_dumper(self, save_path: str) -> None:
        """Download il2cpp-dumper from github.

        Args:
            save_path (str): Path to save il2cpp-dumper.

        Raises:
            FileNotFoundError: Raise error when il2cpp-dumper config file cannot found.

        """
        FileDownloader(IL2CPP_ZIP).save_file(path.join(save_path, ZIP_NAME))
        ZipUtils.extract_zip(path.join(save_path, ZIP_NAME), save_path)

        if not (
            config_path := FileUtils.find_files(
                path.join(save_path, IL2CPP_FOLDER), ["config.json"], True
            )
        ):
            raise FileNotFoundError(
                "Cannot find config file. Make sure il2cpp-dumper exsist."
            )

        with open(config_path[0], "r+", encoding="utf8") as config:
            il2cpp_config: dict = json.load(config)
            il2cpp_config["RequireAnyKey"] = False
            il2cpp_config["GenerateDummyDll"] = False
            config.seek(0)
            config.truncate()
            json.dump(il2cpp_config, config)

        self.project_dir = path.dirname(config_path[0])

    def dump_il2cpp(
        self,
        extract_path: str,
        il2cpp_path: str,
        global_metadata_path: str,
        max_retries: int = 1,
    ) -> None:
        """Dump il2cpp with using il2cpp-dumper.
        Args:
            extract_path (str): Absolute path to extract dump file.
            il2cpp_path (str): Absolute path to il2cpp lib.
            global_metadata_path (str): Absolute path to global metadata.
            max_retries (int): Max retry count for dump when dump failed.


        Raises:
            RuntimeError: Raise error when dump unsuccess.
        """

        os.makedirs(extract_path, exist_ok=True)

        success, err = CommandUtils.run_command(
            "dotnet",
            "run",
            "--framework",
            "net8.0",
            il2cpp_path,
            global_metadata_path,
            extract_path,
            cwd=self.project_dir,
        )
        if not success:
            if max_retries == 0:
                raise RuntimeError(
                    f"Error occurred during dump the lib2cpp file. Retry might solve this issue. Info: {err}"
                )
            return self.dump_il2cpp(
                extract_path, il2cpp_path, global_metadata_path, max_retries - 1
            )

        return None
