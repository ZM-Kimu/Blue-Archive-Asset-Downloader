from __future__ import annotations

import struct

from Crypto.Cipher import AES

HEADER_OFFSETS = [
    0x08,
    0x0C,
    0x10,
    0x14,
    0x18,
    0x1C,
    0x20,
    0x24,
    0x28,
    0x2C,
    0x30,
    0x34,
    0x58,
    0x5C,
    0x60,
    0x64,
    0x68,
    0x6C,
    0x88,
    0x8C,
    0x90,
    0x94,
    0x98,
    0x9C,
    0xA0,
    0xA4,
]

EXPECTED_PROTECTED_MAGIC = bytes.fromhex("94437212")
NORMAL_IL2CPP_MAGIC = bytes.fromhex("af1bb1fa")
RESTORE_KEY_CONSTANT = 0xD96603C0
RESTORE_IV = bytes(range(2, 18))


def restore_runtime_metadata_view(
    protected_metadata: bytes | memoryview,
) -> tuple[bytes, dict[str, object]]:
    restored = apply_restore(protected_metadata, RESTORE_KEY_CONSTANT)
    header_ok, header_values = validate_header_offsets(restored)
    return restored, {
        "input_size": len(protected_metadata),
        "output_size": len(restored),
        "protected_magic": protected_metadata[:4].hex(),
        "restored_magic": restored[:4].hex(),
        "header_offsets_valid": header_ok,
        "header_offset_count": len(header_values),
    }


def derive_xor_byte(key_constant: int) -> int:
    key = (key_constant >> 16) & 0xFF
    return key if key else 0x87


def derive_ascii_key_material(key_constant: int) -> bytes:
    return (f"{key_constant:08x}{key_constant:08x}").encode("ascii")


def apply_restore(raw: bytes | memoryview, key_constant: int) -> bytes:
    out = bytearray(raw)
    xor_byte = derive_xor_byte(key_constant)
    aes_key = derive_ascii_key_material(key_constant)

    for index in range(8, min(0x1000, len(out))):
        out[index] ^= xor_byte

    for offset in range(0x1000, min(0x5000, len(out)), 0x800):
        chunk = bytes(out[offset : offset + 0x800])
        if len(chunk) < 0x800:
            break
        out[offset : offset + 0x800] = AES.new(
            aes_key,
            AES.MODE_CBC,
            RESTORE_IV,
        ).decrypt(chunk)

    tail_len = len(out) - 0x11000
    if tail_len > 0:
        block_count = 0
        if tail_len >= 0x10000:
            block_count = ((len(out) - 0x21000) >> 16) + 1
            for block_index in range(block_count):
                start = 0x11000 + block_index * 0x10000
                end = min(len(out), start + 0x4000)
                for index in range(start, end):
                    out[index] ^= xor_byte

        remaining = tail_len - (block_count << 16)
        if remaining > 0:
            start = 0x11000 + (block_count << 16)
            end = min(len(out), start + remaining)
            for index in range(start, end):
                out[index] ^= xor_byte

    return bytes(out)


def validate_header_offsets(buf: bytes) -> tuple[bool, dict[int, int]]:
    size = len(buf)
    values = {
        offset: struct.unpack_from("<i", buf, offset)[0] for offset in HEADER_OFFSETS
    }
    return all(0 <= value < size for value in values.values()), values
