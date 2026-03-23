from __future__ import annotations

import logging
from pathlib import Path
from typing import Protocol

from file_migration.client.open_drive_client import OpenDriveClient, OpenDriveFile
from file_migration.context.migration_item import MigrationItem
from file_migration.downloader.downloader import Downloader

LOGGER = logging.getLogger(__name__)


class OpenDriveDownloadClient(Protocol):
    def list_files(self, folder_id: str) -> list[OpenDriveFile]: ...

    def download_file(self, file_id: str, destination_path: Path) -> Path: ...


class OpenDriveDownloader(Downloader):
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        *,
        client: OpenDriveDownloadClient | None = None,
    ) -> None:
        self._client = client or OpenDriveClient(api_key=api_key, api_secret=api_secret)

    def list_items(self, source_path: str) -> list[MigrationItem]:
        LOGGER.info("opendrive downloader listing remote folder=%s", source_path)
        return [
            MigrationItem(
                item_id=file.file_id,
                name=file.name,
                source_path=file.path,
                mime_type=file.mime_type,
                size_bytes=file.size_bytes,
            )
            for file in self._client.list_files(source_path)
        ]

    def download(self, item: MigrationItem, workspace: Path) -> Path:
        relative_source_path = (
            Path(item.source_path.lstrip("/")) if item.source_path else Path(item.name)
        )
        destination_path = workspace / relative_source_path
        LOGGER.info(
            "opendrive downloader downloading item_id=%s destination=%s",
            item.item_id,
            destination_path,
        )
        return self._client.download_file(item.item_id, destination_path)
