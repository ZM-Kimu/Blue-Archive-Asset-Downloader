from __future__ import annotations

from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.infrastructure.storage.remote_sqlcipher_key import (
    DEFAULT_SQLCIPHER_KEY_TIMEOUT,
    RemoteSqlCipherKeyProvider,
)

JP_SQLCIPHER_KEY_URL = "https://ba.zmkimu.com/jp"
JP_SQLCIPHER_KEY_TIMEOUT = DEFAULT_SQLCIPHER_KEY_TIMEOUT


class JpSqlCipherKeyProvider(RemoteSqlCipherKeyProvider):
    def __init__(self, context: ExecutionContext) -> None:
        super().__init__(
            context,
            region="JP",
            endpoint=JP_SQLCIPHER_KEY_URL,
            timeout=JP_SQLCIPHER_KEY_TIMEOUT,
        )
