from __future__ import annotations

import lzma
import struct
from dataclasses import dataclass
from pathlib import Path

import pytest
from Crypto.Cipher import AES
from Crypto.PublicKey import RSA

from ba_downloader.bootstrap.region_gateways import (
    DEFAULT_REGION_GATEWAY_REGISTRY,
)
from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.domain.ports.execution import NeverCancelled
from ba_downloader.infrastructure.regions.jp.runtime_assets import (
    JpEncryptedRuntimeExtractor,
    JPRuntimeAssetPreparer,
    JpRuntimeDecryptError,
    JpRuntimePayloadError,
    locate_jp_runtime_payload,
)
from support import RecordingLogger
from support.fixtures import build_execution_context

PADDED_65537 = b"\x00" * 125 + b"\x01\x00\x01"
TARA_MAGIC = 0x41524154


def _build_context(tmp_path: Path) -> ExecutionContext:
    return build_execution_context(
        tmp_path,
        region="jp",
        version="1.70.436321",
        max_retries=1,
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
    recorded_size: int,
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
            _msgpack_uint(recorded_size),
            _msgpack_str("fixture"),
        )
    )


def _write_mftl_tara_fixture(path: Path) -> bytes:
    unpacked_buffer = bytearray(b"\x00" * 64)
    unpacked_buffer[:6] = b"\x7fELF\x02\x01"
    unpacked_buffer[18:20] = (0xB7).to_bytes(2, "little")
    unpacked_buffer[20:40] = b"synthetic-libil2cpp"
    unpacked = bytes(unpacked_buffer)
    rsa_key = RSA.generate(1024)
    tara = _build_tara_payload(unpacked, rsa_key)
    mftl_key = bytes.fromhex("44" * 32)
    mftl_iv = bytes.fromhex("55" * 16)
    encrypted_tara = AES.new(mftl_key, AES.MODE_CBC, mftl_iv).encrypt(tara)

    key_blob = rsa_key.n.to_bytes(128, "big") + PADDED_65537
    payload_offset = 0x200 + len(key_blob) + 0x20
    prefix = bytearray(b"\x00" * 0x200)
    prefix[:6] = b"\x7fELF\x02\x01"
    prefix[18:20] = (0xB7).to_bytes(2, "little")
    prefix[0x20 : 0x20 + len(b"libappsign4a.so")] = b"libappsign4a.so"
    prefix.extend(key_blob)
    prefix.extend(b"\x00" * (payload_offset - len(prefix)))

    directory = _build_mftl_directory(
        payload_offset=payload_offset,
        payload_size=len(encrypted_tara),
        iv=mftl_iv,
        key=mftl_key,
        recorded_size=len(encrypted_tara),
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


def _write_mftl_marker(path: Path) -> None:
    payload_offset = 0x40
    payload = b"\x00" * 16
    directory = _build_mftl_directory(
        payload_offset=payload_offset,
        payload_size=len(payload),
        iv=b"\x11" * 16,
        key=b"\x22" * 32,
        recorded_size=len(payload),
    )
    prefix = bytearray(b"\x00" * payload_offset)
    prefix[:6] = b"\x7fELF\x02\x01"
    prefix[18:20] = (0xB7).to_bytes(2, "little")
    prefix[0x20 : 0x20 + len(b"libappsign4a.so")] = b"libappsign4a.so"
    directory_offset = payload_offset + len(payload)
    footer = (
        struct.pack(
            "<4sIQQQQ",
            b"MFTL",
            1,
            payload_offset,
            len(payload),
            directory_offset,
            len(directory),
        )
        + b"\x00" * 4
    )
    path.write_bytes(bytes(prefix) + payload + directory + footer)


def test_jp_encrypted_runtime_extractor_restores_libil2cpp(tmp_path: Path) -> None:
    source_path = tmp_path / "librontatre.so"
    expected = _write_mftl_tara_fixture(source_path)
    output_path = tmp_path / "libil2cpp.so"

    JpEncryptedRuntimeExtractor().extract(source_path, output_path)

    assert output_path.read_bytes() == expected


def test_jp_encrypted_runtime_extractor_rejects_missing_mftl_footer(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "librontatre.so"
    source_path.write_bytes(b"\x7fELF" + b"\x00" * 128)

    with pytest.raises(JpRuntimeDecryptError):
        JpEncryptedRuntimeExtractor().extract(source_path, tmp_path / "libil2cpp.so")


def test_jp_runtime_payload_locator_uses_mftl_structure_not_filename(
    tmp_path: Path,
) -> None:
    unrelated = tmp_path / "librontatre.so"
    unrelated.write_bytes(b"\x7fELFnot-an-mftl-container")
    renamed = tmp_path / "libgedenedo.so"
    _write_mftl_marker(renamed)

    payload = locate_jp_runtime_payload(tmp_path)

    assert payload is not None
    assert payload.path == renamed
    assert payload.encrypted


def test_jp_runtime_payload_locator_rejects_multiple_mftl_candidates(
    tmp_path: Path,
) -> None:
    _write_mftl_marker(tmp_path / "first.so")
    _write_mftl_marker(tmp_path / "second.so")

    with pytest.raises(JpRuntimePayloadError):
        locate_jp_runtime_payload(tmp_path)


def test_jp_runtime_payload_locator_requires_internal_soname_marker(
    tmp_path: Path,
) -> None:
    candidate = tmp_path / "renamed.so"
    _write_mftl_marker(candidate)
    candidate.write_bytes(
        candidate.read_bytes().replace(b"libappsign4a.so", b"noappsign4a.so?")
    )

    with pytest.raises(JpRuntimePayloadError):
        locate_jp_runtime_payload(tmp_path)


@dataclass
class RecordingRuntimeExtractor:
    calls: list[tuple[Path, Path]]

    def extract(self, source_path: Path, output_path: Path) -> None:
        self.calls.append((source_path, output_path))
        output_path.write_bytes(b"\x7fELFrestored")


def _write_jp_package_runtime(
    context: ExecutionContext,
    *,
    binary_name: str,
    binary_data: bytes,
) -> Path:
    package_root = (
        context.workspace.runtime_state
        / context.require_resource_version()
        / "Package"
        / "Extracted"
    )
    runtime_dir = package_root / "lib" / "arm64-v8a"
    runtime_dir.mkdir(parents=True)
    (runtime_dir / binary_name).write_bytes(binary_data)
    metadata_path = (
        package_root
        / "assets"
        / "bin"
        / "Data"
        / "Managed"
        / "Metadata"
        / "global-metadata.dat"
    )
    metadata_path.parent.mkdir(parents=True)
    metadata_path.write_bytes(b"metadata")
    managers_path = package_root / "assets" / "bin" / "Data" / "globalgamemanagers"
    managers_path.parent.mkdir(parents=True, exist_ok=True)
    managers_path.write_bytes(b"Unity 2021.3.45f1")
    return runtime_dir / binary_name


def test_jp_runtime_preparer_rejects_plaintext_only_libil2cpp(tmp_path: Path) -> None:
    context = _build_context(tmp_path)
    _write_jp_package_runtime(
        context,
        binary_name="libil2cpp.so",
        binary_data=b"\x7fELFexisting",
    )
    extractor = RecordingRuntimeExtractor([])

    with pytest.raises(FileNotFoundError):
        JPRuntimeAssetPreparer(
            RecordingLogger(),
            extractor=extractor,
        ).prepare(context)

    assert extractor.calls == []


def test_jp_runtime_preparer_restores_libil2cpp_from_renamed_mftl_container(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path)
    encrypted_binary = _write_jp_package_runtime(
        context,
        binary_name="libgedenedo.so",
        binary_data=b"",
    )
    _write_mftl_marker(encrypted_binary)
    extractor = RecordingRuntimeExtractor([])

    prepared = JPRuntimeAssetPreparer(
        RecordingLogger(),
        extractor=extractor,
    ).prepare(context)

    assert len(extractor.calls) == 1
    source_path, output_path = extractor.calls[0]
    assert source_path.name == "libgedenedo.so"
    assert output_path.name == "libil2cpp.so"
    assert source_path == encrypted_binary
    assert source_path.parent != output_path.parent
    assert prepared.binary_path.read_bytes() == b"\x7fELFrestored"
    assert not (prepared.root_dir / "libgedenedo.so").exists()
    assert prepared.provenance["type"] == "jp_mftl"


def test_jp_mftl_extractor_never_reads_parent_as_one_bytes_object(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "random-parent.so"
    _write_mftl_tara_fixture(source_path)
    output_path = tmp_path / "libil2cpp.so"

    def fail_read_bytes(_path: Path) -> bytes:
        raise AssertionError("MFTL extraction must stream the parent container")

    monkeypatch.setattr(Path, "read_bytes", fail_read_bytes)

    JpEncryptedRuntimeExtractor().extract(source_path, output_path)

    with output_path.open("rb") as output:
        assert output.read(6) == b"\x7fELF\x02\x01"


def test_default_region_service_profile_uses_jp_runtime_preparer() -> None:
    preparer = DEFAULT_REGION_GATEWAY_REGISTRY.resolve("jp").runtime.asset_preparer(
        http_client=object(),
        logger=RecordingLogger(),
        cancellation=NeverCancelled(),
    )

    assert isinstance(preparer, JPRuntimeAssetPreparer)
