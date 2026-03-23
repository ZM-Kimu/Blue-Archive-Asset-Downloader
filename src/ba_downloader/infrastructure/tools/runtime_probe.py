"""Diagnose whether required runtimes are available."""

import subprocess


def is_dotnet_sdk_version_equal(*target_versions: int) -> bool:
    """Checks if the installed .NET SDK major version matches the specified target version.

    Args:
        target_versions (int): Major versions to check against (e.g. 8 for .NET 8.x.x).

    Returns:
        bool: Is or not installed specified sdk version.
    """
    try:
        result = subprocess.run(
            ["dotnet", "--list-sdks"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        stdout = result.stdout.split("\n")
        if stdout:
            major_versions = [
                ver[0]
                for ver in stdout
                if ver and ver[0].isdigit() and int(ver[0]) in target_versions
            ]
            return bool(major_versions)
        return False
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False



