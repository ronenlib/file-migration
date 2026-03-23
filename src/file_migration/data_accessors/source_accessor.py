from __future__ import annotations

import logging
from pathlib import Path

from file_migration.context.migration_item import MigrationItem
from file_migration.downloader.downloader import Downloader

LOGGER = logging.getLogger(__name__)


class SourceAccessor:
    def __init__(self, downloader: Downloader) -> None:
        self._downloader = downloader

    def list_items(self, source_path: str) -> list[MigrationItem]:
        LOGGER.info("source listing items from source_path=%s", source_path)
        return self._downloader.list_items(source_path)

    def download_to_workspace(self, item: MigrationItem, workspace: Path) -> Path:
        LOGGER.info("source downloading item_id=%s to workspace=%s", item.item_id, workspace)
        return self._downloader.download(item, workspace)
