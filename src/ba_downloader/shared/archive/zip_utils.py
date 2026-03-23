import struct
import zlib
from zipfile import ZipFile

from ba_downloader.lib.console import ProgressBar, notice, print
from ba_downloader.lib.downloader import FileDownloader


class ZipUtils:
    @staticmethod
    def extract_zip(
        zip_path: str | list[str],
        dest_dir: str,
        *,
        keywords: list[str] | None = None,
        zips_dir: str = "",
        password: bytes = bytes(),
        progress_bar: bool = True,
    ) -> list[str]:
        if progress_bar:
            print(f"Extracting files from {zip_path} to {dest_dir}...")
        extract_list: list[str] = []
        zip_files = []

        if isinstance(zip_path, str):
            zip_files = [zip_path]
        elif isinstance(zip_path, list):
            zip_files = [f"{zips_dir}/{p}" for p in zip_path]

        if progress_bar:
            bar = ProgressBar(len(extract_list), "Extract...", "items")

        for zip_file in zip_files:
            try:
                with ZipFile(zip_file, "r") as zip_file_handle:
                    zip_file_handle.setpassword(password)
                    if keywords:
                        extract_list = [
                            item
                            for key in keywords
                            for item in zip_file_handle.namelist()
                            if key in item
                        ]
                        for item in extract_list:
                            try:
                                zip_file_handle.extract(item, dest_dir)
                            except Exception as extract_error:
                                notice(str(extract_error))
                            if progress_bar:
                                bar.increase()
                    else:
                        zip_file_handle.extractall(dest_dir)
            except Exception as zip_error:
                notice(f"Error processing file '{zip_file}': {zip_error}")

        if progress_bar:
            bar.stop()
        return extract_list

    @staticmethod
    def parse_eocd_area(data: bytes) -> tuple[int, int]:
        eocd_signature = b"\x50\x4b\x05\x06"
        eocd_offset = data.rfind(eocd_signature)
        if eocd_offset == -1:
            raise EOFError("Cannot read the eocd of file.")

        eocd = data[eocd_offset : eocd_offset + 22]
        _, _, _, _, _, central_directory_size, central_directory_offset, _ = struct.unpack(
            "<IHHHHIIH", eocd
        )
        return central_directory_offset, central_directory_size

    @staticmethod
    def parse_central_directory_data(data: bytes) -> list[dict[str, int | str]]:
        file_headers: list[dict[str, int | str]] = []
        offset = 0
        while offset < len(data):
            if data[offset : offset + 4] != b"\x50\x4b\x01\x02":
                raise BufferError("Cannot parse the central directory of file.")
            packed = struct.unpack("<IHHHHHHIIIHHHHHII", data[offset : offset + 46])

            uncompressed_size = packed[9]
            file_name_length = packed[10]
            extra_field_length = packed[11]
            file_comment_length = packed[12]
            local_header_offset = packed[16]
            file_name = data[offset + 46 : offset + 46 + file_name_length].decode("utf8")

            file_headers.append(
                {
                    "path": file_name,
                    "offset": local_header_offset,
                    "size": uncompressed_size,
                }
            )
            offset += 46 + file_name_length + extra_field_length + file_comment_length

        return file_headers

    @staticmethod
    def download_and_decompress_file(
        apk_url: str, target_path: str, header_part: bytes, start_offset: int
    ) -> bool:
        try:
            header = struct.unpack("<IHHHHHIIIHH", header_part[:30])
            _, _, _, compression, _, _, _, compressed_size, _, file_name_len, extra_len = (
                header
            )
            data_start = start_offset + 30 + file_name_len + extra_len
            data_end = data_start + compressed_size
            compressed_data = FileDownloader(
                apk_url,
                headers={"Range": f"bytes={data_start}-{data_end - 1}"},
            ).get_bytes()
            return ZipUtils.decompress_file_part(compressed_data, target_path, compression)
        except Exception:
            return False

    @staticmethod
    def decompress_file_part(
        compressed_data_part: bytes, file_path: str, compress_method: int
    ) -> bool:
        try:
            if compress_method == 8:
                decompressor = zlib.decompressobj(-zlib.MAX_WBITS)
                decompressed_data = decompressor.decompress(compressed_data_part)
                decompressed_data += decompressor.flush()
            else:
                decompressed_data = compressed_data_part

            with open(file_path, "wb") as output_file:
                output_file.write(decompressed_data)
            return True
        except Exception:
            return False
