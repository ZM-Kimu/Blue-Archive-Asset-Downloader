from __future__ import annotations

import lzma
import shutil
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO, Protocol
from uuid import uuid4

from Crypto.Cipher import AES

from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.domain.models.runtime_assets import PreparedRuntimeAssets
from ba_downloader.domain.ports.execution import CancellationPort, NeverCancelled
from ba_downloader.domain.ports.logging import LoggerPort
from ba_downloader.domain.ports.runtime import RuntimeAssetPreparerPort
from ba_downloader.infrastructure.files.checksum import calculate_sha256
from ba_downloader.infrastructure.runtime import RuntimeSnapshotStore

MFTL_FOOTER_SIZE = 0x2C
MFTL_MAGIC = b"MFTL"
MFTL_VERSION = 1
MFTL_TARGET_NAME = "libil2cpp.so"
MFTL_CONTAINER_SONAME = b"libappsign4a.so"
TARA_MAGIC = 0x41524154
TARA_V3 = 3
PADDED_65537 = b"\x00" * 125 + b"\x01\x00\x01"
ELF64_LITTLE_ENDIAN_PREFIX = b"\x7fELF\x02\x01"
AARCH64_MACHINE = 0xB7
STREAM_CHUNK_SIZE = 1024 * 1024
MAX_UNPACKED_SIZE = 512 * 1024 * 1024
MAX_MFTL_DIRECTORY_SIZE = 1024 * 1024


class JpRuntimeDecryptError(RuntimeError):
    """Raised when JP encrypted runtime extraction fails."""


class JpRuntimePayloadError(LookupError):
    """Raised when the JP package runtime payload cannot be selected safely."""


@dataclass(frozen=True, slots=True)
class MftlFooter:
    payload_offset: int
    payload_size: int
    directory_offset: int
    directory_size: int


@dataclass(frozen=True, slots=True)
class MftlEntry:
    name: str
    payload_offset: int
    payload_size: int
    iv: bytes
    key: bytes
    recorded_size: int
    checksum: str


@dataclass(frozen=True, slots=True)
class MftlContainerInfo:
    footer: MftlFooter
    entry: MftlEntry


@dataclass(frozen=True, slots=True)
class JpRuntimePayload:
    path: Path
    container: MftlContainerInfo

    @property
    def encrypted(self) -> bool:
        return True


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


def _parse_mftl_footer(footer: bytes, file_size: int) -> MftlFooter:
    if len(footer) != MFTL_FOOTER_SIZE or footer[:4] != MFTL_MAGIC:
        raise JpRuntimeDecryptError("MFTL footer magic not found at EOF.")

    version = struct.unpack_from("<I", footer, 4)[0]
    if version != MFTL_VERSION:
        raise JpRuntimeDecryptError(f"Unsupported MFTL version {version}.")
    if footer[0x28:] != b"\x00" * 4:
        raise JpRuntimeDecryptError("MFTL footer reserved field is not zero.")

    payload_offset, payload_size, directory_offset, directory_size = struct.unpack_from(
        "<QQQQ", footer, 8
    )
    footer_offset = file_size - MFTL_FOOTER_SIZE
    if payload_offset < 20 or payload_offset >= file_size:
        raise JpRuntimeDecryptError("MFTL payload offset is outside the container.")
    if payload_offset + payload_size != directory_offset:
        raise JpRuntimeDecryptError("MFTL payload does not end at directory offset.")
    if directory_offset + directory_size != footer_offset:
        raise JpRuntimeDecryptError("MFTL directory does not end at the footer offset.")
    if payload_size == 0 or payload_size % AES.block_size:
        raise JpRuntimeDecryptError("MFTL payload size is not AES block aligned.")
    if directory_size == 0 or directory_size > MAX_MFTL_DIRECTORY_SIZE:
        raise JpRuntimeDecryptError("MFTL directory is empty.")
    return MftlFooter(
        payload_offset=payload_offset,
        payload_size=payload_size,
        directory_offset=directory_offset,
        directory_size=directory_size,
    )


