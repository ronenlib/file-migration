from __future__ import annotations

import logging
from pathlib import Path
from typing import Protocol

from file_migration.client.google_drive_client import GoogleDriveClient
from file_migration.client.google_oauth import GoogleOAuthTokenProvider
from file_migration.context.migration_item import MigrationItem
from file_migration.uploader.uploader import Uploader

LOGGER = logging.getLogger(__name__)


class GoogleDriveUploadClient(Protocol):
    def upload_file(self, file_path: Path, *, remote_name: str, parent_path: str) -> str: ...


class GoogleDriveUploader(Uploader):
    def __init__(
        self,
        drive_path: str,
        *,
        token_provider: GoogleOAuthTokenProvider | None = None,
        client: GoogleDriveUploadClient | None = None,
    ) -> None:
        self._drive_path = drive_path
        if client is not None:
            self._client = client
        elif token_provider is not None:
            self._client = GoogleDriveClient(token_provider=token_provider)
        else:
            raise ValueError("token_provider is required when client is not provided.")

    def upload(self, file_path: Path, item: MigrationItem) -> str:
        LOGGER.info("google drive uploader uploading item_id=%s name=%s", item.item_id, item.name)
        return self._client.upload_file(
            file_path,
            remote_name=item.name,
            parent_path=self._drive_path,
        )
