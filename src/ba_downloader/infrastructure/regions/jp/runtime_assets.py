from __future__ import annotations

import lzma
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from Crypto.Cipher import AES

from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.infrastructure.runtime.assets import RuntimeAssetLocator

MFTL_FOOTER_SIZE = 0x2C
MFTL_MAGIC = b"MFTL"
TARA_MAGIC = 0x41524154
TARA_V3 = 3
PADDED_65537 = b"\x00" * 125 + b"\x01\x00\x01"


class JpRuntimeDecryptError(RuntimeError):
    """Raised when JP encrypted runtime extraction fails."""


@dataclass(frozen=True)
class MftlEntry:
    name: str
    payload_offset: int
    payload_size: int
    iv: bytes
    key: bytes
    unpacked_size: int
    checksum: str


class MsgpackLite:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.pos = 0

    def read_u8(self) -> int:
        if self.pos >= len(self.data):
            raise JpRuntimeDecryptError("Truncated MFTL directory.")
        value = self.data[self.pos]
        self.pos += 1
        return value

    def read(self, size: int) -> bytes:
        value = self.data[self.pos : self.pos + size]
        if len(value) != size:
            raise JpRuntimeDecryptError("Truncated MFTL directory.")
        self.pos += size
        return value

    def read_array_len(self) -> int:
        marker = self.read_u8()
        if 0x90 <= marker <= 0x9F:
            return marker & 0x0F
        raise JpRuntimeDecryptError(f"Unsupported MFTL array marker 0x{marker:02x}.")

    def read_str(self) -> str:
        marker = self.read_u8()
        if not 0xA0 <= marker <= 0xBF:
            raise JpRuntimeDecryptError(
                f"Unsupported MFTL string marker 0x{marker:02x}."
            )
        return self.read(marker & 0x1F).decode("utf-8")

    def read_bin(self) -> bytes:
        marker = self.read_u8()
        if marker != 0xC4:
            raise JpRuntimeDecryptError(f"Unsupported MFTL bin marker 0x{marker:02x}.")
        return self.read(self.read_u8())

    def read_uint(self) -> int:
        marker = self.read_u8()
        if marker <= 0x7F:
            return marker
        if marker == 0xCC:
            return self.read_u8()
        if marker == 0xCD:
            return int.from_bytes(self.read(2), "big")
        if marker == 0xCE:
            return int.from_bytes(self.read(4), "big")
        if marker == 0xCF:
            return int.from_bytes(self.read(8), "big")
        raise JpRuntimeDecryptError(f"Unsupported MFTL uint marker 0x{marker:02x}.")