def _parse_mftl_directory(data: bytes, footer: MftlFooter) -> MftlEntry:
    reader = MsgpackLite(data)
    outer_len = reader.read_array_len()
    if outer_len != 1:
        raise JpRuntimeDecryptError(f"Expected one MFTL entry, got {outer_len}.")
    entry_len = reader.read_array_len()
    if entry_len != 7:
        raise JpRuntimeDecryptError(f"Expected 7-field MFTL entry, got {entry_len}.")

    entry = MftlEntry(
        name=reader.read_str(),
        payload_offset=reader.read_uint(),
        payload_size=reader.read_uint(),
        iv=reader.read_bin(),
        key=reader.read_bin(),
        recorded_size=reader.read_uint(),
        checksum=reader.read_str(),
    )
    if reader.pos != len(data):
        raise JpRuntimeDecryptError("MFTL directory contains trailing data.")
    if entry.name != MFTL_TARGET_NAME:
        raise JpRuntimeDecryptError(
            f"MFTL entry targets {entry.name!r}, expected {MFTL_TARGET_NAME!r}."
        )
    if (
        entry.payload_offset != footer.payload_offset
        or entry.payload_size != footer.payload_size
    ):
        raise JpRuntimeDecryptError("MFTL footer and directory disagree.")
    if len(entry.key) != 32 or len(entry.iv) != 16:
        raise JpRuntimeDecryptError("Unexpected MFTL AES key/IV lengths.")
    if entry.recorded_size != entry.payload_size:
        raise JpRuntimeDecryptError("MFTL recorded size and payload size disagree.")
    return entry


def _read_mftl_entry(path: Path) -> MftlContainerInfo:
    file_size = path.stat().st_size
    if file_size < MFTL_FOOTER_SIZE:
        raise JpRuntimeDecryptError("MFTL footer magic not found at EOF.")
    with path.open("rb") as source:
        source.seek(-MFTL_FOOTER_SIZE, 2)
        footer = _parse_mftl_footer(source.read(MFTL_FOOTER_SIZE), file_size)
        source.seek(0)
        elf_header = source.read(20)
        if (
            not elf_header.startswith(ELF64_LITTLE_ENDIAN_PREFIX)
            or len(elf_header) < 20
            or int.from_bytes(elf_header[18:20], "little") != AARCH64_MACHINE
        ):
            raise JpRuntimeDecryptError(
                "MFTL runtime container is not an AArch64 ELF file."
            )
        if not _stream_contains(
            source,
            MFTL_CONTAINER_SONAME,
            limit=footer.payload_offset,
        ):
            raise JpRuntimeDecryptError(
                "MFTL runtime container SONAME marker was not found."
            )
        source.seek(footer.directory_offset)
        directory = source.read(footer.directory_size)
    if len(directory) != footer.directory_size:
        raise JpRuntimeDecryptError("Truncated MFTL directory.")
    return MftlContainerInfo(
        footer=footer,
        entry=_parse_mftl_directory(directory, footer),
    )


def _stream_contains(source: BinaryIO, marker: bytes, *, limit: int) -> bool:
    source.seek(0)
    remaining = limit
    overlap = b""
    while remaining > 0:
        chunk = source.read(min(64 * 1024, remaining))
        if not chunk:
            return False
        if marker in overlap + chunk:
            return True
        overlap = chunk[-(len(marker) - 1) :]
        remaining -= len(chunk)
    return False


def _has_mftl_footer(path: Path) -> bool:
    try:
        if path.stat().st_size < MFTL_FOOTER_SIZE:
            return False
        with path.open("rb") as source:
            source.seek(-MFTL_FOOTER_SIZE, 2)
            return source.read(len(MFTL_MAGIC)) == MFTL_MAGIC
    except OSError:
        return False


def locate_jp_runtime_payload(runtime_dir: Path) -> JpRuntimePayload | None:
    encrypted_candidates: list[JpRuntimePayload] = []
    for candidate in sorted(runtime_dir.glob("*.so"), key=lambda path: path.name):
        if not candidate.is_file() or not _has_mftl_footer(candidate):
            continue
        try:
            container = _read_mftl_entry(candidate)
        except (OSError, JpRuntimeDecryptError) as exc:
            raise JpRuntimePayloadError(
                f"Invalid JP MFTL runtime candidate '{candidate.name}': {exc}"
            ) from exc
        encrypted_candidates.append(JpRuntimePayload(candidate, container))

    if len(encrypted_candidates) > 1:
        names = ", ".join(payload.path.name for payload in encrypted_candidates)
        raise JpRuntimePayloadError(
            f"Multiple JP MFTL runtime candidates were found: {names}."
        )
    if encrypted_candidates:
        return encrypted_candidates[0]
    return None


