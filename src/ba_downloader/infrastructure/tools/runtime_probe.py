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