class JpEncryptedRuntimeExtractor:
    def extract(self, source_path: Path, output_path: Path) -> None:
        try:
            unpacked = self.extract_bytes(source_path.read_bytes())
        except JpRuntimeDecryptError:
            raise
        except (OSError, ValueError, struct.error) as exc:
            raise JpRuntimeDecryptError(str(exc)) from exc

        output_path.parent.mkdir(parents=True, exist_ok=True)
        temp_output_path = output_path.with_name(f"{output_path.name}.tmp")
        try:
            temp_output_path.write_bytes(unpacked)
            temp_output_path.replace(output_path)
        finally:
            temp_output_path.unlink(missing_ok=True)

    def extract_bytes(self, so_data: bytes) -> bytes:
        entry = self._parse_mftl_entry(so_data)
        payload = so_data[
            entry.payload_offset : entry.payload_offset + entry.payload_size
        ]
        tara = AES.new(entry.key, AES.MODE_CBC, entry.iv).decrypt(payload)
        return self._unpack_tara_v3(tara, so_data)

    @staticmethod
    def _parse_mftl_entry(so_data: bytes) -> MftlEntry:
        if len(so_data) < MFTL_FOOTER_SIZE:
            raise JpRuntimeDecryptError("MFTL footer magic not found at EOF.")

        footer = so_data[-MFTL_FOOTER_SIZE:]
        if footer[:4] != MFTL_MAGIC:
            raise JpRuntimeDecryptError("MFTL footer magic not found at EOF.")

        version = struct.unpack_from("<I", footer, 4)[0]
        payload_offset, payload_size, dir_offset, dir_size = struct.unpack_from(
            "<QQQQ",
            footer,
            8,
        )
        if version != 1:
            raise JpRuntimeDecryptError(f"Unsupported MFTL version {version}.")
        if payload_offset + payload_size != dir_offset:
            raise JpRuntimeDecryptError(
                "MFTL payload does not end at directory offset."
            )

        reader = MsgpackLite(so_data[dir_offset : dir_offset + dir_size])
        outer_len = reader.read_array_len()
        if outer_len != 1:
            raise JpRuntimeDecryptError(f"Expected one MFTL entry, got {outer_len}.")
        entry_len = reader.read_array_len()
        if entry_len != 7:
            raise JpRuntimeDecryptError(
                f"Expected 7-field MFTL entry, got {entry_len}."
            )

        entry = MftlEntry(
            name=reader.read_str(),
            payload_offset=reader.read_uint(),
            payload_size=reader.read_uint(),
            iv=reader.read_bin(),
            key=reader.read_bin(),
            unpacked_size=reader.read_uint(),
            checksum=reader.read_str(),
        )
        if entry.payload_offset != payload_offset or entry.payload_size != payload_size:
            raise JpRuntimeDecryptError("MFTL footer and directory disagree.")
        if len(entry.key) != 32 or len(entry.iv) != 16:
            raise JpRuntimeDecryptError("Unexpected MFTL AES key/IV lengths.")
        return entry

    def _unpack_tara_v3(self, tara: bytes, so_data: bytes) -> bytes:
        if len(tara) < 0x20:
            raise JpRuntimeDecryptError("Truncated TARA payload.")

        magic, version, _, side_len, comp_len, out_len, _, _ = struct.unpack_from(
            "<8I",
            tara,
            0,
        )
        if magic != TARA_MAGIC or version != TARA_V3:
            raise JpRuntimeDecryptError("Not a TARA v3 payload.")

        aligned_comp_len = (comp_len + 15) & ~15
        expected_len = 0x20 + side_len + aligned_comp_len
        if expected_len > len(tara):
            raise JpRuntimeDecryptError("Truncated TARA payload.")

        props = tara[0x18:0x1D]
        side = tara[0x20 : 0x20 + side_len]
        encrypted_comp = tara[0x20 + side_len : expected_len]
        elf_head32 = self._rsa_unwrap_side_block(side, so_data)
        compressed = AES.new(elf_head32, AES.MODE_CBC, b"\x00" * 16).decrypt(
            encrypted_comp
        )[:comp_len]

        decompressor = lzma.LZMADecompressor(
            format=lzma.FORMAT_RAW,
            filters=[self._parse_lzma_filter(props)],
        )
        unpacked = decompressor.decompress(compressed, max_length=out_len)
        if len(unpacked) != out_len:
            raise JpRuntimeDecryptError(
                f"LZMA produced 0x{len(unpacked):x}, expected 0x{out_len:x}."
            )
        if not unpacked.startswith(elf_head32):
            raise JpRuntimeDecryptError(
                "Unpacked ELF does not match RSA side-block prefix."
            )
        return unpacked

    @staticmethod
    def _rsa_unwrap_side_block(side: bytes, so_data: bytes) -> bytes:
        seen_offsets: set[int] = set()
        search_pos = 0
        while True:
            exponent_offset = so_data.find(PADDED_65537, search_pos)
            if exponent_offset < 0:
                break
            search_pos = exponent_offset + 1
            offset = exponent_offset - 0x80
            if offset < 0 or offset in seen_offsets:
                continue
            seen_offsets.add(offset)

            blob = so_data[offset : offset + 0x100]
            if len(blob) != 0x100 or blob[0x80:] != PADDED_65537 or blob[0] == 0:
                continue

            modulus = int.from_bytes(blob[:0x80], "big")
            plain = pow(int.from_bytes(side, "big"), 65537, modulus).to_bytes(
                0x80,
                "big",
            )
            if plain[0] != 0:
                continue
            try:
                delimiter = plain.index(0, 2)
            except ValueError:
                continue
            payload = plain[delimiter + 1 :]
            if len(payload) == 32 and payload.startswith(b"\x7fELF"):
                return payload

        raise JpRuntimeDecryptError("No RSA key candidate unwrapped TARA side block.")

    @staticmethod
    def _parse_lzma_filter(props: bytes) -> dict[str, int]:
        if len(props) != 5:
            raise JpRuntimeDecryptError("LZMA properties must be 5 bytes.")
        prop = props[0]
        lc = prop % 9
        rem = prop // 9
        lp = rem % 5
        pb = rem // 5
        return {
            "id": lzma.FILTER_LZMA1,
            "dict_size": int.from_bytes(props[1:5], "little"),
            "lc": lc,
            "lp": lp,
            "pb": pb,
        }


class RuntimeExtractor(Protocol):
    def extract(self, source_path: Path, output_path: Path) -> None: ...


class JPRuntimeAssetPreparer:
    BINARY_CANDIDATES = ("GameAssembly.dll", "libil2cpp.so")
    ENCRYPTED_BINARY_NAME = "libgedenedo.so"

    def __init__(
        self,
        logger: LoggerPort,
        *,
        extractor: RuntimeExtractor | None = None,
    ) -> None:
        self.logger = logger
        self.extractor = extractor or JpEncryptedRuntimeExtractor()

    def prepare(self, context: RuntimeContext) -> None:
        temp_dir = Path(context.temp_dir)
        locator = RuntimeAssetLocator(temp_dir)
        if locator.find_first(self.BINARY_CANDIDATES):
            return

        encrypted_binary = locator.find_first((self.ENCRYPTED_BINARY_NAME,))
        if encrypted_binary is None:
            raise FileNotFoundError(
                "Cannot find JP runtime binary. Expected GameAssembly.dll, "
                f"libil2cpp.so, or {self.ENCRYPTED_BINARY_NAME} under {temp_dir}."
            )

        output_path = encrypted_binary.with_name("libil2cpp.so")
        self.logger.info("Restoring JP libil2cpp.so from encrypted runtime payload...")
        self.extractor.extract(encrypted_binary, output_path)

        if not output_path.is_file():
            raise FileNotFoundError(
                f"Failed to restore JP libil2cpp.so from {encrypted_binary}."
            )
        self.logger.info("Restored JP libil2cpp.so successfully.")
