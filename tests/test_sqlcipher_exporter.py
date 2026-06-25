from __future__ import annotations

import hashlib
import hmac
import sqlite3
from pathlib import Path

import pytest
from Crypto.Cipher import AES

from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.infrastructure.extraction.table.database import TableDatabaseReader
from ba_downloader.infrastructure.storage.sqlcipher import (
    SQLITE_HEADER,
    SqlCipherDatabaseResolver,
    SqlCipherRawExporter,
    SqlCipherRawExportError,
)

RAW_KEY_HEX = "00" * 32


def _build_context(tmp_path: Path, *, key_hex: str = RAW_KEY_HEX) -> RuntimeContext:
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
        jp_sqlcipher_key_hex=key_hex,
    )


def _encrypt_sqlcipher_page(plain_page: bytes, key: bytes, salt: bytes) -> bytes:
    page_size = SqlCipherRawExporter.PAGE_SIZE
    reserve_size = SqlCipherRawExporter.RESERVE_SIZE
    iv_size = SqlCipherRawExporter.IV_SIZE
    hmac_size = SqlCipherRawExporter.HMAC_SIZE
    salt_size = SqlCipherRawExporter.SALT_SIZE
    usable_size = page_size - reserve_size
    cipher_offset = salt_size
    cipher_length = usable_size - cipher_offset
    iv = bytes.fromhex("11" * iv_size)

    encrypted = AES.new(key, AES.MODE_CBC, iv).encrypt(
        plain_page[cipher_offset : cipher_offset + cipher_length]
    )
    hmac_salt = bytes(value ^ SqlCipherRawExporter.HMAC_SALT_MASK for value in salt)
    hmac_key = hashlib.pbkdf2_hmac(
        "sha512",
        key,
        hmac_salt,
        SqlCipherRawExporter.HMAC_KDF_ITERATIONS,
        32,
    )
    digest = hmac.new(
        hmac_key,
        encrypted + iv + (1).to_bytes(4, "little"),
        hashlib.sha512,
    ).digest()

    page = bytearray(page_size)
    page[:salt_size] = salt
    page[cipher_offset : cipher_offset + cipher_length] = encrypted
    page[usable_size : usable_size + iv_size] = iv
    page[usable_size + iv_size : usable_size + iv_size + hmac_size] = digest
    return bytes(page)


