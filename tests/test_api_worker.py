from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any

from ba_downloader.api.worker import run_application_job
from ba_downloader.application.operations import (
    ApplicationOperation,
    ApplicationOperationCommand,
)
from ba_downloader.domain.models.runtime import RuntimeContext


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
    context = RuntimeContext(
        region="jp",
        threads=1,
        version="1",
        raw_dir=str(tmp_path / "raw"),
        extract_dir=str(tmp_path / "extracted"),
        temp_dir=str(tmp_path / "temp"),
        resource_type=("bundle",),
        proxy_url=f"http://user:{proxy_password}@example.test",
        max_retries=1,
        search=(),
        advanced_search=(),
        work_dir=str(tmp_path),
        sqlcipher_key_hex=secret_key,
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
        "ba_downloader.api.worker.application_operation_executor",
        executor_scope,
    )
    terminal = _TerminalSender()

    run_application_job(
        ApplicationOperationCommand(ApplicationOperation.extract),
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
