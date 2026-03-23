"""Dump il2cpp file to csharp file."""

import json
import subprocess
from pathlib import Path
from zipfile import ZipFile

from ba_downloader.domain.ports.http import HttpClientPort
from ba_downloader.infrastructure.tools.runtime_probe import is_dotnet_sdk_version_equal

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

    def get_il2cpp_dumper(self, http_client: HttpClientPort, save_path: str) -> None:
        """Download il2cpp-dumper from github.

        Args:
            save_path (str): Path to save il2cpp-dumper.

        Raises:
            FileNotFoundError: Raise error when il2cpp-dumper config file cannot found.

        """
        save_dir = Path(save_path)
        save_dir.mkdir(parents=True, exist_ok=True)
        archive_path = save_dir / ZIP_NAME
        http_client.download_to_file(IL2CPP_ZIP, str(archive_path))
        with ZipFile(archive_path, "r") as archive:
            archive.extractall(save_dir)

        config_matches = list((save_dir / IL2CPP_FOLDER).rglob("config.json"))
        if not config_matches:
            raise FileNotFoundError(
                "Cannot find config file. Make sure il2cpp-dumper exsist."
            )

        config_path = config_matches[0]
        with config_path.open("r+", encoding="utf8") as config:
            il2cpp_config: dict = json.load(config)
            il2cpp_config["RequireAnyKey"] = False
            il2cpp_config["GenerateDummyDll"] = False
            config.seek(0)
            config.truncate()
            json.dump(il2cpp_config, config)

        self.project_dir = str(config_path.parent)

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

        Path(extract_path).mkdir(parents=True, exist_ok=True)

        try:
            subprocess.run(
                [
                    "dotnet",
                    "run",
                    "--framework",
                    "net8.0",
                    il2cpp_path,
                    global_metadata_path,
                    extract_path,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                text=True,
                cwd=self.project_dir,
                encoding="utf8",
            )
        except Exception as exc:
            if max_retries == 0:
                raise RuntimeError(
                    f"Error occurred during dump the lib2cpp file. Retry might solve this issue. Info: {exc}"
                )
            return self.dump_il2cpp(
                extract_path, il2cpp_path, global_metadata_path, max_retries - 1
            )

        return None

