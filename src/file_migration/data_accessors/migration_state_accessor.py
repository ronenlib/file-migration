from __future__ import annotations

import logging

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from file_migration.context.migration_item import MigrationItem
from file_migration.context.migration_stage import MigrationStage
from file_migration.data_accessors.models.migration_state_record import MigrationStateRecord

LOGGER = logging.getLogger(__name__)


class MigrationStateAccessor:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_or_create(
        self, job_name: str, item: MigrationItem, target_provider: str
    ) -> MigrationStateRecord:
        stmt: Select[tuple[MigrationStateRecord]] = select(MigrationStateRecord).where(
            MigrationStateRecord.job_name == job_name,
            MigrationStateRecord.source_item_id == item.item_id,
        )
        record = self._session.execute(stmt).scalar_one_or_none()
        if record is not None:
            LOGGER.info(
                "db reused migration state job=%s item_id=%s stage=%s",
                job_name,
                item.item_id,
                record.stage,
            )
            return record

        new_record = MigrationStateRecord(
            job_name=job_name,
            source_item_id=item.item_id,
            source_name=item.name,
            source_path=item.source_path,
            stage=MigrationStage.PENDING,
            target_provider=target_provider,
        )
        self._session.add(new_record)
        self._session.commit()
        LOGGER.info(
            "db created migration state job=%s item_id=%s provider=%s stage=%s",
            job_name,
            item.item_id,
            target_provider,
            new_record.stage,
        )
        return new_record

    def save(self, record: MigrationStateRecord) -> None:
        self._session.add(record)
        self._session.commit()
        LOGGER.info(
            "db updated migration state job=%s item_id=%s stage=%s target_id=%s local_path=%s",
            record.job_name,
            record.source_item_id,
            record.stage,
            record.target_id,
            record.local_path,
        )

    def list_exported(self, job_name: str) -> list[MigrationStateRecord]:
        stmt: Select[tuple[MigrationStateRecord]] = select(MigrationStateRecord).where(
            MigrationStateRecord.job_name == job_name,
            MigrationStateRecord.stage == MigrationStage.EXPORTED,
        )
        records = list(self._session.execute(stmt).scalars().all())
        LOGGER.info("db loaded %d exported records for job=%s", len(records), job_name)
        return records
