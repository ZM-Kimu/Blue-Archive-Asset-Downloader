from __future__ import annotations

import lzma
import struct
from dataclasses import dataclass
from pathlib import Path

import pytest
from Crypto.Cipher import AES
from Crypto.PublicKey import RSA

from ba_downloader.bootstrap.region_profiles import (
    DEFAULT_REGION_SERVICE_PROFILE_REGISTRY,
)
from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.infrastructure.regions.jp.runtime_assets import (
    JpEncryptedRuntimeExtractor,
    JPRuntimeAssetPreparer,
    JpRuntimeDecryptError,
)
from ba_downloader.infrastructure.runtime import RuntimeAssetLocator
from support import RecordingLogger

PADDED_65537 = b"\x00" * 125 + b"\x01\x00\x01"
TARA_MAGIC = 0x41524154


def _build_context(tmp_path: Path) -> RuntimeContext:
    return RuntimeContext(
        region="jp",
        threads=1,
        version="",
        raw_dir=str(tmp_path / "Raw"),
        extract_dir=str(tmp_path / "Extracted"),
        temp_dir=str(tmp_path / "Temp"),
        extract_while_download=False,
        resource_type=("table",),
        proxy_url="",
        max_retries=1,
        search=(),
        advanced_search=(),
        work_dir=str(tmp_path),
    )


def _msgpack_uint(value: int) -> bytes:
    if value <= 0x7F:
        return bytes([value])
    if value <= 0xFF:
        return b"\xcc" + value.to_bytes(1, "big")
    if value <= 0xFFFF:
        return b"\xcd" + value.to_bytes(2, "big")
    return b"\xce" + value.to_bytes(4, "big")


def _msgpack_str(value: str) -> bytes:
    raw = value.encode("utf-8")
    if len(raw) > 31:
        raise ValueError("test strings must fit msgpack fixstr")
    return bytes([0xA0 | len(raw)]) + raw


def _msgpack_bin(value: bytes) -> bytes:
    if len(value) > 255:
        raise ValueError("test bins must fit msgpack bin8")
    return b"\xc4" + bytes([len(value)]) + value


def _build_tara_payload(unpacked: bytes, rsa_key: RSA.RsaKey) -> bytes:
    filters = [{"id": lzma.FILTER_LZMA1, "dict_size": 4096, "lc": 3, "lp": 0, "pb": 2}]
    compressor = lzma.LZMACompressor(format=lzma.FORMAT_RAW, filters=filters)
    compressed = compressor.compress(unpacked) + compressor.flush()
    aligned_size = (len(compressed) + 15) & ~15
    padded_compressed = compressed.ljust(aligned_size, b"\x00")

    head32 = unpacked[:32]
    padding = b"\xff" * (128 - len(head32) - 3)
    side_plain = b"\x00\x02" + padding + b"\x00" + head32
    side = pow(
        int.from_bytes(side_plain, "big"),
        rsa_key.d,
        rsa_key.n,
    ).to_bytes(128, "big")
    encrypted_compressed = AES.new(head32, AES.MODE_CBC, b"\x00" * 16).encrypt(
        padded_compressed
    )

    header = bytearray(
        struct.pack(
            "<8I",
            TARA_MAGIC,
            3,
            0,
            len(side),
            len(compressed),
            len(unpacked),
            0,
            0,
        )
    )
    header[0x18:0x1D] = b"\x5d\x00\x10\x00\x00"
    return bytes(header) + side + encrypted_compressed


def _build_mftl_directory(
    *,
    payload_offset: int,
    payload_size: int,
    iv: bytes,
    key: bytes,
    unpacked_size: int,
) -> bytes:
    return b"".join(
        (
            b"\x91",
            b"\x97",
            _msgpack_str("libil2cpp.so"),
            _msgpack_uint(payload_offset),
            _msgpack_uint(payload_size),
            _msgpack_bin(iv),
            _msgpack_bin(key),
            _msgpack_uint(unpacked_size),
            _msgpack_str("fixture"),
        )
    )


