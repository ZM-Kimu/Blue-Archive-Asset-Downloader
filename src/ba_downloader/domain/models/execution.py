from __future__ import annotations

import re
from dataclasses import dataclass, replace

from ba_downloader.domain.exceptions import ConfigError
from ba_downloader.domain.models.region import Platform, Region
from ba_downloader.domain.models.workspace import WorkspaceLayout

SQLCIPHER_KEY_PATTERN = re.compile(r"[0-9a-fA-F]{64}")


@dataclass(frozen=True, slots=True)
class ExecutionContext:
    region: Region
    platform: Platform
    workspace: WorkspaceLayout
    proxy_url: str = ""
    max_retries: int = 5
    sqlcipher_key: str = ""
    resource_version: str | None = None

    def __post_init__(self) -> None:
        if self.workspace.region != self.region:
            raise ConfigError("Execution context and workspace region must match.")
        if self.workspace.platform != self.platform:
            raise ConfigError("Execution context and workspace platform must match.")
        if self.max_retries < 0:
            raise ConfigError("max_retries must be greater than or equal to zero.")
        if self.sqlcipher_key and not SQLCIPHER_KEY_PATTERN.fullmatch(
            self.sqlcipher_key
        ):
            raise ConfigError("SQLCipher key must contain exactly 64 hex characters.")
        if self.resource_version is not None and not self.resource_version.strip():
            raise ConfigError("Resource version must not be empty.")

    def resolve_resource_version(self, version: str) -> ExecutionContext:
        normalized = version.strip()
        if not normalized:
            raise ConfigError("Resource version must not be empty.")
        if self.resource_version is None:
            return replace(self, resource_version=normalized)
        if self.resource_version != normalized:
            raise ConfigError(
                "Execution context resource version is already resolved as "
                f"'{self.resource_version}'."
            )
        return self

    def without_resource_version(self) -> ExecutionContext:
        return replace(self, resource_version=None)

    def require_resource_version(self) -> str:
        if self.resource_version is None:
            raise ConfigError("Resource version has not been resolved.")
        return self.resource_version

    @property
    def proxy(self) -> dict[str, str] | None:
        if not self.proxy_url:
            return None
        return {"http": self.proxy_url, "https": self.proxy_url}
