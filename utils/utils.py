import hashlib
import math
import struct
from binascii import crc32
from threading import Thread
from typing import Any, Generator

from .console import print


# Used to create threads.
def create_thread(target_func: Any, thread_pool: list[Thread], *args, **kwargs) -> None:
    thread = Thread(target=target_func, args=args, kwargs=kwargs)
    thread.start()
    thread_pool.append(thread)


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


# Used to parse the area where the EOCD (End of Central Directory) of the compressed file's central directory is located.
def parse_eocd_area(data: bytes) -> tuple[int, int]:
    eocd_signature = b"\x50\x4b\x05\x06"
    eocd_offset = data.rfind(eocd_signature)
    if eocd_offset == -1:
        raise EOFError("Cannot read the eocd of file.")
    eocd = data[eocd_offset : eocd_offset + 22]
    _, _, _, _, _, cd_size, cd_offset, _ = struct.unpack("<IHHHHIIH", eocd)
    return cd_offset, cd_size


# Used to parse the files contained in the central directory. Use for common apk.
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
        file_name = data[offset + 46 : offset + 46 + file_name_length].decode("utf8")

        file_headers.append(
            {"path": file_name, "offset": local_header_offset, "size": uncomp_size}
        )
        offset += 46 + file_name_length + extra_field_length + file_comment_length

    return file_headers


# Used to split a list into a specified number of parts and return a generator.
def seperate_list_as_blocks(
    content: list, block_num: int
) -> Generator[list, Any, None]:
    for i in range(0, len(content), math.ceil(len(content) / block_num)):
        yield content[i : i + math.ceil(len(content) / block_num)]


def calculate_crc(path: str) -> int:
    """Calculate the crc checksum value of a file.
    Args:
        path (str): File path.
    Returns:
        int: Crc checksum.
    """
    with open(path, "rb") as f:
        return crc32(f.read()) & 0xFFFFFFFF


def calculate_md5(path: str) -> str:
    """Calculate the md5 checksum value of a file.
    Args:
        path (str): File path.
    Returns:
        str: MD5 checksum.
    """
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


# The private function is used to download file from a compressed file within a specified range and decompress it.
def __download_and_decompress_file(
    self, apk_url: str, target_path: str, header_part: bytes, start_offset: int
) -> bool:
    """Request partial data from an online compressed file and then decompress it."""
    try:
        header = struct.unpack("<IHHHHHIIIHH", header_part[:30])
        _, _, _, compression, _, _, _, comp_size, _, file_name_len, extra_len = header
        data_start = start_offset + 30 + file_name_len + extra_len
        data_end = data_start + comp_size
        compressed_data = self.file_downloader(
            apk_url,
            False,
            {"Range": f"bytes={data_start}-{data_end - 1}"},
        )
        return self.extractor.decompress_file_part(
            compressed_data, target_path, compression
        )
    except:
        return False