def _write_sqlite_db(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE SampleDBSchema (Id INTEGER, Name TEXT)")
        connection.execute("INSERT INTO SampleDBSchema VALUES (1, 'Arona')")


def test_sqlcipher_raw_exporter_writes_sqlite_page_with_verified_hmac(
    tmp_path: Path,
) -> None:
    key = bytes.fromhex(RAW_KEY_HEX)
    salt = bytes.fromhex("22" * SqlCipherRawExporter.SALT_SIZE)
    plain_page = bytearray(SqlCipherRawExporter.PAGE_SIZE)
    plain_page[: len(SQLITE_HEADER)] = SQLITE_HEADER
    plain_page[
        16 : SqlCipherRawExporter.PAGE_SIZE - SqlCipherRawExporter.RESERVE_SIZE
    ] = bytes(
        index % 251
        for index in range(
            SqlCipherRawExporter.PAGE_SIZE - SqlCipherRawExporter.RESERVE_SIZE - 16
        )
    )
    plain_page[-SqlCipherRawExporter.RESERVE_SIZE :] = (
        b"x" * SqlCipherRawExporter.RESERVE_SIZE
    )

    encrypted_path = tmp_path / "encrypted.db"
    output_path = tmp_path / "plain.db"
    encrypted_path.write_bytes(_encrypt_sqlcipher_page(bytes(plain_page), key, salt))

    SqlCipherRawExporter().export(encrypted_path, output_path, RAW_KEY_HEX)

    exported = output_path.read_bytes()
    assert exported[: len(SQLITE_HEADER)] == SQLITE_HEADER
    assert (
        exported[
            16 : SqlCipherRawExporter.PAGE_SIZE - SqlCipherRawExporter.RESERVE_SIZE
        ]
        == plain_page[
            16 : SqlCipherRawExporter.PAGE_SIZE - SqlCipherRawExporter.RESERVE_SIZE
        ]
    )
    assert (
        exported[-SqlCipherRawExporter.RESERVE_SIZE :]
        == b"\x00" * SqlCipherRawExporter.RESERVE_SIZE
    )


def test_sqlcipher_raw_exporter_rejects_bad_hmac(tmp_path: Path) -> None:
    key = bytes.fromhex(RAW_KEY_HEX)
    salt = bytes.fromhex("33" * SqlCipherRawExporter.SALT_SIZE)
    plain_page = bytearray(SqlCipherRawExporter.PAGE_SIZE)
    plain_page[: len(SQLITE_HEADER)] = SQLITE_HEADER
    encrypted = bytearray(_encrypt_sqlcipher_page(bytes(plain_page), key, salt))
    encrypted[-1] ^= 0xFF
    encrypted_path = tmp_path / "encrypted.db"
    encrypted_path.write_bytes(encrypted)

    with pytest.raises(
        SqlCipherRawExportError, match="HMAC verification failed at page 1"
    ):
        SqlCipherRawExporter().export(
            encrypted_path,
            tmp_path / "plain.db",
            RAW_KEY_HEX,
        )


def test_sqlcipher_raw_exporter_rejects_non_page_sized_input(tmp_path: Path) -> None:
    encrypted_path = tmp_path / "encrypted.db"
    encrypted_path.write_bytes(b"not a page")

    with pytest.raises(SqlCipherRawExportError, match="multiple of page size"):
        SqlCipherRawExporter().export(
            encrypted_path,
            tmp_path / "plain.db",
            RAW_KEY_HEX,
        )


class CopyingExporter:
    def __init__(self, plaintext_path: Path) -> None:
        self.plaintext_path = plaintext_path
        self.calls: list[tuple[Path, Path, str]] = []

    def export(self, input_path: Path, output_path: Path, key_hex: str) -> None:
        self.calls.append((input_path, output_path, key_hex))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(self.plaintext_path.read_bytes())


class NoopProgress:
    def ensure_not_cancelled(self, should_stop):  # type: ignore[no-untyped-def]
        _ = should_stop

    def notify_progress(self, progress_callback, current, total, unit):  # type: ignore[no-untyped-def]
        _ = (progress_callback, current, total, unit)


def test_jp_sqlcipher_database_resolver_exports_encrypted_db_before_reading(
    tmp_path: Path,
) -> None:
    encrypted_db = tmp_path / "Raw" / "Table" / "Sample.db"
    encrypted_db.parent.mkdir(parents=True)
    encrypted_db.write_bytes(b"encrypted" * 512)
    plaintext_db = tmp_path / "plain.db"
    _write_sqlite_db(plaintext_db)
    exporter = CopyingExporter(plaintext_db)

    resolver = SqlCipherDatabaseResolver(_build_context(tmp_path), exporter=exporter)
    reader = TableDatabaseReader(
        codec_adapter=object(),  # type: ignore[arg-type]
        payload_router=object(),  # type: ignore[arg-type]
        logger=object(),  # type: ignore[arg-type]
        progress=NoopProgress(),  # type: ignore[arg-type]
        database_path_resolver=resolver,
    )

    tables = reader.process_db_file(str(encrypted_db))

    assert [table.name for table in tables] == ["SampleDBSchema"]
    assert tables[0].data == [[1, "Arona"]]
    assert len(exporter.calls) == 1
    assert exporter.calls[0][0] == encrypted_db
    assert exporter.calls[0][2] == RAW_KEY_HEX
    assert exporter.calls[0][1].parent == tmp_path / "Temp" / "SQLCipher"


def test_jp_sqlcipher_database_resolver_requires_key_for_encrypted_db(
    tmp_path: Path,
) -> None:
    encrypted_db = tmp_path / "encrypted.db"
    encrypted_db.write_bytes(b"encrypted" * 512)
    resolver = SqlCipherDatabaseResolver(_build_context(tmp_path, key_hex=""))

    with pytest.raises(LookupError, match="--jp-sqlcipher-key-hex"):
        resolver.resolve(encrypted_db)
