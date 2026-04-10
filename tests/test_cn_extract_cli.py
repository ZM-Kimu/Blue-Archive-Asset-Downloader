from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path


ANSI_ESCAPE_PATTERN = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")


def _build_corrupt_unityfs_bundle() -> bytes:
    return (
        b"UnityFS\x00"
        b"6.x.x\x00"
        b"2021.3.0f1\x00"
        b"1234\x00"
        b"\x00\x00\x00\x20"
        b"\x00\x00\x00\x20"
        b"\x00\x00\x00\x00"
        b"\x00\x00\x00\x03"
        b"broken-data"
    )


def _run_cn_extract(
    repo_root: Path,
    raw_dir: Path,
    extract_dir: Path,
    temp_dir: Path,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        "-m",
        "ba_downloader",
        "extract",
        "--region",
        "cn",
        "--threads",
        "1",
        "--raw-dir",
        str(raw_dir),
        "--extract-dir",
        str(extract_dir),
        "--temp-dir",
        str(temp_dir),
    ]
    env = os.environ.copy()
    env["NO_COLOR"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    env["TERM"] = "dumb"
    return subprocess.run(
        command,
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )


def _normalize_console_output(output: str) -> str:
    normalized = ANSI_ESCAPE_PATTERN.sub("", output)
    normalized = normalized.replace("\r", "\n")
    return normalized


def test_cn_extract_reports_corrupt_bundle_failures_without_traceback(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    raw_dir = tmp_path / "RawData"
    extract_dir = tmp_path / "Extracted"
    temp_dir = tmp_path / "Temp"
    bundle_dir = raw_dir / "Bundle"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    (bundle_dir / "corrupt.bundle").write_bytes(_build_corrupt_unityfs_bundle())

    result = _run_cn_extract(repo_root, raw_dir, extract_dir, temp_dir)
    output = _normalize_console_output(result.stdout + result.stderr)

    assert result.returncode == 0
    assert "Failed to extract bundle" in output
    assert "corrupt.bundle" in output
    assert "Extracted bundles with 1 errors." in output
    assert "Extracted bundles successfully." not in output
    assert "Traceback (most recent call last):" not in output
    assert "Process Process-" not in output


def test_cn_extract_summarizes_multiple_bundle_failures(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    raw_dir = tmp_path / "RawData"
    extract_dir = tmp_path / "Extracted"
    temp_dir = tmp_path / "Temp"
    bundle_dir = raw_dir / "Bundle"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    corrupt_payload = _build_corrupt_unityfs_bundle()
    (bundle_dir / "corrupt_a.bundle").write_bytes(corrupt_payload)
    (bundle_dir / "corrupt_b.bundle").write_bytes(corrupt_payload)

    result = _run_cn_extract(repo_root, raw_dir, extract_dir, temp_dir)
    output = _normalize_console_output(result.stdout + result.stderr)

    assert result.returncode == 0
    assert output.count("Failed to extract bundle") >= 2
    assert "Extracted bundles with 2 errors." in output
    assert "Extracted bundles successfully." not in output
