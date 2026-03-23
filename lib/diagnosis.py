"""Diagnose the environment is available in different conditions."""

import subprocess


def is_dotnet_sdk_version_equal(target_version: int) -> bool:
    """Checks if the installed .NET SDK major version matches the specified target version.

    Args:
        target_version (int): The major version of the .NET SDK to check against (e.g., 7 for .NET 7.x.x).

    Returns:
        bool: Is or not installed specified sdk version.
    """
    try:
        result = subprocess.run(
            ["dotnet", "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        stdout = result.stdout.strip()
        if stdout:
            major_version = stdout.split(".")[0]
            if major_version.isdigit():
                return int(major_version) == target_version
        return False
    except:
        return False
