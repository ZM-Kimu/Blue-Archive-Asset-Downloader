from dataclasses import dataclass
from typing import Any, Callable, Literal, Mapping, Protocol


TransportKind = Literal["default", "browser"]


@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    headers: Mapping[str, str]
    content: bytes
    url: str

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")

    def json(self) -> Any:
        import json

        return json.loads(self.text)


@dataclass(frozen=True)
class DownloadResult:
    path: str
    bytes_written: int
    status_code: int
    headers: Mapping[str, str]
    url: str


class HttpClientPort(Protocol):
    def request(
        self,
        method: Literal["GET", "POST", "HEAD"],
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        json: Any | None = None,
        data: Any | None = None,
        params: Mapping[str, Any] | None = None,
        transport: TransportKind = "default",
        timeout: float = 10.0,
    ) -> HttpResponse:
        ...

    def download_to_file(
        self,
        url: str,
        destination: str,
        *,
        headers: Mapping[str, str] | None = None,
        transport: TransportKind = "default",
        timeout: float = 300.0,
        progress_callback: Callable[[int], None] | None = None,
        should_stop: Callable[[], bool] | None = None,
    ) -> DownloadResult:
        ...

    def close(self) -> None:
        ...
