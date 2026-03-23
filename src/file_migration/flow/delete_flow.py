from __future__ import annotations

import logging
from typing import Protocol
from uuid import uuid4

from file_migration.config.job_config import JobConfig
from file_migration.context.migration_stage import MigrationStage
from file_migration.data_accessors.migration_state_accessor import MigrationStateAccessor


class OpenDriveDeleteClient(Protocol):
    def delete_file(self, file_id: str) -> None: ...


LOGGER = logging.getLogger(__name__)


class DeleteFlow:
    def __init__(
        self,
        config: JobConfig,
        open_drive_client: OpenDriveDeleteClient,
        state_accessor: MigrationStateAccessor,
    ) -> None:
        self._config = config
        self._open_drive_client = open_drive_client
        self._state_accessor = state_accessor

    def run(self) -> None:
        flow_id = uuid4().hex[:8]
        flow_logger = logging.LoggerAdapter(
            LOGGER,
            {"flow_id": flow_id, "job_name": self._config.job_name, "flow_name": "delete"},
        )
        exported_records = self._state_accessor.list_exported(self._config.job_name)
        total_records = len(exported_records)
        flow_logger.info("found %d exported records to delete", total_records)
        for index, record in enumerate(exported_records, start=1):
            flow_logger.info(
                "deleting item %d/%d item_id=%s",
                index,
                total_records,
                record.source_item_id,
            )
            record.stage = MigrationStage.DELETING
            self._state_accessor.save(record)
            self._open_drive_client.delete_file(record.source_item_id)
            record.stage = MigrationStage.DELETED
            self._state_accessor.save(record)
            flow_logger.info("deleted source item_id=%s", record.source_item_id)
        flow_logger.info("delete flow completed total_items=%d", total_records)
