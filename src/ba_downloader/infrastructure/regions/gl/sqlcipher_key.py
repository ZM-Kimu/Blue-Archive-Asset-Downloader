from __future__ import annotations

from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.infrastructure.storage.remote_sqlcipher_key import (
    RemoteSqlCipherKeyProvider,
)

GL_SQLCIPHER_KEY_URL = "https://ba.zmkimu.com/gl"


class GlSqlCipherKeyProvider(RemoteSqlCipherKeyProvider):
    def __init__(self, context: ExecutionContext) -> None:
        super().__init__(
            context,
            region="GL",
            endpoint=GL_SQLCIPHER_KEY_URL,
        )
