from __future__ import annotations

import logging
from pathlib import Path

from file_migration.context.migration_item import MigrationItem
from file_migration.uploader.uploader import Uploader

LOGGER = logging.getLogger(__name__)


class TargetAccessor:
    def __init__(self, uploader: Uploader) -> None:
        self._uploader = uploader

    def upload(self, local_path: Path, item: MigrationItem) -> str:
        LOGGER.info("target uploading item_id=%s local_path=%s", item.item_id, local_path)
        return self._uploader.upload(local_path, item)
