from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from ba_downloader.api.app import create_app
from ba_downloader.infrastructure.extraction.media.exporter import (
    media_extraction_lock_path,
)
from ba_downloader.infrastructure.files.lock import InterprocessFileLock
from support.fixtures import build_execution_context


def _create_context(client: TestClient, **changes: object) -> dict[str, object]:
    payload: dict[str, object] = {"region": "cn"}
    payload.update(changes)
    response = client.post("/api/v1/contexts", json=payload)
    assert response.status_code in {200, 201}
    return response.json()


def test_context_is_normalized_redacted_and_deduplicated(tmp_path: object) -> None:
    payload = {
        "region": "jp",
        "workspace": str(tmp_path),
        "proxy": "https://user:password@example.test:8443",
        "sqlcipher_key": "a" * 64,
    }
    with TestClient(create_app(port=9230)) as client:
        first = client.post("/api/v1/contexts", json=payload)
        second = client.post("/api/v1/contexts", json=payload)

    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["proxy_configured"] is True
    assert first.json()["sqlcipher_key_configured"] is True
    assert "password" not in first.text
    assert "a" * 64 not in first.text


def test_context_refresh_derives_new_unresolved_context() -> None:
    with TestClient(create_app(port=9230)) as client:
        original = _create_context(client)
        refreshed = client.post(f"/api/v1/contexts/{original['id']}/refresh")

    assert refreshed.status_code == 201
    assert refreshed.json()["id"] != original["id"]
    assert refreshed.json()["resource_version"] is None


def test_typed_job_submission() -> None:
    with TestClient(create_app(port=9230)) as client:
        context = _create_context(client)
        created = client.post(
            "/api/v1/jobs",
            json={"operation": "assets.extract", "context_id": context["id"]},
        )

    assert created.status_code == 202
    assert created.json()["operation"] == "extract"


def test_media_extraction_conflict_uses_http_409_wire(tmp_path: Path) -> None:
    execution_context = build_execution_context(
        tmp_path,
        region="cn",
        version="",
    )
    with TestClient(create_app(port=9230)) as client:
        context = _create_context(client, workspace=str(tmp_path))
        with InterprocessFileLock(
            media_extraction_lock_path(execution_context),
            operation="external media extraction",
        ):
            response = client.post(
                "/api/v1/jobs",
                json={
                    "operation": "assets.extract",
                    "context_id": context["id"],
                    "resources": ["media"],
                },
            )

    assert response.status_code == 409
    assert response.json()["code"] == "MEDIA_EXTRACTION_CONFLICT"


def test_openapi_exposes_unique_explicit_operation_ids() -> None:
    schema = create_app(port=9230).openapi()
    operation_ids = [
        operation["operationId"]
        for methods in schema["paths"].values()
        for method, operation in methods.items()
        if method in {"get", "post", "put", "delete", "patch"}
    ]
    assert len(operation_ids) == len(set(operation_ids))
    assert "createContext" in operation_ids
    assert "createJob" in operation_ids
    assert "downloadFile" in operation_ids


def test_private_network_preflight_is_allowed_without_credentials() -> None:
    with TestClient(create_app(port=9230)) as client:
        response = client.options(
            "/api/v1/discovery",
            headers={
                "Origin": "https://remote.example",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Private-Network": "true",
            },
        )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"
    assert response.headers["access-control-allow-private-network"] == "true"
    assert "access-control-allow-credentials" not in response.headers


def test_validation_errors_do_not_echo_request_values() -> None:
    secret = "SECRET_UNKNOWN_VALUE"
    with TestClient(create_app(port=9230)) as client:
        response = client.post(
            "/api/v1/contexts",
            json={"region": "invalid", "sqlcipher_key": secret, "unknown": secret},
        )
    assert response.status_code == 422
    assert all(
        set(error) == {"type", "loc", "msg"} for error in response.json()["errors"]
    )
    assert secret not in response.text


def test_context_file_content_supports_http_range(tmp_path: Path) -> None:
    raw = tmp_path / "cn" / "android" / "raw"
    raw.mkdir(parents=True)
    (raw / "asset.bin").write_bytes(b"0123456789")
    with TestClient(create_app(port=9230)) as client:
        context = _create_context(client, workspace=str(tmp_path))
        listed = client.get(
            f"/api/v1/contexts/{context['id']}/files", params={"scope": "raw"}
        ).json()["items"]
        response = client.get(
            f"/api/v1/contexts/{context['id']}/files/{listed[0]['id']}/content",
            headers={"Range": "bytes=2-5"},
        )

    assert response.status_code == 206
    assert response.content == b"2345"
    assert response.headers["content-range"] == "bytes 2-5/10"
