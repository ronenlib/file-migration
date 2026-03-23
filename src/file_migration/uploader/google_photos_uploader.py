from __future__ import annotations

import logging
from pathlib import Path
from typing import Protocol

from file_migration.client.google_oauth import GoogleOAuthTokenProvider
from file_migration.client.google_photos_client import GooglePhotosClient
from file_migration.context.migration_item import MigrationItem
from file_migration.uploader.uploader import Uploader

LOGGER = logging.getLogger(__name__)


class GooglePhotosUploadClient(Protocol):
    def ensure_album(self, album_name: str) -> str: ...

    def upload_media_item(self, file_path: Path, *, album_id: str) -> str: ...


class GooglePhotosUploader(Uploader):
    def __init__(
        self,
        album_name: str,
        *,
        token_provider: GoogleOAuthTokenProvider | None = None,
        client: GooglePhotosUploadClient | None = None,
    ) -> None:
        self._album_name = album_name
        if client is not None:
            self._client = client
        elif token_provider is not None:
            self._client = GooglePhotosClient(token_provider=token_provider)
        else:
            raise ValueError("token_provider is required when client is not provided.")
        self._album_id: str | None = None

    def upload(self, file_path: Path, item: MigrationItem) -> str:
        LOGGER.info("google photos uploader uploading item_id=%s name=%s", item.item_id, item.name)
        if self._album_id is None:
            self._album_id = self._client.ensure_album(self._album_name)
        return self._client.upload_media_item(file_path, album_id=self._album_id)
