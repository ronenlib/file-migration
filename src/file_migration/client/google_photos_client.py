from __future__ import annotations

import json
import logging
import mimetypes
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from file_migration.client.google_oauth import GoogleOAuthTokenProvider

LOGGER = logging.getLogger(__name__)


class GooglePhotosClient:
    def __init__(
        self,
        *,
        token_provider: GoogleOAuthTokenProvider,
        base_url: str = "https://photoslibrary.googleapis.com/v1",
    ) -> None:
        self._token_provider = token_provider
        self._base_url = base_url.rstrip("/")

    def ensure_album(self, album_name: str) -> str:
        LOGGER.info("google photos client ensuring album title=%s", album_name)
        page_token: str | None = None
        while True:
            query = {"pageSize": "50"}
            if page_token is not None:
                query["pageToken"] = page_token
            payload = self._request_json("GET", "/albums", query=query)
            albums = payload.get("albums")
            if isinstance(albums, list):
                for album in albums:
                    if not isinstance(album, dict):
                        continue
                    title = album.get("title")
                    album_id = album.get("id")
                    if title == album_name and isinstance(album_id, str) and album_id != "":
                        LOGGER.info(
                            "google photos client reused album album_id=%s title=%s",
                            album_id,
                            album_name,
                        )
                        return album_id
            next_page_token = payload.get("nextPageToken")
            if not isinstance(next_page_token, str) or next_page_token == "":
                break
            page_token = next_page_token

        payload = self._request_json(
            "POST",
            "/albums",
            body=json.dumps({"album": {"title": album_name}}).encode("utf-8"),
            extra_headers={"Content-Type": "application/json; charset=UTF-8"},
        )
        album_id = payload.get("id")
        if not isinstance(album_id, str) or album_id == "":
            raise ValueError("Google Photos album create response did not include id.")
        LOGGER.info("google photos client created album album_id=%s title=%s", album_id, album_name)
        return album_id

    def upload_media_item(self, file_path: Path, *, album_id: str) -> str:
        LOGGER.info("google photos client uploading media file=%s album_id=%s", file_path, album_id)
        mime_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        upload_token = self._upload_bytes(file_path, mime_type)
        payload = self._request_json(
            "POST",
            "/mediaItems:batchCreate",
            body=json.dumps(
                {
                    "albumId": album_id,
                    "newMediaItems": [
                        {
                            "description": file_path.name,
                            "simpleMediaItem": {
                                "uploadToken": upload_token,
                                "fileName": file_path.name,
                            },
                        }
                    ],
                }
            ).encode("utf-8"),
            extra_headers={"Content-Type": "application/json; charset=UTF-8"},
        )
        results = payload.get("newMediaItemResults")
        if not isinstance(results, list) or len(results) == 0:
            raise ValueError("Google Photos batchCreate response did not include created items.")
        first = results[0]
        if not isinstance(first, dict):
            raise ValueError("Google Photos batchCreate response had invalid item payload.")
        media_item = first.get("mediaItem")
        if not isinstance(media_item, dict):
            raise ValueError("Google Photos batchCreate response did not include mediaItem.")
        media_item_id = media_item.get("id")
        if not isinstance(media_item_id, str) or media_item_id == "":
            raise ValueError("Google Photos batchCreate response did not include mediaItem id.")
        LOGGER.info("google photos client uploaded media_item_id=%s", media_item_id)
        return media_item_id

    def _upload_bytes(self, file_path: Path, mime_type: str) -> str:
        headers = {
            "Authorization": f"Bearer {self._token_provider.get_access_token()}",
            "Content-Type": "application/octet-stream",
            "X-Goog-Upload-Content-Type": mime_type,
            "X-Goog-Upload-Protocol": "raw",
        }
        request = Request(
            f"{self._base_url}/uploads",
            method="POST",
            data=file_path.read_bytes(),
            headers=headers,
        )
        with urlopen(request) as response:
            upload_token = response.read().decode("utf-8").strip()
        if upload_token == "":
            raise ValueError("Google Photos upload did not return an upload token.")
        return upload_token

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, str] | None = None,
        body: bytes | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
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
            raise ValueError("Google Photos response must be a JSON object.")
        return payload
