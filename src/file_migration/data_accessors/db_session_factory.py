from __future__ import annotations

import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from file_migration.data_accessors.models.base import Base

LOGGER = logging.getLogger(__name__)


class DbSessionFactory:
    def __init__(self, db_url: str) -> None:
        LOGGER.info("creating database engine")
        self._engine = create_engine(db_url, future=True)
        self._session_factory = sessionmaker(
            bind=self._engine, class_=Session, expire_on_commit=False
        )

    def initialize_schema(self) -> None:
        LOGGER.info("initializing database schema")
        Base.metadata.create_all(self._engine)

    def create_session(self) -> Session:
        LOGGER.info("creating database session")
        return self._session_factory()
