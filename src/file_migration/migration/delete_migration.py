from __future__ import annotations

from file_migration.flow.delete_flow import DeleteFlow
from file_migration.migration.migration_runner import MigrationRunner


class DeleteMigration(MigrationRunner):
    def __init__(self, flow: DeleteFlow) -> None:
        self._flow = flow

    def run(self) -> None:
        self._flow.run()
