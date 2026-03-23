from __future__ import annotations

from typing import Any

from file_migration.client.google_oauth import GoogleOAuthTokenProvider


def _request_body_text(data: object) -> str:
    if not isinstance(data, bytes):
        raise AssertionError("Expected request.data to be bytes.")
    return data.decode("utf-8")


def test_google_oauth_provider_exchanges_authorization_code_and_then_refreshes(
    monkeypatch: Any,
) -> None:
    requests: list[dict[str, Any]] = []
    responses = iter(
        [
            b'{"access_token":"first-access","refresh_token":"refresh-123","expires_in":1}',
            b'{"access_token":"second-access","expires_in":3600}',
        ]
    )
    prompted_urls: list[str] = []
    current_time = {"value": 1000.0}

    class FakeResponse:
        def __init__(self, payload: bytes) -> None:
            self._payload = payload

        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
            return None

        def read(self) -> bytes:
            return self._payload

    def fake_urlopen(request: Any) -> FakeResponse:
        requests.append(
            {
                "url": request.full_url,
                "method": request.get_method(),
                "body": _request_body_text(request.data),
            }
        )
        return FakeResponse(next(responses))

    def fake_prompt(url: str) -> str:
        prompted_urls.append(url)
        return "auth-code-123"

    monkeypatch.setattr("file_migration.client.google_oauth.urlopen", fake_urlopen)
    monkeypatch.setattr(
        "file_migration.client.google_oauth.time.time", lambda: current_time["value"]
    )

    provider = GoogleOAuthTokenProvider(
        client_id="client-id",
        client_secret="client-secret",
        scopes=["scope-a", "scope-b"],
        redirect_uri="https://example.com/oauth/callback",
        prompt_for_auth_code=fake_prompt,
    )

    first_token = provider.get_access_token()
    current_time["value"] = 1002.0
    second_token = provider.get_access_token()

    assert first_token == "first-access"
    assert second_token == "second-access"
    assert len(prompted_urls) == 1
    assert "client_id=client-id" in prompted_urls[0]
    assert "scope=scope-a+scope-b" in prompted_urls[0]
    assert "access_type=offline" in prompted_urls[0]
    assert requests == [
        {
            "url": "https://oauth2.googleapis.com/token",
            "method": "POST",
            "body": "client_id=client-id&client_secret=client-secret&code=auth-code-123&grant_type=authorization_code&redirect_uri=https%3A%2F%2Fexample.com%2Foauth%2Fcallback",
        },
        {
            "url": "https://oauth2.googleapis.com/token",
            "method": "POST",
            "body": "client_id=client-id&client_secret=client-secret&refresh_token=refresh-123&grant_type=refresh_token",
        },
    ]


def test_google_oauth_provider_uses_local_callback_when_available(monkeypatch: Any) -> None:
    requests: list[dict[str, Any]] = []

    class FakeResponse:
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
            return None

        def read(self) -> bytes:
            return b'{"access_token":"first-access","refresh_token":"refresh-123","expires_in":3600}'

    def fake_urlopen(request: Any) -> FakeResponse:
        requests.append(
            {
                "url": request.full_url,
                "method": request.get_method(),
                "body": _request_body_text(request.data),
            }
        )
        return FakeResponse()

    monkeypatch.setattr("file_migration.client.google_oauth.urlopen", fake_urlopen)
    monkeypatch.setattr(
        GoogleOAuthTokenProvider,
        "_wait_for_local_authorization_code",
        lambda self: ("http://127.0.0.1:43123/oauth/callback", "callback-code-123"),
    )

    provider = GoogleOAuthTokenProvider(
        client_id="client-id",
        client_secret="client-secret",
        scopes=["scope-a"],
    )

    access_token = provider.get_access_token()

    assert access_token == "first-access"
    assert requests == [
        {
            "url": "https://oauth2.googleapis.com/token",
            "method": "POST",
            "body": "client_id=client-id&client_secret=client-secret&code=callback-code-123&grant_type=authorization_code&redirect_uri=http%3A%2F%2F127.0.0.1%3A43123%2Foauth%2Fcallback",
        }
    ]
