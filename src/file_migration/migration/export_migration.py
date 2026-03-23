from __future__ import annotations

from file_migration.flow.export_flow import ExportFlow
from file_migration.migration.migration_runner import MigrationRunner


class ExportMigration(MigrationRunner):
    def __init__(self, flow: ExportFlow) -> None:
        self._flow = flow

    def run(self) -> None:
        self._flow.run()
