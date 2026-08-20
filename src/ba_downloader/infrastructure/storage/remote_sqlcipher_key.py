from __future__ import annotations

from ba_downloader.domain.models.execution import ExecutionContext
from ba_downloader.infrastructure.http.client import ResilientHttpClient

DEFAULT_SQLCIPHER_KEY_TIMEOUT = 10.0


class RemoteSqlCipherKeyProvider:
    def __init__(
        self,
        context: ExecutionContext,
        *,
        region: str,
        endpoint: str,
        timeout: float = DEFAULT_SQLCIPHER_KEY_TIMEOUT,
    ) -> None:
        self.context = context
        self.region = region.upper()
        self.endpoint = endpoint
        self.timeout = timeout

    def get_key_hex(self) -> str:
        client = ResilientHttpClient(
            proxy_url=self.context.proxy_url or None,
            max_retries=self.context.max_retries,
        )
        try:
            response = client.request(
                "GET",
                self.endpoint,
                timeout=self.timeout,
            )
        except Exception as exc:
            raise LookupError(
                f"Failed to fetch {self.region} SQLCipher key from {self.endpoint}. "
                "Pass --sqlcipher-key to override."
            ) from exc
        finally:
            client.close()

        if response.status_code != 200:
            raise LookupError(
                f"Failed to fetch {self.region} SQLCipher key from {self.endpoint}: "
                f"HTTP {response.status_code}. Pass --sqlcipher-key to override."
            )

        content_type = response.header("Content-Type").lower()
        if content_type and "text/plain" not in content_type:
            raise LookupError(
                f"{self.region} SQLCipher key endpoint returned unexpected content "
                f"type '{content_type}'. Pass --sqlcipher-key to override."
            )

        return response.text.strip()
