from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any

from ba_downloader.api.worker import run_application_job
from ba_downloader.application.contracts import AssetsExtractCommand
from support.fixtures import build_execution_context


class _TerminalSender:
    def __init__(self) -> None:
        self.messages: list[dict[str, object]] = []

    def send(self, message: dict[str, object]) -> None:
        self.messages.append(message)

    def close(self) -> None:
        pass


def test_worker_redacts_secrets_from_success_warnings(
    monkeypatch: Any,
    tmp_path: Any,
) -> None:
    secret_key = "a" * 64
    proxy_password = "secret-password"
    context = build_execution_context(
        tmp_path,
        region="jp",
        version="1",
        proxy_url=f"http://user:{proxy_password}@example.test",
        max_retries=1,
        sqlcipher_key=secret_key,
    )

    @contextmanager
    def executor_scope(*_args: object, **_kwargs: object) -> Iterator[Any]:
        yield SimpleNamespace(
            execute=lambda _command: SimpleNamespace(
                context=context,
                artifacts=(),
                catalog=None,
                statistics=(),
                warnings=(f"failed with {secret_key} via {proxy_password}",),
            )
        )

    monkeypatch.setattr(
        "ba_downloader.api.worker.ExecutionScope",
        executor_scope,
    )
    terminal = _TerminalSender()

    run_application_job(
        AssetsExtractCommand(),
        context,
        SimpleNamespace(put=lambda _event: None),
        terminal,
        SimpleNamespace(is_set=lambda: False),
    )

    payload = terminal.messages[0]["payload"]
    assert isinstance(payload, dict)
    warnings = payload["warnings"]
    assert secret_key not in str(warnings)
    assert proxy_password not in str(warnings)
    assert warnings == ("failed with *** via ***",)
