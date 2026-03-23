from __future__ import annotations

import logging
from pathlib import Path
from uuid import uuid4

from file_migration.config.job_config import JobConfig
from file_migration.context.migration_item import MigrationItem
from file_migration.context.migration_stage import MigrationStage
from file_migration.data_accessors.migration_state_accessor import MigrationStateAccessor
from file_migration.data_accessors.source_accessor import SourceAccessor
from file_migration.data_accessors.target_accessor import TargetAccessor

LOGGER = logging.getLogger(__name__)


class ExportFlow:
    def __init__(
        self,
        config: JobConfig,
        source_accessor: SourceAccessor,
        target_accessor: TargetAccessor,
        state_accessor: MigrationStateAccessor,
    ) -> None:
        self._config = config
        self._source_accessor = source_accessor
        self._target_accessor = target_accessor
        self._state_accessor = state_accessor

    def run(self) -> None:
        flow_id = uuid4().hex[:8]
        flow_logger = logging.LoggerAdapter(
            LOGGER,
            {"flow_id": flow_id, "job_name": self._config.job_name, "flow_name": "export"},
        )
        workspace = Path(self._config.workspace_dir).expanduser()
        workspace.mkdir(parents=True, exist_ok=True)
        flow_logger.info("workspace ready at %s", workspace)

        items = self._source_accessor.list_items(self._config.downloader.source_folder_id)
        total_items = len(items)
        flow_logger.info("discovered %d source items", total_items)
        for index, item in enumerate(items, start=1):
            flow_logger.info(
                "processing item %d/%d item_id=%s name=%s",
                index,
                total_items,
                item.item_id,
                item.name,
            )
            self._run_item(item=item, workspace=workspace, flow_logger=flow_logger)
        flow_logger.info("export flow completed total_items=%d", total_items)

    def _run_item(
        self,
        item: MigrationItem,
        workspace: Path,
        flow_logger: logging.LoggerAdapter,
    ) -> None:
        record = self._state_accessor.get_or_create(
            job_name=self._config.job_name,
            item=item,
            target_provider=self._config.uploader.provider,
        )
        if record.stage in {MigrationStage.EXPORTED, MigrationStage.DELETED}:
            flow_logger.info(
                "skipping item item_id=%s current_stage=%s",
                item.item_id,
                record.stage,
            )
            return

        try:
            flow_logger.info(
                "downloading item_id=%s source_path=%s", item.item_id, item.source_path
            )
            local_path = self._source_accessor.download_to_workspace(item=item, workspace=workspace)
            record.local_path = str(local_path)
            record.stage = MigrationStage.DOWNLOADED
            self._state_accessor.save(record)
            flow_logger.info("downloaded item_id=%s local_path=%s", item.item_id, local_path)

            for step_name in self._config.intermediate_steps:
                _ = step_name
                # Placeholder for future intermediate processors (e.g. ffmpeg).
                flow_logger.info("intermediate step placeholder step=%s", step_name)

            flow_logger.info(
                "uploading item_id=%s provider=%s",
                item.item_id,
                self._config.uploader.provider,
            )
            target_id = self._target_accessor.upload(local_path=local_path, item=item)
            record.target_id = target_id
            record.stage = MigrationStage.UPLOADED
            self._state_accessor.save(record)
            flow_logger.info("uploaded item_id=%s target_id=%s", item.item_id, target_id)

            if local_path.exists():
                local_path.unlink()
            record.local_path = None
            record.stage = MigrationStage.EXPORTED
            self._state_accessor.save(record)
            flow_logger.info("marked exported item_id=%s", item.item_id)
        except Exception as error:  # pragma: no cover
            record.stage = MigrationStage.FAILED
            record.error_message = str(error)
            self._state_accessor.save(record)
            flow_logger.exception("item failed item_id=%s error=%s", item.item_id, error)
