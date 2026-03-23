from __future__ import annotations

import json
import logging
import mimetypes
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from file_migration.client.google_oauth import GoogleOAuthTokenProvider

LOGGER = logging.getLogger(__name__)


class GoogleDriveClient:
    def __init__(
        self,
        *,
        token_provider: GoogleOAuthTokenProvider,
        base_url: str = "https://www.googleapis.com/drive/v3",
        upload_base_url: str = "https://www.googleapis.com/upload/drive/v3",
    ) -> None:
        self._token_provider = token_provider
        self._base_url = base_url.rstrip("/")
        self._upload_base_url = upload_base_url.rstrip("/")

    def upload_file(self, file_path: Path, *, remote_name: str, parent_path: str) -> str:
        LOGGER.info(
            "google drive client uploading file=%s remote_name=%s parent_path=%s",
            file_path,
            remote_name,
            parent_path,
        )
        parent_id = self.ensure_folder_path(parent_path)
        boundary = f"file-migration-{uuid.uuid4().hex}"
        metadata = json.dumps(
            {
                "name": remote_name,
                "parents": [parent_id],
            }
        ).encode("utf-8")
        mime_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        file_bytes = file_path.read_bytes()
        body = (
            b"--"
            + boundary.encode("ascii")
            + b"\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n"
            + metadata
            + b"\r\n--"
            + boundary.encode("ascii")
            + b"\r\nContent-Type: "
            + mime_type.encode("utf-8")
            + b"\r\n\r\n"
            + file_bytes
            + b"\r\n--"
            + boundary.encode("ascii")
            + b"--\r\n"
        )
        payload = self._request_json(
            "POST",
            "/files",
            base_url=self._upload_base_url,
            query={"uploadType": "multipart", "supportsAllDrives": "true", "fields": "id"},
            body=body,
            extra_headers={"Content-Type": f"multipart/related; boundary={boundary}"},
        )
        file_id = payload.get("id")
        if not isinstance(file_id, str) or file_id == "":
            raise ValueError("Google Drive create response did not include file id.")
        LOGGER.info("google drive client uploaded file_id=%s remote_name=%s", file_id, remote_name)
        return file_id

    def ensure_folder_path(self, folder_path: str) -> str:
        LOGGER.info("google drive client ensuring folder path=%s", folder_path)
        normalized_parts = [part for part in folder_path.split("/") if part]
        parent_id = "root"
        for part in normalized_parts:
            existing_id = self._find_folder_id(name=part, parent_id=parent_id)
            if existing_id is None:
                parent_id = self._create_folder(name=part, parent_id=parent_id)
            else:
                parent_id = existing_id
        return parent_id

    def _find_folder_id(self, *, name: str, parent_id: str) -> str | None:
        query = (
            f"name = '{self._escape_query_value(name)}' and "
            "mimeType = 'application/vnd.google-apps.folder' and "
            f"'{self._escape_query_value(parent_id)}' in parents and trashed = false"
        )
        payload = self._request_json(
            "GET",
            "/files",
            query={
                "q": query,
                "fields": "files(id,name)",
                "pageSize": "1",
                "supportsAllDrives": "true",
                "includeItemsFromAllDrives": "true",
            },
        )
        files = payload.get("files")
        if not isinstance(files, list) or len(files) == 0:
            return None
        first = files[0]
        if not isinstance(first, dict):
            return None
        folder_id = first.get("id")
        return folder_id if isinstance(folder_id, str) and folder_id != "" else None

    def _create_folder(self, *, name: str, parent_id: str) -> str:
        LOGGER.info("google drive client creating folder name=%s parent_id=%s", name, parent_id)
        payload = self._request_json(
            "POST",
            "/files",
            query={"fields": "id", "supportsAllDrives": "true"},
            body=json.dumps(
                {
                    "name": name,
                    "mimeType": "application/vnd.google-apps.folder",
                    "parents": [parent_id],
                }
            ).encode("utf-8"),
            extra_headers={"Content-Type": "application/json; charset=UTF-8"},
        )
        folder_id = payload.get("id")
        if not isinstance(folder_id, str) or folder_id == "":
            raise ValueError("Google Drive folder create response did not include id.")
        LOGGER.info("google drive client created folder folder_id=%s name=%s", folder_id, name)
        return folder_id

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, str] | None = None,
        body: bytes | None = None,
        extra_headers: dict[str, str] | None = None,
        base_url: str | None = None,
    ) -> dict[str, Any]:
        url = f"{(base_url or self._base_url).rstrip('/')}{path}"
        if query:
            url = f"{url}?{urlencode(query)}"
        headers = {
            "Authorization": f"Bearer {self._token_provider.get_access_token()}",
            "Accept": "application/json",
        }
        if extra_headers:
            headers.update(extra_headers)
        request = Request(url, method=method, data=body, headers=headers)
        with urlopen(request) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Google Drive response must be a JSON object.")
        return payload

    def _escape_query_value(self, value: str) -> str:
        return value.replace("\\", "\\\\").replace("'", "\\'")