def _write_mftl_tara_fixture(path: Path) -> bytes:
    unpacked = b"\x7fELF" + b"synthetic-libil2cpp".ljust(60, b"\x00")
    rsa_key = RSA.generate(1024)
    tara = _build_tara_payload(unpacked, rsa_key)
    mftl_key = bytes.fromhex("44" * 32)
    mftl_iv = bytes.fromhex("55" * 16)
    encrypted_tara = AES.new(mftl_key, AES.MODE_CBC, mftl_iv).encrypt(tara)

    key_blob = rsa_key.n.to_bytes(128, "big") + PADDED_65537
    payload_offset = 0x200 + len(key_blob) + 0x20
    prefix = bytearray(b"\x7fELF")
    prefix.extend(b"\x00" * (0x200 - len(prefix)))
    prefix.extend(key_blob)
    prefix.extend(b"\x00" * (payload_offset - len(prefix)))

    directory = _build_mftl_directory(
        payload_offset=payload_offset,
        payload_size=len(encrypted_tara),
        iv=mftl_iv,
        key=mftl_key,
        unpacked_size=len(unpacked),
    )
    dir_offset = payload_offset + len(encrypted_tara)
    footer = (
        struct.pack(
            "<4sIQQQQ",
            b"MFTL",
            1,
            payload_offset,
            len(encrypted_tara),
            dir_offset,
            len(directory),
        )
        + b"\x00" * 4
    )
    path.write_bytes(bytes(prefix) + encrypted_tara + directory + footer)
    return unpacked


def test_jp_encrypted_runtime_extractor_restores_libil2cpp(tmp_path: Path) -> None:
    source_path = tmp_path / "libgedenedo.so"
    expected = _write_mftl_tara_fixture(source_path)
    output_path = tmp_path / "libil2cpp.so"

    JpEncryptedRuntimeExtractor().extract(source_path, output_path)

    assert output_path.read_bytes() == expected


def test_jp_encrypted_runtime_extractor_rejects_missing_mftl_footer(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "libgedenedo.so"
    source_path.write_bytes(b"\x7fELF" + b"\x00" * 128)

    with pytest.raises(JpRuntimeDecryptError, match="MFTL footer magic"):
        JpEncryptedRuntimeExtractor().extract(source_path, tmp_path / "libil2cpp.so")


@dataclass
class RecordingRuntimeExtractor:
    calls: list[tuple[Path, Path]]

    def extract(self, source_path: Path, output_path: Path) -> None:
        self.calls.append((source_path, output_path))
        output_path.write_bytes(b"\x7fELFrestored")


def test_jp_runtime_preparer_keeps_existing_libil2cpp(tmp_path: Path) -> None:
    context = _build_context(tmp_path)
    runtime_dir = Path(context.temp_dir) / "Data" / "lib" / "arm64-v8a"
    runtime_dir.mkdir(parents=True)
    (runtime_dir / "libil2cpp.so").write_bytes(b"\x7fELFexisting")
    extractor = RecordingRuntimeExtractor([])

    JPRuntimeAssetPreparer(RecordingLogger(), extractor=extractor).prepare(context)

    assert extractor.calls == []
    assert (runtime_dir / "libil2cpp.so").read_bytes() == b"\x7fELFexisting"


def test_jp_runtime_preparer_restores_libil2cpp_from_libgedenedo(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path)
    runtime_dir = Path(context.temp_dir) / "Data" / "lib" / "arm64-v8a"
    runtime_dir.mkdir(parents=True)
    source_path = runtime_dir / "libgedenedo.so"
    source_path.write_bytes(b"encrypted")
    extractor = RecordingRuntimeExtractor([])

    JPRuntimeAssetPreparer(RecordingLogger(), extractor=extractor).prepare(context)

    assert extractor.calls == [(source_path, runtime_dir / "libil2cpp.so")]
    assert (runtime_dir / "libil2cpp.so").read_bytes() == b"\x7fELFrestored"


def test_default_region_service_profile_uses_jp_runtime_preparer() -> None:
    preparer = DEFAULT_REGION_SERVICE_PROFILE_REGISTRY.resolve(
        "jp"
    ).runtime_asset_preparer_factory(
        http_client=object(),
        logger=RecordingLogger(),
    )

    assert isinstance(preparer, JPRuntimeAssetPreparer)


def test_runtime_asset_locator_uses_candidate_order_and_deterministic_paths(
    tmp_path: Path,
) -> None:
    root = tmp_path / "Temp"
    deeper = root / "z" / "runtime"
    shallower = root / "a"
    deeper.mkdir(parents=True)
    shallower.mkdir(parents=True)
    (deeper / "libil2cpp.so").write_bytes(b"deeper")
    (shallower / "libil2cpp.so").write_bytes(b"shallower")
    (deeper / "GameAssembly.dll").write_bytes(b"preferred")

    locator = RuntimeAssetLocator(root)

    assert locator.find_first(("GameAssembly.dll", "libil2cpp.so")) == (
        deeper / "GameAssembly.dll"
    )
    assert locator.find_first(("libil2cpp.so",)) == shallower / "libil2cpp.so"
