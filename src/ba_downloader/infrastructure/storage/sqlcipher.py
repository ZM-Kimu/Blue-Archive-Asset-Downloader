from __future__ import annotations

import hashlib
import hmac
from pathlib import Path
from typing import Protocol

from Crypto.Cipher import AES

from ba_downloader.domain.models.runtime import RuntimeContext

SQLITE_HEADER = b"SQLite format 3\x00"


class SqlCipherRawExportError(RuntimeError):
    """Raised when a SQLCipher raw-page export fails."""


class SqlCipherRawExporter:
    PAGE_SIZE = 4096
    RESERVE_SIZE = 80
    IV_SIZE = 16
    HMAC_SIZE = 64
    SALT_SIZE = 16
    HMAC_KDF_ITERATIONS = 2
    HMAC_SALT_MASK = 0x3A

    def export(self, input_path: Path, output_path: Path, key_hex: str) -> None:
        key = self._decode_raw_key(key_hex)
        input_size = input_path.stat().st_size
        if input_size == 0 or input_size % self.PAGE_SIZE != 0:
            raise SqlCipherRawExportError(
                f"Input size must be a non-zero multiple of page size {self.PAGE_SIZE}: {input_path}."
            )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        temp_output_path = output_path.with_name(f"{output_path.name}.tmp")
        page_count = input_size // self.PAGE_SIZE
        usable_size = self.PAGE_SIZE - self.RESERVE_SIZE
        try:
            with (
                input_path.open("rb") as input_file,
                temp_output_path.open("wb") as output_file,
            ):
                hmac_key = b""
                for page_no in range(1, page_count + 1):
                    page = input_file.read(self.PAGE_SIZE)
                    if len(page) != self.PAGE_SIZE:
                        raise SqlCipherRawExportError(
                            f"Unexpected end of input at SQLCipher page {page_no}."
                        )
                    if page_no == 1:
                        hmac_key = self._derive_hmac_key(
                            key,
                            page[: self.SALT_SIZE],
                        )

                    cipher_offset = self.SALT_SIZE if page_no == 1 else 0
                    cipher_length = usable_size - cipher_offset
                    iv_offset = usable_size
                    hmac_offset = usable_size + self.IV_SIZE

                    self._verify_page_hmac(
                        page,
                        cipher_offset,
                        cipher_length,
                        iv_offset,
                        hmac_offset,
                        page_no,
                        hmac_key,
                    )
                    output_file.write(
                        self._decrypt_page(
                            key,
                            page,
                            cipher_offset,
                            cipher_length,
                            iv_offset,
                            page_no,
                        )
                    )
            temp_output_path.replace(output_path)
        except Exception:
            temp_output_path.unlink(missing_ok=True)
            raise

    @classmethod
    def _decode_raw_key(cls, key_hex: str) -> bytes:
        normalized = key_hex.strip()
        if len(normalized) != 64:
            raise SqlCipherRawExportError(
                f"Expected 32-byte SQLCipher raw key as 64 hex chars, got {len(normalized)}."
            )
        try:
            return bytes.fromhex(normalized)
        except ValueError as exc:
            raise SqlCipherRawExportError(
                "SQLCipher raw key must be valid hex."
            ) from exc

    @classmethod
    def _derive_hmac_key(cls, raw_key: bytes, file_salt: bytes) -> bytes:
        hmac_salt = bytes(value ^ cls.HMAC_SALT_MASK for value in file_salt)
        return hashlib.pbkdf2_hmac(
            "sha512",
            raw_key,
            hmac_salt,
            cls.HMAC_KDF_ITERATIONS,
            32,
        )

    @classmethod
    def _verify_page_hmac(
        cls,
        page: bytes,
        cipher_offset: int,
        cipher_length: int,
        iv_offset: int,
        hmac_offset: int,
        page_no: int,
        hmac_key: bytes,
    ) -> None:
        mac_input = (
            page[cipher_offset : cipher_offset + cipher_length]
            + page[iv_offset : iv_offset + cls.IV_SIZE]
            + page_no.to_bytes(4, "little")
        )
        actual = hmac.new(hmac_key, mac_input, hashlib.sha512).digest()
        expected = page[hmac_offset : hmac_offset + cls.HMAC_SIZE]
        if not hmac.compare_digest(actual[: cls.HMAC_SIZE], expected):
            raise SqlCipherRawExportError(
                f"HMAC verification failed at page {page_no}."
            )

    @classmethod
    def _decrypt_page(
        cls,
        key: bytes,
        page: bytes,
        cipher_offset: int,
        cipher_length: int,
        iv_offset: int,
        page_no: int,
    ) -> bytes:
        plain_page = bytearray(cls.PAGE_SIZE)
        destination_offset = 0
        if page_no == 1:
            plain_page[: len(SQLITE_HEADER)] = SQLITE_HEADER
            destination_offset = cls.SALT_SIZE

        decrypted = AES.new(
            key,
            AES.MODE_CBC,
            page[iv_offset : iv_offset + cls.IV_SIZE],
        ).decrypt(page[cipher_offset : cipher_offset + cipher_length])
        if len(decrypted) != cipher_length:
            raise SqlCipherRawExportError("AES-CBC page decrypt failed.")
        plain_page[destination_offset : destination_offset + cipher_length] = decrypted
        return bytes(plain_page)


class SqlCipherExporter(Protocol):
    def export(self, input_path: Path, output_path: Path, key_hex: str) -> None: ...


def is_sqlite_database(path: Path) -> bool:
    try:
        return path.read_bytes()[: len(SQLITE_HEADER)] == SQLITE_HEADER
    except OSError:
        return False


class SqlCipherDatabaseResolver:
    def __init__(
        self,
        context: RuntimeContext,
        *,
        exporter: SqlCipherExporter | None = None,
    ) -> None:
        self.context = context
        self.exporter = exporter or SqlCipherRawExporter()
        self._cache: dict[Path, Path] = {}

    def resolve(self, database_path: Path) -> Path:
        database_path = database_path.resolve()
        if is_sqlite_database(database_path):
            return database_path

        key_hex = self.context.sqlcipher_key_hex.strip()
        if not key_hex:
            raise LookupError("Encrypted table databases require --sqlcipher-key-hex.")

        if database_path in self._cache:
            return self._cache[database_path]

        output_path = (
            Path(self.context.temp_dir)
            / "SQLCipher"
            / f"{database_path.name}.sqlite.db"
        ).resolve()
        self.exporter.export(database_path, output_path, key_hex)
        self._cache[database_path] = output_path
        return output_path
