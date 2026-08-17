from __future__ import annotations

import multiprocessing
import socket
from collections.abc import Callable, Iterable
from importlib.util import find_spec
from typing import Any

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORTS = range(9230, 9240)


class ApiDependencyError(RuntimeError):
    pass


class ApiBindError(RuntimeError):
    pass


def bind_listen_socket(
    host: str,
    port: int | None,
    *,
    fallback_ports: Iterable[int] = DEFAULT_PORTS,
) -> tuple[socket.socket, int]:
    candidates = (port,) if port is not None else tuple(fallback_ports)
    last_error: OSError | None = None
    for candidate in candidates:
        if not 1 <= candidate <= 65535:
            raise ApiBindError(f"Invalid HTTP API port '{candidate}'.")
        try:
            listener = socket.create_server((host, candidate), backlog=128)
        except OSError as exc:
            last_error = exc
            if port is not None:
                break
            continue
        listener.set_inheritable(True)
        return listener, candidate

    if port is not None:
        target = f"{host}:{port}"
        detail = str(last_error) if last_error is not None else "unknown bind error"
        raise ApiBindError(f"HTTP API cannot bind to {target}: {detail}")
    raise ApiBindError(
        "HTTP API cannot bind to any default port from 9230 through 9239."
    )


def api_display_url(host: str, port: int) -> str:
    display_host = "127.0.0.1" if host in {"0.0.0.0", "::", "[::]"} else host
    if ":" in display_host and not display_host.startswith("["):
        display_host = f"[{display_host}]"
    return f"http://{display_host}:{port}"


def serve(
    host: str = DEFAULT_HOST,
    port: int | None = None,
    *,
    catalog_loader: Callable[[Any], tuple[Any, Any]] | None = None,
    character_index_loader: Callable[[Any], Any] | None = None,
    character_index_searcher: Callable[[Any, list[str]], list[str]] | None = None,
    log_info: Callable[[str], None] | None = None,
) -> int:
    missing = [name for name in ("fastapi", "uvicorn") if find_spec(name) is None]
    if missing:
        raise ApiDependencyError(
            "HTTP API dependencies are not installed. "
            "Install them with 'pip install ba-downloader[api]'."
        )

    import uvicorn

    from ba_downloader.api.app import create_app

    listener, selected_port = bind_listen_socket(host, port)
    server_holder: dict[str, Any] = {}

    def request_shutdown() -> None:
        active_server = server_holder.get("server")
        if active_server is not None:
            active_server.should_exit = True

    application = create_app(
        port=selected_port,
        shutdown_callback=request_shutdown,
        catalog_loader=catalog_loader,
        character_index_loader=character_index_loader,
        character_index_searcher=character_index_searcher,
    )
    config = uvicorn.Config(
        application,
        host=host,
        port=selected_port,
        workers=1,
        log_level="info",
    )
    server = uvicorn.Server(config)
    server_holder["server"] = server
    display_url = api_display_url(host, selected_port)
    if log_info is not None:
        log_info(f"HTTP API available at {display_url}")
        log_info(f"OpenAPI documentation at {display_url}/docs")
    multiprocessing.freeze_support()
    try:
        server.run(sockets=[listener])
    finally:
        listener.close()
    return 0
