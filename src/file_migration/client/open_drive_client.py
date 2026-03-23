from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class OpenDriveFile:
    file_id: str
    name: str
    path: str
    size_bytes: int
    mime_type: str


class OpenDriveClient:
    """Thin OpenDrive API client.

    The endpoint shapes are inferred from OpenDrive's public API surface:
    session login, folder listing, file download, and file trash/delete.
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        *,
        base_url: str = "https://dev.opendrive.com/api/v1",
    ) -> None:
        self._api_key = api_key
        self._api_secret = api_secret
        self._base_url = base_url.rstrip("/")
        self._session_id: str | None = None

    def list_files(self, folder_id: str) -> list[OpenDriveFile]:
        LOGGER.info("opendrive client listing files folder_id=%s", folder_id)
        files: list[OpenDriveFile] = []
        self._collect_files(folder_id=folder_id, files=files, visited_folder_ids=set())
        LOGGER.info("opendrive client listed %d files folder_id=%s", len(files), folder_id)
        return files

    def download_file(self, file_id: str, destination_path: Path) -> Path:
        LOGGER.info(
            "opendrive client downloading file_id=%s destination=%s", file_id, destination_path
        )
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        request = self._build_request(
            "GET",
            f"/download/file.json/{file_id}",
            query={"session_id": self._get_session_id(), "inline": "0"},
        )
        with urlopen(request) as response, destination_path.open("wb") as output_handle:
            while True:
                chunk = response.read(64 * 1024)
                if not chunk:
                    break
                output_handle.write(chunk)
        return destination_path

    def delete_file(self, file_id: str) -> None:
        LOGGER.info("opendrive client deleting file_id=%s", file_id)
        for method, path in (
            ("POST", "/file/trash.json"),
            ("DELETE", f"/file.json/{self._get_session_id()}/{file_id}"),
        ):
            try:
                body = (
                    {"session_id": self._get_session_id(), "file_id": file_id}
                    if method == "POST"
                    else None
                )
                self._request_json(method, path, body=body)
                return
            except HTTPError as error:
                if error.code not in {404, 405}:
                    raise
        raise ValueError(f"Unable to delete OpenDrive file: {file_id}")

    def _collect_files(
        self,
        *,
        folder_id: str,
        files: list[OpenDriveFile],
        visited_folder_ids: set[str],
    ) -> None:
        if folder_id in visited_folder_ids:
            return
        visited_folder_ids.add(folder_id)

        payload = self._request_json("GET", self._folder_list_path(folder_id))
        files.extend(self._parse_folder_listing(payload))

        for child_folder_id in self._parse_child_folder_ids(payload):
            self._collect_files(
                folder_id=child_folder_id,
                files=files,
                visited_folder_ids=visited_folder_ids,
            )

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        query: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        request = self._build_request(method, path, query=query, body=body)
        with urlopen(request) as response:
            payload = response.read()

        decoded = json.loads(payload.decode("utf-8"))
        if not isinstance(decoded, dict):
            raise ValueError("OpenDrive API response must be a JSON object.")
        return decoded

    def _folder_list_path(self, folder_id: str) -> str:
        session_id = self._get_session_id()
        return f"/folder/list.json/{session_id}/{folder_id}"

    def _build_request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        query: dict[str, str] | None = None,
    ) -> Request:
        url = f"{self._base_url}{path}"
        if query:
            url = f"{url}?{urlencode(query)}"

        headers = {"Accept": "application/json"}
        data: bytes | None = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode("utf-8")
        return Request(url, method=method, headers=headers, data=data)

    def _get_session_id(self) -> str:
        if self._session_id is not None:
            return self._session_id

        request = self._build_request(
            "POST",
            "/session/login.json",
            body={"username": self._api_key, "passwd": self._api_secret},
        )
        LOGGER.info("opendrive client creating session")
        with urlopen(request) as response:
            payload = response.read()

        decoded = json.loads(payload.decode("utf-8"))
        if not isinstance(decoded, dict):
            raise ValueError("OpenDrive login response must be a JSON object.")

        session_id = self._read_string(decoded, ("SessionID", "session_id"))
        self._session_id = session_id
        LOGGER.info("opendrive client session established")
        return session_id

    def _parse_folder_listing(self, payload: dict[str, Any]) -> list[OpenDriveFile]:
        raw_files = self._read_list(payload, ("Files", "files", "items"))
        files: list[OpenDriveFile] = []
        for raw_file in raw_files:
            if not isinstance(raw_file, dict):
                continue

            file_id = self._read_string(raw_file, ("FileId", "FileID", "file_id", "id"))
            name = self._read_string(raw_file, ("Name", "name"))
            full_path = self._read_optional_string(raw_file, ("FilePath", "Path", "path")) or name
            size_value = self._read_optional_string(raw_file, ("Size", "size"))
            mime_type = (
                self._read_optional_string(raw_file, ("MimeType", "mime_type", "type"))
                or "application/octet-stream"
            )
            files.append(
                OpenDriveFile(
                    file_id=file_id,
                    name=name,
                    path=full_path,
                    size_bytes=int(size_value or "0"),
                    mime_type=mime_type,
                )
            )
        return files

    def _parse_child_folder_ids(self, payload: dict[str, Any]) -> list[str]:
        raw_folders = self._read_list(payload, ("Folders", "folders"))
        folder_ids: list[str] = []
        for raw_folder in raw_folders:
            if not isinstance(raw_folder, dict):
                continue
            folder_id = self._read_optional_string(
                raw_folder,
                ("FolderID", "FolderId", "folder_id", "id"),
            )
            if folder_id is not None:
                folder_ids.append(folder_id)
        return folder_ids

    def _read_list(self, payload: dict[str, Any], keys: tuple[str, ...]) -> list[Any]:
        for key in keys:
            value = payload.get(key)
            if isinstance(value, list):
                return value
        return []

    def _read_string(self, payload: dict[str, Any], keys: tuple[str, ...]) -> str:
        value = self._read_optional_string(payload, keys)
        if value is None:
            raise ValueError(f"Missing expected OpenDrive field: {keys[0]}")
        return value

    def _read_optional_string(self, payload: dict[str, Any], keys: tuple[str, ...]) -> str | None:
        for key in keys:
            value = payload.get(key)
            if isinstance(value, str) and value != "":
                return value
            if isinstance(value, int):
                return str(value)
        return None
