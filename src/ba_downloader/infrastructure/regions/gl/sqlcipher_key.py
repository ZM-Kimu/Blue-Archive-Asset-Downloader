from __future__ import annotations

from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.infrastructure.storage.remote_sqlcipher_key import (
    RemoteSqlCipherKeyProvider,
)

GL_SQLCIPHER_KEY_URL = "https://ba.zmkimu.com/gl"


class GlSqlCipherKeyProvider(RemoteSqlCipherKeyProvider):
    def __init__(self, context: RuntimeContext) -> None:
        super().__init__(
            context,
            region="GL",
            endpoint=GL_SQLCIPHER_KEY_URL,
        )
