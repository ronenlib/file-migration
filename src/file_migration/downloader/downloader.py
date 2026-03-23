from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from file_migration.context.migration_item import MigrationItem


class Downloader(ABC):
    @abstractmethod
    def list_items(self, source_path: str) -> list[MigrationItem]:
        """List source items."""

    @abstractmethod
    def download(self, item: MigrationItem, workspace: Path) -> Path:
        """Download source item to local workspace."""
