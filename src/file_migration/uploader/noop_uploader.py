from __future__ import annotations

import logging
from pathlib import Path

from file_migration.context.migration_item import MigrationItem
from file_migration.uploader.uploader import Uploader

LOGGER = logging.getLogger(__name__)


class NoopUploader(Uploader):
    def upload(self, file_path: Path, item: MigrationItem) -> str:
        LOGGER.info(
            "noop uploader skipping remote upload item_id=%s local_path=%s", item.item_id, file_path
        )
        return f"noop:{item.item_id}"
