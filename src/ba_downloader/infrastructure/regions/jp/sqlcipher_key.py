from __future__ import annotations

from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.infrastructure.http.client import ResilientHttpClient

JP_SQLCIPHER_KEY_URL = "https://ba.zmkimu.com/jp"
JP_SQLCIPHER_KEY_TIMEOUT = 10.0


class JpSqlCipherKeyProvider:
    def __init__(self, context: RuntimeContext) -> None:
        self.context = context

    def get_key_hex(self) -> str:
        client = ResilientHttpClient(
            proxy_url=self.context.proxy_url or None,
            max_retries=self.context.max_retries,
        )
        try:
            response = client.request(
                "GET",
                JP_SQLCIPHER_KEY_URL,
                timeout=JP_SQLCIPHER_KEY_TIMEOUT,
            )
        except Exception as exc:
            raise LookupError(
                "Failed to fetch JP SQLCipher key from "
                f"{JP_SQLCIPHER_KEY_URL}. Pass --sqlcipher-key-hex to override."
            ) from exc
        finally:
            client.close()

        if response.status_code != 200:
            raise LookupError(
                "Failed to fetch JP SQLCipher key from "
                f"{JP_SQLCIPHER_KEY_URL}: HTTP {response.status_code}. "
                "Pass --sqlcipher-key-hex to override."
            )

        content_type = response.header("Content-Type").lower()
        if content_type and "text/plain" not in content_type:
            raise LookupError(
                "JP SQLCipher key endpoint returned unexpected content type "
                f"'{content_type}'. Pass --sqlcipher-key-hex to override."
            )

        return response.text.strip()
