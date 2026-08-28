from __future__ import annotations

import lzma
import struct
from pathlib import Path

import pytest
from Crypto.Cipher import AES
from Crypto.PublicKey import RSA

from ba_downloader.infrastructure.regions.jp.runtime_assets import (
    AARCH64_MACHINE,
    ELF64_LITTLE_ENDIAN_PREFIX,
    MFTL_MAGIC,
    MFTL_TARGET_NAME,
    PADDED_65537,
    TARA_MAGIC,
    TARA_V3,
    JpEncryptedRuntimeExtractor,
    JpRuntimeDecryptError,
    locate_jp_runtime_payload,
)


def test_synthetic_mftl_tara_container_round_trips_and_is_located(
    tmp_path: Path,
) -> None:
    restored = bytearray(range(128))
    restored[: len(ELF64_LITTLE_ENDIAN_PREFIX)] = ELF64_LITTLE_ENDIAN_PREFIX
    restored[18:20] = AARCH64_MACHINE.to_bytes(2, "little")
    source = tmp_path / "libencrypted.so"
    source.write_bytes(_build_container(bytes(restored)))

    payload = locate_jp_runtime_payload(tmp_path)
    assert payload is not None
    assert payload.path == source
    assert payload.encrypted
    destination = tmp_path / "libil2cpp.so"
    JpEncryptedRuntimeExtractor().extract(source, destination)

    assert destination.read_bytes() == bytes(restored)


def test_failed_runtime_decryption_preserves_existing_output(tmp_path: Path) -> None:
    source = tmp_path / "broken.so"
    source.write_bytes(_build_container(_minimal_elf(), include_rsa_material=False))
    destination = tmp_path / "libil2cpp.so"
    destination.write_bytes(b"previous")

    with pytest.raises(JpRuntimeDecryptError, match="No RSA material"):
        JpEncryptedRuntimeExtractor().extract(source, destination)

    assert destination.read_bytes() == b"previous"
    assert not tuple(tmp_path.glob(".libil2cpp.so.*.tmp"))


def _build_container(restored: bytes, *, include_rsa_material: bool = True) -> bytes:
    key = RSA.generate(1024)
    expected_prefix = restored[:32]
    encoded = b"\x00\x01" + (b"\xff" * 93) + b"\x00" + expected_prefix
    side = pow(int.from_bytes(encoded, "big"), key.d, key.n).to_bytes(128, "big")
    lzma_filter = {
        "id": lzma.FILTER_LZMA1,
        "dict_size": 4096,
        "lc": 3,
        "lp": 0,
        "pb": 2,
    }
    compressed = lzma.compress(restored, format=lzma.FORMAT_RAW, filters=[lzma_filter])
    padded = compressed + b"\x00" * (-len(compressed) % AES.block_size)
    encrypted_compressed = AES.new(
        expected_prefix,
        AES.MODE_CBC,
        b"\x00" * AES.block_size,
    ).encrypt(padded)
    header = bytearray(
        struct.pack(
            "<8I",
            TARA_MAGIC,
            TARA_V3,
            0,
            len(side),
            len(compressed),
            len(restored),
            0,
            0,
        )
    )
    header[24:29] = bytes((3 + 9 * (0 + 5 * 2),)) + (4096).to_bytes(4, "little")
    tara = bytes(header) + side + encrypted_compressed
    outer_key = bytes(range(32))
    outer_iv = bytes(range(16))
    encrypted_payload = AES.new(outer_key, AES.MODE_CBC, outer_iv).encrypt(tara)

    host = bytearray(384)
    host[: len(ELF64_LITTLE_ENDIAN_PREFIX)] = ELF64_LITTLE_ENDIAN_PREFIX
    host[18:20] = AARCH64_MACHINE.to_bytes(2, "little")
    if include_rsa_material:
        host[64:320] = key.n.to_bytes(128, "big") + PADDED_65537
    payload_offset = len(host)
    directory = _mftl_directory(
        payload_offset,
        len(encrypted_payload),
        outer_iv,
        outer_key,
        len(restored),
    )
    directory_offset = payload_offset + len(encrypted_payload)
    footer = (
        MFTL_MAGIC
        + struct.pack(
            "<IQQQQ",
            1,
            payload_offset,
            len(encrypted_payload),
            directory_offset,
            len(directory),
        )
        + b"\x00" * 4
    )
    return bytes(host) + encrypted_payload + directory + footer


def _mftl_directory(
    payload_offset: int,
    payload_size: int,
    iv: bytes,
    key: bytes,
    recorded_size: int,
) -> bytes:
    return b"".join(
        (
            b"\x91\x97",
            _msgpack_string(MFTL_TARGET_NAME),
            _msgpack_uint(payload_offset),
            _msgpack_uint(payload_size),
            _msgpack_binary(iv),
            _msgpack_binary(key),
            _msgpack_uint(recorded_size),
            _msgpack_string("test"),
        )
    )


def _msgpack_uint(value: int) -> bytes:
    if value <= 0x7F:
        return bytes((value,))
    if value <= 0xFF:
        return b"\xcc" + value.to_bytes(1, "big")
    if value <= 0xFFFF:
        return b"\xcd" + value.to_bytes(2, "big")
    return b"\xce" + value.to_bytes(4, "big")


def _msgpack_string(value: str) -> bytes:
    encoded = value.encode("utf8")
    if len(encoded) <= 31:
        return bytes((0xA0 + len(encoded),)) + encoded
    return b"\xd9" + bytes((len(encoded),)) + encoded


def _msgpack_binary(value: bytes) -> bytes:
    return b"\xc4" + bytes((len(value),)) + value


def _minimal_elf() -> bytes:
    payload = bytearray(64)
    payload[: len(ELF64_LITTLE_ENDIAN_PREFIX)] = ELF64_LITTLE_ENDIAN_PREFIX
    payload[18:20] = AARCH64_MACHINE.to_bytes(2, "little")
    return bytes(payload)
