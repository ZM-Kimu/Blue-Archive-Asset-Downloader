import argparse
import os
from typing import Literal

# import json

# Commandline Arguments
parser = argparse.ArgumentParser(description="Blue Archive Resource Donwloader")
parser.add_argument_group("Required Arguments").add_argument(
    "--region",
    "-g",
    type=str,
    choices=["cn", "gl", "jp"],
    help="Server region: cn/gl/jp",
    required=True,
)
# Optional
parser.add_argument(
    "--threads", "-t", type=int, help="Number of download threads", default=20
)
parser.add_argument(
    "--version",
    "-v",
    type=str,
    help="Game version, automatically retrieved if not specified",
    default="",
)
parser.add_argument(
    "--raw", "-r", type=str, help="Output location for raw files", default="RawData"
)
parser.add_argument(
    "--extract",
    "-e",
    type=str,
    help="Output location for extracted files",
    default="Extracted",
)
parser.add_argument(
    "--temporary",
    "-m",
    type=str,
    help="Output location for temporary files",
    default="Temp",
)
parser.add_argument(
    "--downloading-extract",
    "-de",
    action="store_true",
    help="Extract files while downloading",
)

parser.add_argument(
    "--resource-type",
    "-rt",
    choices=["table", "media", "bundle", "all"],
    nargs="*",
    help="Specify the resource type to be processed, with options including table, media, bundle, and all.",
    default=["all"],
)

parser.add_argument(
    "--proxy",
    "-p",
    type=str,
    help="Set HTTP proxy for downloading",
    default="",
)
parser.add_argument(
    "--max-retries",
    "-mr",
    type=int,
    help="Maximum number of retries during download",
    default=5,
)
parser.add_argument(
    "--search",
    "-s",
    type=str,
    help="Search for files using keywords.",
    nargs="*",
    default=[],
)

parser.add_argument(
    "--advance-search",
    "-as",
    type=str,
    help="Advanced search, using character keywords to specify the files to be searched and downloaded.",
    nargs="*",
    default=[],
)

args = parser.parse_args()


# Basic configuration for next steps.
class Config:
    threads: int = args.threads
    version: str = args.version
    region: Literal["cn", "gl", "jp"] = args.region.lower()
    raw_dir: str = args.raw
    extract_dir: str = args.extract
    temp_dir: str = args.temporary
    downloading_extract: bool = args.downloading_extract
    resource_type: list[str] = args.resource_type
    search: list[str] = args.search
    advance_search: list[str] = args.advance_search
    proxy: dict | None = (
        {"http": args.proxy, "https": args.proxy} if args.proxy else None
    )
    retries: int = args.max_retries
    work_dir: str = os.getcwd()
    max_threads: int = threads * 7

    temp_dir = (
        temp_dir
        if temp_dir != parser.get_default("temporary")
        else f"{region.upper()}{temp_dir}"
    )
    raw_dir = (
        raw_dir
        if raw_dir != parser.get_default("raw")
        else f"{region.upper()}{raw_dir}"
    )
    extract_dir = (
        extract_dir
        if extract_dir != parser.get_default("extract")
        else f"{region.upper()}{extract_dir}"
    )

    if "all" in resource_type:
        resource_type = ["table", "media", "bundle"]
