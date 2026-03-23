from __future__ import annotations

import tempfile
from pathlib import Path

from file_migration.composition import CompositionRoot
from file_migration.config.job_config import DbConfig, DownloaderConfig, JobConfig, UploaderConfig
from file_migration.context.migration_item import MigrationItem
from file_migration.downloader.downloader import Downloader
from file_migration.uploader.uploader import Uploader


class FakeOpenDriveDownloader(Downloader):
    def __init__(self, api_key: str, api_secret: str, *, client: object | None = None) -> None:
        _ = (api_key, api_secret, client)
        self._items: dict[str, bytes] = {"remote/photo1.jpg": b"hello-bytes"}

    def list_items(self, source_path: str) -> list[MigrationItem]:
        assert source_path == "folder-123"
        return [
            MigrationItem(
                item_id="file-1",
                name="photo1.jpg",
                source_path="remote/photo1.jpg",
                mime_type="image/jpeg",
                size_bytes=len(self._items["remote/photo1.jpg"]),
            )
        ]

    def download(self, item: MigrationItem, workspace: Path) -> Path:
        destination = workspace / item.name
        destination.write_bytes(self._items[item.source_path])
        return destination


class FakeOpenDriveClient:
    def __init__(self, api_key: str, api_secret: str) -> None:
        _ = (api_key, api_secret)
        self.deleted_file_ids: list[str] = []

    def delete_file(self, file_id: str) -> None:
        self.deleted_file_ids.append(file_id)


class FakeGooglePhotosUploader(Uploader):
    def __init__(self, album_name: str) -> None:
        _ = album_name
        self.uploaded_files: list[str] = []

    def upload(self, file_path: Path, item: MigrationItem) -> str:
        _ = item
        self.uploaded_files.append(file_path.name)
        return "photo-media-id"


def test_export_then_delete_flow() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        db_path = base / "state.sqlite"
        config = JobConfig(
            job_name="job-1",
            db=DbConfig(url=f"sqlite+pysqlite:///{db_path}"),
            downloader=DownloaderConfig(
                provider="opendrive",
                source_folder_id="folder-123",
                api_key="key",
                api_secret="secret",
            ),
            uploader=UploaderConfig(
                provider="google_photos",
                oauth_client_id="client-id",
                oauth_client_secret="client-secret",
                target_path=None,
                album_name="Album",
            ),
            intermediate_steps=("noop",),
            workspace_dir=str(base / "workspace"),
        )

        open_drive_client = FakeOpenDriveClient(api_key="key", api_secret="secret")
        downloader = FakeOpenDriveDownloader(api_key="key", api_secret="secret", client=None)
        uploader = FakeGooglePhotosUploader(
            album_name="Album",
        )
        composition = CompositionRoot(
            config,
            open_drive_delete_client=open_drive_client,
            downloader=downloader,
            uploader=uploader,
        )
        composition.build_export_migration().run()

        workspace_file = base / "workspace" / "photo1.jpg"
        assert workspace_file.exists() is False

        composition.build_delete_migration().run()
        assert open_drive_client.deleted_file_ids == ["file-1"]
