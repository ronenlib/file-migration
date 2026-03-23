from __future__ import annotations

import json
import logging
import socket
import time
from collections.abc import Callable, Sequence
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Event
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

LOGGER = logging.getLogger(__name__)


class GoogleOAuthTokenProvider:
    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        scopes: Sequence[str],
        token_uri: str = "https://oauth2.googleapis.com/token",
        auth_uri: str = "https://accounts.google.com/o/oauth2/v2/auth",
        redirect_uri: str = "http://localhost",
        callback_timeout_seconds: float = 300.0,
        prompt_for_auth_code: Callable[[str], str] | None = None,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._scopes = tuple(scopes)
        self._token_uri = token_uri
        self._auth_uri = auth_uri
        self._redirect_uri = redirect_uri
        self._callback_timeout_seconds = callback_timeout_seconds
        self._prompt_for_auth_code = prompt_for_auth_code or self._default_prompt_for_auth_code
        self._refresh_token: str | None = None
        self._access_token: str | None = None
        self._expires_at: float = 0.0

    def get_access_token(self) -> str:
        if self._access_token is not None and time.time() < self._expires_at - 60:
            return self._access_token

        if self._refresh_token is None:
            self._exchange_authorization_code()
        else:
            self._refresh_access_token()

        if self._access_token is None:
            raise ValueError("Google OAuth access token was not established.")
        return self._access_token

    def build_authorization_url(self, *, redirect_uri: str | None = None) -> str:
        return (
            f"{self._auth_uri}?"
            f"{urlencode({'client_id': self._client_id, 'redirect_uri': redirect_uri or self._redirect_uri, 'response_type': 'code', 'scope': ' '.join(self._scopes), 'access_type': 'offline', 'prompt': 'consent'})}"
        )

    def _exchange_authorization_code(self) -> None:
        authorization_code, redirect_uri = self._obtain_authorization_code()
        if authorization_code == "":
            raise ValueError("Google authorization code must be a non-empty string.")

        LOGGER.info("exchanging google oauth authorization code for refresh token")
        payload = self._token_request(
            {
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "code": authorization_code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            }
        )
        self._store_token_payload(payload, require_refresh_token=True)

    def _obtain_authorization_code(self) -> tuple[str, str]:
        callback_result = self._maybe_wait_for_local_callback()
        if callback_result is not None:
            redirect_uri, authorization_code = callback_result
            return authorization_code.strip(), redirect_uri

        authorization_url = self.build_authorization_url()
        return self._prompt_for_auth_code(authorization_url).strip(), self._redirect_uri

    def _maybe_wait_for_local_callback(self) -> tuple[str, str] | None:
        parsed = urlparse(self._redirect_uri)
        if parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1"}:
            return None

        try:
            return self._wait_for_local_authorization_code()
        except OSError:
            LOGGER.info("google oauth local callback listener unavailable, falling back to manual paste")
            return None

    def _wait_for_local_authorization_code(self) -> tuple[str, str]:
        auth_code: dict[str, str] = {}
        ready = Event()
        request_path = "/oauth/callback"

        class CallbackHandler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # type: ignore[override]
                parsed_request = urlparse(self.path)
                params = parse_qs(parsed_request.query)
                code = params.get("code", [""])[0]
                if code == "":
                    self.send_response(400)
                    self.send_header("Content-Type", "text/plain; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(b"Missing OAuth code.")
                    return

                auth_code["value"] = code
                ready.set()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(
                    b"<html><body><h1>Authorization received.</h1><p>You can return to the CLI.</p></body></html>"
                )

            def log_message(self, format: str, *args: object) -> None:  # noqa: A003
                _ = (format, args)

        with HTTPServer(("127.0.0.1", 0), CallbackHandler) as server:
            server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            redirect_uri = f"http://127.0.0.1:{server.server_port}{request_path}"
            authorization_url = self.build_authorization_url(redirect_uri=redirect_uri)
            print("Open this URL in your browser and approve access:")
            print(authorization_url)
            server.timeout = self._callback_timeout_seconds
            server.handle_request()

        code = auth_code.get("value")
        if code is None or code == "":
            raise OSError("Timed out waiting for OAuth callback.")
        return redirect_uri, code

    def _refresh_access_token(self) -> None:
        LOGGER.info("refreshing google oauth access token")
        payload = self._token_request(
            {
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "refresh_token": self._refresh_token,
                "grant_type": "refresh_token",
            }
        )
        self._store_token_payload(payload, require_refresh_token=False)

    def _token_request(self, form_data: dict[str, str | None]) -> dict[str, object]:
        encoded_payload = urlencode(
            {
                key: value
                for key, value in form_data.items()
                if isinstance(value, str) and value != ""
            }
        ).encode("utf-8")
        request = Request(
            self._token_uri,
            method="POST",
            data=encoded_payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        with urlopen(request) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("OAuth token response must be a JSON object.")
        return payload

    def _store_token_payload(
        self, payload: dict[str, object], *, require_refresh_token: bool
    ) -> None:
        access_token = payload.get("access_token")
        expires_in = payload.get("expires_in")
        refresh_token = payload.get("refresh_token")
        if not isinstance(access_token, str) or access_token == "":
            raise ValueError("OAuth token response did not include an access_token.")
        if not isinstance(expires_in, int):
            raise ValueError("OAuth token response did not include expires_in.")
        if require_refresh_token and (not isinstance(refresh_token, str) or refresh_token == ""):
            raise ValueError("OAuth token response did not include a refresh_token.")

        self._access_token = access_token
        self._expires_at = time.time() + expires_in
        if isinstance(refresh_token, str) and refresh_token != "":
            self._refresh_token = refresh_token
        LOGGER.info("google oauth access token ready expires_in=%s", expires_in)

    def _default_prompt_for_auth_code(self, authorization_url: str) -> str:
        print("Open this URL in your browser, approve access, then paste the returned code:")
        print(authorization_url)
        return input("Google authorization code: ")
