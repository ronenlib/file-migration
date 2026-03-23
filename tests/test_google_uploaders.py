from __future__ import annotations

from pathlib import Path

from file_migration.context.migration_item import MigrationItem
from file_migration.uploader.google_drive_uploader import GoogleDriveUploader
from file_migration.uploader.google_photos_uploader import GooglePhotosUploader


class FakeGoogleDriveClient:
    def __init__(self) -> None:
        self.calls: list[tuple[Path, str, str]] = []

    def upload_file(self, file_path: Path, *, remote_name: str, parent_path: str) -> str:
        self.calls.append((file_path, remote_name, parent_path))
        return "drive-file-id"


class FakeGooglePhotosClient:
    def __init__(self) -> None:
        self.ensure_album_calls: list[str] = []
        self.upload_calls: list[tuple[Path, str]] = []

    def ensure_album(self, album_name: str) -> str:
        self.ensure_album_calls.append(album_name)
        return "album-123"

    def upload_media_item(self, file_path: Path, *, album_id: str) -> str:
        self.upload_calls.append((file_path, album_id))
        return "media-item-456"


def test_google_drive_uploader_uses_drive_client(tmp_path: Path) -> None:
    file_path = tmp_path / "photo.jpg"
    file_path.write_bytes(b"jpg")
    item = MigrationItem(
        item_id="item-1",
        name="photo.jpg",
        source_path="/Trips/photo.jpg",
        mime_type="image/jpeg",
        size_bytes=3,
    )
    client = FakeGoogleDriveClient()

    uploader = GoogleDriveUploader(
        drive_path="/Imports/Trips",
        token_provider=None,
        client=client,
    )

    file_id = uploader.upload(file_path, item)

    assert file_id == "drive-file-id"
    assert client.calls == [(file_path, "photo.jpg", "/Imports/Trips")]


def test_google_photos_uploader_creates_album_once_then_uploads(tmp_path: Path) -> None:
    first_file = tmp_path / "first.jpg"
    first_file.write_bytes(b"1")
    second_file = tmp_path / "second.jpg"
    second_file.write_bytes(b"2")
    item = MigrationItem(
        item_id="item-1",
        name="first.jpg",
        source_path="/Trips/first.jpg",
        mime_type="image/jpeg",
        size_bytes=1,
    )
    client = FakeGooglePhotosClient()

    uploader = GooglePhotosUploader(
        album_name="Imported Album",
        token_provider=None,
        client=client,
    )

    first_id = uploader.upload(first_file, item)
    second_id = uploader.upload(second_file, item)

    assert first_id == "media-item-456"
    assert second_id == "media-item-456"
    assert client.ensure_album_calls == ["Imported Album"]
    assert client.upload_calls == [
        (first_file, "album-123"),
        (second_file, "album-123"),
    ]
