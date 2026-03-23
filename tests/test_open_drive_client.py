from __future__ import annotations

import json
from typing import Any

from file_migration.client.open_drive_client import OpenDriveClient


def _request_data_as_text(data: object) -> str:
    if not isinstance(data, bytes):
        raise AssertionError("Expected request.data to be bytes.")
    return data.decode("utf-8")


def test_folder_list_path_includes_session_id() -> None:
    client = OpenDriveClient(api_key="key", api_secret="secret", base_url="https://example.com/api")
    client._session_id = "session-123"

    path = client._folder_list_path("folder-456")

    assert path == "/folder/list.json/session-123/folder-456"


def test_build_request_does_not_send_session_header() -> None:
    client = OpenDriveClient(api_key="key", api_secret="secret", base_url="https://example.com/api")
    client._session_id = "session-123"

    request = client._build_request("GET", "/folder/list.json/session-123/folder-456")

    assert request.full_url == "https://example.com/api/folder/list.json/session-123/folder-456"
    assert request.headers == {"Accept": "application/json"}


def test_build_request_encodes_json_body_for_post_calls() -> None:
    client = OpenDriveClient(api_key="key", api_secret="secret", base_url="https://example.com/api")

    request = client._build_request(
        "POST",
        "/file/trash.json",
        body={"session_id": "session-123", "file_id": "file-456"},
    )

    assert request.full_url == "https://example.com/api/file/trash.json"
    assert request.headers == {
        "Accept": "application/json",
        "Content-type": "application/json",
    }
    assert json.loads(_request_data_as_text(request.data)) == {
        "session_id": "session-123",
        "file_id": "file-456",
    }


def test_download_request_uses_session_id_as_query_parameter() -> None:
    client = OpenDriveClient(api_key="key", api_secret="secret", base_url="https://example.com/api")
    client._session_id = "session-123"

    request = client._build_request(
        "GET",
        "/download/file.json/file-456",
        query={"session_id": client._get_session_id(), "inline": "0"},
    )

    assert (
        request.full_url
        == "https://example.com/api/download/file.json/file-456?session_id=session-123&inline=0"
    )


def test_get_session_id_uses_login_post_request(monkeypatch: Any) -> None:
    client = OpenDriveClient(
        api_key="api-user", api_secret="api-pass", base_url="https://example.com/api"
    )
    captured: dict[str, Any] = {}

    class FakeResponse:
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
            return None

        def read(self) -> bytes:
            return b'{"SessionID": "session-123"}'

    def fake_urlopen(request: Any) -> FakeResponse:
        captured["method"] = request.get_method()
        captured["url"] = request.full_url
        captured["headers"] = dict(request.headers)
        captured["body"] = json.loads(_request_data_as_text(request.data))
        return FakeResponse()

    monkeypatch.setattr("file_migration.client.open_drive_client.urlopen", fake_urlopen)

    session_id = client._get_session_id()

    assert session_id == "session-123"
    assert captured["method"] == "POST"
    assert captured["url"] == "https://example.com/api/session/login.json"
    assert captured["headers"] == {
        "Accept": "application/json",
        "Content-type": "application/json",
    }
    assert captured["body"] == {"username": "api-user", "passwd": "api-pass"}
