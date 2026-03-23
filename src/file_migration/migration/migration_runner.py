from __future__ import annotations

from abc import ABC, abstractmethod


class MigrationRunner(ABC):
    @abstractmethod
    def run(self) -> None:
        """Run migration workflow."""
