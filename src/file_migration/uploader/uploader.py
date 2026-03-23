from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from file_migration.context.migration_item import MigrationItem


class Uploader(ABC):
    @abstractmethod
    def upload(self, file_path: Path, item: MigrationItem) -> str:
        """Upload local file and return provider item id."""
