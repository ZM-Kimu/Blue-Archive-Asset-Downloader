from dataclasses import dataclass
from typing import Any, Callable, Literal, Mapping, Protocol


TransportKind = Literal["default", "browser"]


def get_header(headers: Mapping[str, str], name: str, default: str = "") -> str:
    expected = name.casefold()
    for key, value in headers.items():
        if key.casefold() == expected:
            return str(value)
    return default


@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    headers: Mapping[str, str]
    content: bytes
    url: str

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")

    def header(self, name: str, default: str = "") -> str:
        return get_header(self.headers, name, default)

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

    def header(self, name: str, default: str = "") -> str:
        return get_header(self.headers, name, default)


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
