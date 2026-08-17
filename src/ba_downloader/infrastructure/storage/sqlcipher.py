from __future__ import annotations

import hashlib
import hmac
import json
import os
import shutil
import tempfile
from dataclasses import asdict, replace
from pathlib import Path
from typing import Protocol

from Crypto.Cipher import AES

from ba_downloader.domain.models.database import DatabaseSourceIdentity
from ba_downloader.domain.models.runtime import RuntimeContext

SQLITE_HEADER = b"SQLite format 3\x00"


class SqlCipherRawExportError(RuntimeError):
    """Raised when a SQLCipher raw-page export fails."""


class SqlCipherRawExporter:
    VERSION = "sqlcipher-raw-v1"
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


class SqlCipherKeyProvider(Protocol):
    def get_key_hex(self) -> str: ...


def is_sqlite_database(path: Path) -> bool:
    try:
        with path.open("rb") as database_file:
            return database_file.read(len(SQLITE_HEADER)) == SQLITE_HEADER
    except OSError:
        return False


class SqlCipherDatabaseResolver:
    CACHE_SCHEMA_VERSION = 1

    def __init__(
        self,
        context: RuntimeContext,
        *,
        exporter: SqlCipherExporter | None = None,
        key_provider: SqlCipherKeyProvider | None = None,
    ) -> None:
        self.context = context
        self.exporter = exporter or SqlCipherRawExporter()
        self.key_provider = key_provider
        self._cache: dict[Path, Path] = {}
        self._resolved_key_hex: str | None = None

    def resolve(self, database_path: Path) -> Path:
        database_path = database_path.resolve()
        if database_path in self._cache:
            return self._cache[database_path]

        if is_sqlite_database(database_path):
            self._cache[database_path] = database_path
            return database_path

        key_hex = self._resolve_key_hex()
        identity = self._build_source_identity(database_path, key_hex)
        cache_key = self._identity_digest(identity)
        cache_scope = (
            Path(self.context.temp_dir)
            / "SQLCipher"
            / "cache"
            / self.context.region
            / self.context.platform
        ).resolve()
        entry_root = cache_scope / cache_key
        output_path = entry_root / f"{database_path.name}.sqlite.db"
        manifest_path = entry_root / "manifest.json"
        if self._is_valid_cache_hit(manifest_path, output_path, identity):
            self._cache[database_path] = output_path
            return output_path

        if entry_root.exists():
            shutil.rmtree(entry_root)
        cache_scope.mkdir(parents=True, exist_ok=True)
        staging_root = Path(tempfile.mkdtemp(prefix=f".{cache_key}.", dir=cache_scope))
        staged_output = staging_root / output_path.name
        try:
            self.exporter.export(database_path, staged_output, key_hex)
            if not is_sqlite_database(staged_output):
                raise SqlCipherRawExportError(
                    "SQLCipher exporter produced a file without a SQLite header."
                )
            output_hash = self._sha256_file(staged_output)
            output_size = staged_output.stat().st_size
            entry_root.mkdir(parents=True, exist_ok=True)
            os.replace(staged_output, output_path)
            output_stat = output_path.stat()
            self._write_manifest(
                manifest_path,
                {
                    "schema_version": self.CACHE_SCHEMA_VERSION,
                    "complete": True,
                    "source_identity": asdict(identity),
                    "output": {
                        "name": output_path.name,
                        "size": output_size,
                        "sha256": output_hash,
                        "mtime_ns": output_stat.st_mtime_ns,
                    },
                },
            )
        except BaseException:
            if entry_root.exists() and not manifest_path.is_file():
                shutil.rmtree(entry_root, ignore_errors=True)
            raise
        finally:
            shutil.rmtree(staging_root, ignore_errors=True)

        self._cache[database_path] = output_path
        self._prune_old_entries(cache_scope, keep={cache_key})
        return output_path

    def invalidate(self, database_path: Path) -> None:
        source_path = database_path.resolve()
        resolved_path = self._cache.pop(source_path, None)
        if resolved_path is None or resolved_path == source_path:
            return
        cache_scope = (
            Path(self.context.temp_dir)
            / "SQLCipher"
            / "cache"
            / self.context.region
            / self.context.platform
        ).resolve()
        try:
            entry_root = resolved_path.parent.resolve()
            entry_root.relative_to(cache_scope)
        except (OSError, ValueError):
            return
        shutil.rmtree(entry_root, ignore_errors=True)

    def _build_source_identity(
        self,
        database_path: Path,
        key_hex: str,
    ) -> DatabaseSourceIdentity:
        source = self.context.database_source_identity
        exporter_version = str(
            getattr(
                self.exporter,
                "VERSION",
                f"{type(self.exporter).__module__}.{type(self.exporter).__qualname__}:1",
            )
        )
        key_id = hashlib.sha256(bytes.fromhex(key_hex.strip())).hexdigest()[:16]
        if source is None:
            source = DatabaseSourceIdentity(
                region=self.context.region,
                platform=self.context.platform,
                release=self.context.version,
                size=database_path.stat().st_size,
                checksum="unavailable",
            )
        if source.size != database_path.stat().st_size:
            raise SqlCipherRawExportError(
                "Downloaded database size does not match its catalog identity."
            )
        return replace(
            source,
            exporter_version=exporter_version,
            key_id=key_id,
        )

    @staticmethod
    def _identity_digest(identity: DatabaseSourceIdentity) -> str:
        payload = json.dumps(
            asdict(identity),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def _is_valid_cache_hit(
        self,
        manifest_path: Path,
        output_path: Path,
        identity: DatabaseSourceIdentity,
    ) -> bool:
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            output = payload["output"]
            stat = output_path.stat()
            if not (
                payload.get("schema_version") == self.CACHE_SCHEMA_VERSION
                and payload.get("complete") is True
                and payload.get("source_identity") == asdict(identity)
                and output.get("name") == output_path.name
                and output.get("size") == stat.st_size
                and isinstance(output.get("sha256"), str)
                and is_sqlite_database(output_path)
            ):
                return False
            if output.get("mtime_ns") == stat.st_mtime_ns:
                return True
            if self._sha256_file(output_path) != output["sha256"]:
                return False
            output["mtime_ns"] = stat.st_mtime_ns
            self._write_manifest(manifest_path, payload)
            return True
        except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
            return False

    @staticmethod
    def _write_manifest(path: Path, payload: dict[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temp_name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
        )
        temp_path = Path(temp_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, path)
        except BaseException:
            temp_path.unlink(missing_ok=True)
            raise

    @staticmethod
    def _sha256_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _prune_old_entries(cache_scope: Path, *, keep: set[str]) -> None:
        entries = sorted(
            (
                path
                for path in cache_scope.iterdir()
                if path.is_dir()
                and len(path.name) == 64
                and all(character in "0123456789abcdef" for character in path.name)
            ),
            key=lambda path: path.stat().st_mtime_ns,
            reverse=True,
        )
        retained = set(keep)
        for path in entries:
            if path.name not in retained:
                retained.add(path.name)
                break
        for path in entries:
            if path.name not in retained:
                shutil.rmtree(path, ignore_errors=True)

    def _resolve_key_hex(self) -> str:
        manual_key_hex = self.context.sqlcipher_key_hex.strip()
        if manual_key_hex:
            return manual_key_hex
        if self._resolved_key_hex is not None:
            return self._resolved_key_hex
        if self.key_provider is None:
            raise LookupError("Encrypted table databases require --sqlcipher-key.")

        try:
            key_hex = self.key_provider.get_key_hex().strip()
        except LookupError:
            raise
        except Exception as exc:
            raise LookupError(
                "Failed to resolve SQLCipher key automatically. "
                "Pass --sqlcipher-key to override."
            ) from exc

        try:
            SqlCipherRawExporter._decode_raw_key(key_hex)
        except SqlCipherRawExportError as exc:
            raise LookupError(
                "Automatic SQLCipher key must be a 64-character hex string. "
                "Pass --sqlcipher-key to override."
            ) from exc

        self._resolved_key_hex = key_hex
        return key_hex
