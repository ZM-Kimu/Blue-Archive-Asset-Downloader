"""Diagnose whether required runtimes are available."""

import subprocess


def get_installed_dotnet_sdk_major_versions() -> set[int]:
    """Return installed .NET SDK major versions."""
    try:
        result = subprocess.run(
            ["dotnet", "--list-sdks"],
            capture_output=True,
            text=True,
            check=True,
        )
        majors: set[int] = set()
        for line in result.stdout.splitlines():
            if not line:
                continue
            major_text = line.split(".", 1)[0]
            if major_text.isdigit():
                majors.add(int(major_text))
        return majors
    except (FileNotFoundError, subprocess.CalledProcessError):
        return set()


def is_dotnet_sdk_version_equal(*target_versions: int) -> bool:
    """Checks if the installed .NET SDK major version matches the specified target version.

    Args:
        target_versions (int): Major versions to check against (e.g. 8 for .NET 8.x.x).

    Returns:
        bool: Is or not installed specified sdk version.
    """
    installed = get_installed_dotnet_sdk_major_versions()
    return any(version in installed for version in target_versions)