class JpEncryptedRuntimeExtractor:
    def __init__(self, cancellation: CancellationPort | None = None) -> None:
        self.cancellation = cancellation or NeverCancelled()

    def extract(self, source_path: Path, output_path: Path) -> None:
        temp_output_path = output_path.with_name(
            f".{output_path.name}.{uuid4().hex}.tmp"
        )
        try:
            container = _read_mftl_entry(source_path)
            moduli = self._scan_rsa_moduli(
                source_path,
                limit=container.footer.payload_offset,
            )
            if not moduli:
                raise JpRuntimeDecryptError(
                    "No RSA material was found before the MFTL payload."
                )
            output_path.parent.mkdir(parents=True, exist_ok=True)
            declared_output_size = self._extract_stream(
                source_path,
                temp_output_path,
                container.entry,
                moduli,
            )
            os_header = self._read_elf_header(temp_output_path)
            if temp_output_path.stat().st_size != declared_output_size:
                raise JpRuntimeDecryptError(
                    "Restored runtime size does not match the TARA header."
                )
            if (
                not os_header.startswith(ELF64_LITTLE_ENDIAN_PREFIX)
                or len(os_header) < 20
                or int.from_bytes(os_header[18:20], "little") != AARCH64_MACHINE
            ):
                raise JpRuntimeDecryptError(
                    "Restored runtime is not an AArch64 ELF64 little-endian file."
                )
            temp_output_path.replace(output_path)
        except JpRuntimeDecryptError:
            raise
        except (OSError, ValueError, struct.error, lzma.LZMAError) as exc:
            raise JpRuntimeDecryptError(str(exc)) from exc
        finally:
            temp_output_path.unlink(missing_ok=True)

    def _extract_stream(
        self,
        source_path: Path,
        output_path: Path,
        entry: MftlEntry,
        moduli: list[int],
    ) -> int:
        outer_cipher = AES.new(entry.key, AES.MODE_CBC, entry.iv)
        prefix = bytearray()
        side_target: int | None = None
        inner_cipher: Any | None = None
        decompressor: lzma.LZMADecompressor | None = None
        encrypted_comp_remaining = 0
        compressed_remaining = 0
        declared_output_size: int | None = None
        output_remaining: int | None = None
        inner_pending = bytearray()
        expected_prefix = b""

        with source_path.open("rb") as source, output_path.open("wb") as output:
            source.seek(entry.payload_offset)
            payload_remaining = entry.payload_size

            def write_decompressed(compressed: bytes) -> None:
                nonlocal output_remaining
                assert decompressor is not None
                assert output_remaining is not None
                pending = compressed
                while pending or not decompressor.needs_input:
                    self.cancellation.raise_if_cancelled()
                    unpacked = decompressor.decompress(
                        pending,
                        max_length=min(STREAM_CHUNK_SIZE, output_remaining + 1),
                    )
                    pending = b""
                    if len(unpacked) > output_remaining:
                        raise JpRuntimeDecryptError(
                            "LZMA output exceeds the declared unpacked size."
                        )
                    output.write(unpacked)
                    output_remaining -= len(unpacked)
                    if decompressor.eof or decompressor.needs_input:
                        break

            while payload_remaining:
                self.cancellation.raise_if_cancelled()
                encrypted = source.read(min(STREAM_CHUNK_SIZE, payload_remaining))
                if not encrypted or len(encrypted) % AES.block_size:
                    raise JpRuntimeDecryptError("Truncated MFTL AES payload.")
                payload_remaining -= len(encrypted)
                decrypted = outer_cipher.decrypt(encrypted)
                if inner_cipher is None:
                    prefix.extend(decrypted)
                    if side_target is None and len(prefix) >= 0x20:
                        (
                            magic,
                            version,
                            _,
                            side_len,
                            comp_len,
                            out_len,
                            _,
                            _,
                        ) = struct.unpack_from("<8I", prefix, 0)
                        if magic != TARA_MAGIC or version != TARA_V3:
                            raise JpRuntimeDecryptError("Not a TARA v3 payload.")
                        if side_len <= 0 or side_len > 64 * 1024 or comp_len <= 0:
                            raise JpRuntimeDecryptError(
                                "TARA side or compressed length is invalid."
                            )
                        if out_len <= 0 or out_len > MAX_UNPACKED_SIZE:
                            raise JpRuntimeDecryptError(
                                "TARA output size is outside the allowed range."
                            )
                        declared_output_size = out_len
                        output_remaining = out_len
                        aligned_comp_len = (comp_len + 15) & ~15
                        if 0x20 + side_len + aligned_comp_len != entry.payload_size:
                            raise JpRuntimeDecryptError(
                                "TARA lengths do not match the MFTL payload size."
                            )
                        side_target = 0x20 + side_len
                        encrypted_comp_remaining = aligned_comp_len
                        compressed_remaining = comp_len
                    if side_target is None or len(prefix) < side_target:
                        continue
                    side = bytes(prefix[0x20:side_target])
                    expected_prefix = self._rsa_unwrap_side_block(side, moduli)
                    inner_cipher = AES.new(
                        expected_prefix,
                        AES.MODE_CBC,
                        b"\x00" * AES.block_size,
                    )
                    decompressor = lzma.LZMADecompressor(
                        format=lzma.FORMAT_RAW,
                        filters=[self._parse_lzma_filter(bytes(prefix[0x18:0x1D]))],
                    )
                    decrypted = bytes(prefix[side_target:])
                    prefix.clear()

                take = min(len(decrypted), encrypted_comp_remaining)
                inner_pending.extend(decrypted[:take])
                encrypted_comp_remaining -= take
                if len(decrypted) != take:
                    raise JpRuntimeDecryptError("TARA payload contains trailing data.")
                decrypt_length = len(inner_pending) // AES.block_size * AES.block_size
                if decrypt_length:
                    encrypted_comp = bytes(inner_pending[:decrypt_length])
                    del inner_pending[:decrypt_length]
                    assert inner_cipher is not None
                    plain_comp = inner_cipher.decrypt(encrypted_comp)
                    useful_length = min(len(plain_comp), compressed_remaining)
                    compressed_remaining -= useful_length
                    write_decompressed(plain_comp[:useful_length])

            if (
                inner_cipher is None
                or decompressor is None
                or encrypted_comp_remaining
                or compressed_remaining
                or inner_pending
                or output_remaining != 0
            ):
                raise JpRuntimeDecryptError("Truncated or incomplete TARA stream.")
            output.flush()

        with output_path.open("rb") as restored:
            if restored.read(len(expected_prefix)) != expected_prefix:
                raise JpRuntimeDecryptError(
                    "Unpacked ELF does not match RSA side-block prefix."
                )
        assert declared_output_size is not None
        return declared_output_size

    @staticmethod
    def _rsa_unwrap_side_block(side: bytes, moduli: list[int]) -> bytes:
        for modulus in moduli:
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

    def _scan_rsa_moduli(self, path: Path, *, limit: int) -> list[int]:
        moduli: list[int] = []
        seen_offsets: set[int] = set()
        overlap = b""
        consumed = 0
        with path.open("rb") as source:
            while consumed < limit:
                self.cancellation.raise_if_cancelled()
                chunk = source.read(min(STREAM_CHUNK_SIZE, limit - consumed))
                if not chunk:
                    break
                combined = overlap + chunk
                combined_offset = consumed - len(overlap)
                search_pos = 0
                while True:
                    marker_pos = combined.find(PADDED_65537, search_pos)
                    if marker_pos < 0:
                        break
                    absolute_offset = combined_offset + marker_pos - 0x80
                    search_pos = marker_pos + 1
                    blob_start = marker_pos - 0x80
                    blob_end = marker_pos + len(PADDED_65537)
                    if (
                        absolute_offset < 0
                        or absolute_offset in seen_offsets
                        or blob_start < 0
                        or blob_end > len(combined)
                    ):
                        continue
                    blob = combined[blob_start:blob_end]
                    if len(blob) == 0x100 and blob[0] != 0:
                        seen_offsets.add(absolute_offset)
                        moduli.append(int.from_bytes(blob[:0x80], "big"))
                overlap = combined[-0x200:]
                consumed += len(chunk)
        return moduli

    @staticmethod
    def _read_elf_header(path: Path) -> bytes:
        with path.open("rb") as restored:
            return restored.read(20)

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


