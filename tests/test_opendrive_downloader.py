from __future__ import annotations

from pathlib import Path

from file_migration.client.open_drive_client import OpenDriveFile
from file_migration.context.migration_item import MigrationItem
from file_migration.downloader.opendrive_downloader import OpenDriveDownloader


class FakeOpenDriveClient:
    def __init__(self) -> None:
        self.downloads: list[tuple[str, Path]] = []

    def list_files(self, folder_id: str) -> list[OpenDriveFile]:
        assert folder_id == "folder-123"
        return [
            OpenDriveFile(
                file_id="file-1",
                name="photo.jpg",
                path="/Trips/photo.jpg",
                size_bytes=12,
                mime_type="image/jpeg",
            )
        ]

    def download_file(self, file_id: str, destination_path: Path) -> Path:
        self.downloads.append((file_id, destination_path))
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        destination_path.write_bytes(b"image-bytes")
        return destination_path


def test_opendrive_downloader_uses_client_for_list_and_download(tmp_path: Path) -> None:
    client = FakeOpenDriveClient()
    downloader = OpenDriveDownloader(api_key="key", api_secret="secret", client=client)

    items = downloader.list_items("folder-123")

    assert items == [
        MigrationItem(
            item_id="file-1",
            name="photo.jpg",
            source_path="/Trips/photo.jpg",
            mime_type="image/jpeg",
            size_bytes=12,
        )
    ]

    downloaded_path = downloader.download(items[0], tmp_path)
    assert downloaded_path.read_bytes() == b"image-bytes"
    assert client.downloads == [("file-1", tmp_path / "Trips" / "photo.jpg")]
