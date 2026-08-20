from __future__ import annotations

import socket
from unittest.mock import patch

import pytest

from ba_downloader.api.server import (
    ApiBindError,
    ApiDependencyError,
    api_display_url,
    bind_listen_socket,
    serve,
)


def test_default_port_selection_uses_next_available_port() -> None:
    occupied = socket.create_server(("127.0.0.1", 0))
    first_port = occupied.getsockname()[1]
    second_probe = socket.create_server(("127.0.0.1", 0))
    second_port = second_probe.getsockname()[1]
    second_probe.close()
    try:
        listener, selected = bind_listen_socket(
            "127.0.0.1", None, fallback_ports=(first_port, second_port)
        )
    finally:
        occupied.close()

    try:
        assert selected == second_port
    finally:
        listener.close()


def test_explicit_port_conflict_does_not_fall_back() -> None:
    occupied = socket.create_server(("127.0.0.1", 0))
    port = occupied.getsockname()[1]
    try:
        with pytest.raises(ApiBindError):
            bind_listen_socket("127.0.0.1", port)
    finally:
        occupied.close()


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("0.0.0.0", "http://127.0.0.1:9230"),
        ("::", "http://127.0.0.1:9230"),
        ("127.0.0.1", "http://127.0.0.1:9230"),
        ("::1", "http://[::1]:9230"),
        ("api.example.test", "http://api.example.test:9230"),
    ],
)
def test_api_display_url_is_browser_usable(host: str, expected: str) -> None:
    assert api_display_url(host, 9230) == expected


def test_missing_optional_dependency_has_install_guidance() -> None:
    with (
        patch("ba_downloader.api.server.find_spec", return_value=None),
        pytest.raises(ApiDependencyError),
    ):
        serve()


def test_internal_import_error_is_not_masked_as_dependency_error() -> None:
    real_import = __import__

    def failing_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "ba_downloader.api.app":
            raise ImportError("internal API defect")
        return real_import(name, *args, **kwargs)

    with (
        patch("builtins.__import__", side_effect=failing_import),
        pytest.raises(ImportError),
    ):
        serve("127.0.0.1", 9230)