class JPRuntimeAssetPreparer(RuntimeAssetPreparerPort):
    BINARY_NAME = "libil2cpp.so"
    METADATA_NAME = "global-metadata.dat"
    GLOBALGAMEMANAGERS_NAME = "globalgamemanagers"
    PACKAGE_METADATA_PATH = Path("assets/bin/Data/Managed/Metadata/global-metadata.dat")
    PACKAGE_GLOBALGAMEMANAGERS_PATH = Path("assets/bin/Data/globalgamemanagers")
    PACKAGE_RUNTIME_DIR = Path("lib/arm64-v8a")

    def __init__(
        self,
        logger: LoggerPort,
        *,
        extractor: RuntimeExtractor | None = None,
        snapshot_store: RuntimeSnapshotStore | None = None,
        cancellation: CancellationPort | None = None,
    ) -> None:
        self.logger = logger
        self.cancellation = cancellation or NeverCancelled()
        self.extractor = extractor or JpEncryptedRuntimeExtractor(self.cancellation)
        self.snapshot_store = snapshot_store or RuntimeSnapshotStore(
            cancellation=self.cancellation
        )

    def prepare(self, context: ExecutionContext) -> PreparedRuntimeAssets:
        self.cancellation.raise_if_cancelled()
        if not context.resource_version:
            raise ValueError(
                "JP runtime preparation requires a resolved release version."
            )
        if prepared := self.snapshot_store.load(context, context.resource_version):
            return prepared

        package_root = (
            self.snapshot_store.version_root(context, context.resource_version)
            / "Package"
            / "Extracted"
        )
        package_runtime_dir = package_root / self.PACKAGE_RUNTIME_DIR
        runtime_payload = locate_jp_runtime_payload(package_runtime_dir)
        metadata_source = package_root / self.PACKAGE_METADATA_PATH
        managers_source = package_root / self.PACKAGE_GLOBALGAMEMANAGERS_PATH
        if not metadata_source.is_file() or not managers_source.is_file():
            raise FileNotFoundError(
                "JP package snapshot is missing global-metadata.dat or "
                "globalgamemanagers for the resolved release."
            )
        if runtime_payload is None:
            raise FileNotFoundError(
                "JP package snapshot is missing libil2cpp.so or a structurally "
                "valid MFTL runtime container for the resolved release."
            )

        with self.snapshot_store.staging_runtime(
            context,
            context.resource_version,
        ) as runtime_dir:
            shutil.copy2(metadata_source, runtime_dir / self.METADATA_NAME)
            self.cancellation.raise_if_cancelled()
            shutil.copy2(
                managers_source,
                runtime_dir / self.GLOBALGAMEMANAGERS_NAME,
            )
            file_roles: dict[str, str] = {}
            output_path = runtime_dir / self.BINARY_NAME
            self.logger.info(
                "Restoring JP libil2cpp.so from MFTL runtime payload "
                f"'{runtime_payload.path.name}'..."
            )
            parent_hash = calculate_sha256(
                runtime_payload.path,
                on_chunk=self.cancellation.raise_if_cancelled,
            )
            self.extractor.extract(runtime_payload.path, output_path)
            self.cancellation.raise_if_cancelled()
            self.logger.info("Restored JP libil2cpp.so successfully.")

            if not output_path.is_file():
                raise FileNotFoundError(
                    f"Failed to prepare JP libil2cpp.so from {package_runtime_dir}."
                )
            prepared = self.snapshot_store.publish(
                context,
                context.resource_version,
                runtime_dir,
                binary_name=self.BINARY_NAME,
                metadata_name=self.METADATA_NAME,
                globalgamemanagers_name=self.GLOBALGAMEMANAGERS_NAME,
                file_roles=file_roles,
                provenance={
                    "type": "jp_mftl_v1",
                    "parent": {
                        "name": runtime_payload.path.name,
                        "size": runtime_payload.path.stat().st_size,
                        "sha256": parent_hash,
                    },
                    "footer": {
                        "payload_offset": runtime_payload.container.footer.payload_offset,
                        "payload_size": runtime_payload.container.footer.payload_size,
                        "directory_offset": runtime_payload.container.footer.directory_offset,
                        "directory_size": runtime_payload.container.footer.directory_size,
                    },
                    "entry": {
                        "name": runtime_payload.container.entry.name,
                        "payload_offset": runtime_payload.container.entry.payload_offset,
                        "payload_size": runtime_payload.container.entry.payload_size,
                        "recorded_size": runtime_payload.container.entry.recorded_size,
                        "checksum": runtime_payload.container.entry.checksum,
                    },
                },
            )
            metadata_cache = (
                self.snapshot_store.version_root(context, context.resource_version)
                / "Metadata"
                / "manifest.json"
            )
            if metadata_cache.is_file():
                shutil.rmtree(
                    self.snapshot_store.version_root(context, context.resource_version)
                    / "Package",
                    ignore_errors=True,
                )
            return prepared
