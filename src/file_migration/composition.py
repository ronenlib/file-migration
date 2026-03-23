from __future__ import annotations

from sqlalchemy.orm import Session

from file_migration.client.google_oauth import GoogleOAuthTokenProvider
from file_migration.client.open_drive_client import OpenDriveClient
from file_migration.config.job_config import JobConfig
from file_migration.data_accessors.db_session_factory import DbSessionFactory
from file_migration.data_accessors.migration_state_accessor import MigrationStateAccessor
from file_migration.data_accessors.source_accessor import SourceAccessor
from file_migration.data_accessors.target_accessor import TargetAccessor
from file_migration.downloader.downloader import Downloader
from file_migration.downloader.opendrive_downloader import (
    OpenDriveDownloadClient,
    OpenDriveDownloader,
)
from file_migration.flow.delete_flow import DeleteFlow, OpenDriveDeleteClient
from file_migration.flow.export_flow import ExportFlow
from file_migration.migration.delete_migration import DeleteMigration
from file_migration.migration.export_migration import ExportMigration
from file_migration.uploader.google_drive_uploader import GoogleDriveUploader
from file_migration.uploader.google_photos_uploader import GooglePhotosUploader
from file_migration.uploader.noop_uploader import NoopUploader
from file_migration.uploader.uploader import Uploader


class CompositionRoot:
    GOOGLE_DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.file"
    GOOGLE_PHOTOS_SCOPE = "https://www.googleapis.com/auth/photoslibrary.appendonly"
    GOOGLE_PHOTOS_READ_SCOPE = (
        "https://www.googleapis.com/auth/photoslibrary.readonly.appcreateddata"
    )

    def __init__(
        self,
        config: JobConfig,
        *,
        open_drive_download_client: OpenDriveDownloadClient | None = None,
        open_drive_delete_client: OpenDriveDeleteClient | None = None,
        downloader: Downloader | None = None,
        uploader: Uploader | None = None,
    ) -> None:
        self._config = config
        self._db_factory = DbSessionFactory(config.db.url)
        default_open_drive_client = OpenDriveClient(
            api_key=config.downloader.api_key,
            api_secret=config.downloader.api_secret,
        )
        self._open_drive_download_client = open_drive_download_client or default_open_drive_client
        self._open_drive_delete_client = open_drive_delete_client or default_open_drive_client
        self._downloader = downloader
        self._uploader = uploader
        self._db_factory.initialize_schema()

    def build_export_migration(self) -> ExportMigration:
        session = self._db_factory.create_session()
        source_accessor, target_accessor, state_accessor = self._build_accessors(session)
        flow = ExportFlow(
            config=self._config,
            source_accessor=source_accessor,
            target_accessor=target_accessor,
            state_accessor=state_accessor,
        )
        return ExportMigration(flow)

    def build_delete_migration(self) -> DeleteMigration:
        session = self._db_factory.create_session()
        _, _, state_accessor = self._build_accessors(session)
        flow = DeleteFlow(
            config=self._config,
            open_drive_client=self._open_drive_delete_client,
            state_accessor=state_accessor,
        )
        return DeleteMigration(flow)

    def _build_accessors(
        self, session: Session
    ) -> tuple[SourceAccessor, TargetAccessor, MigrationStateAccessor]:
        downloader = self._downloader or OpenDriveDownloader(
            api_key=self._config.downloader.api_key,
            api_secret=self._config.downloader.api_secret,
            client=self._open_drive_download_client,
        )
        uploader = self._uploader or self._build_uploader()
        source_accessor = SourceAccessor(downloader=downloader)
        target_accessor = TargetAccessor(uploader=uploader)
        state_accessor = MigrationStateAccessor(session=session)
        return source_accessor, target_accessor, state_accessor

    def _build_uploader(self) -> Uploader:
        if self._config.uploader.provider == "noop":
            return NoopUploader()

        oauth_client_id = self._config.uploader.oauth_client_id
        oauth_client_secret = self._config.uploader.oauth_client_secret
        if oauth_client_id is None:
            raise ValueError("oauth_client_id is required for Google uploads")
        if oauth_client_secret is None:
            raise ValueError("oauth_client_secret is required for Google uploads")

        if self._config.uploader.provider == "google_photos":
            album_name = self._config.uploader.album_name
            if album_name is None:
                raise ValueError("album_name is required for google_photos")
            token_provider = GoogleOAuthTokenProvider(
                client_id=oauth_client_id,
                client_secret=oauth_client_secret,
                scopes=[self.GOOGLE_PHOTOS_SCOPE, self.GOOGLE_PHOTOS_READ_SCOPE],
            )
            return GooglePhotosUploader(
                album_name=album_name,
                token_provider=token_provider,
            )

        target_path = self._config.uploader.target_path
        if target_path is None:
            raise ValueError("target_path is required for google_drive")
        token_provider = GoogleOAuthTokenProvider(
            client_id=oauth_client_id,
            client_secret=oauth_client_secret,
            scopes=[self.GOOGLE_DRIVE_SCOPE],
        )
        return GoogleDriveUploader(
            drive_path=target_path,
            token_provider=token_provider,
        )
