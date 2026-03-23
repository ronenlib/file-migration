from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from file_migration.config.loader import JobConfigLoader


def test_loader_requires_drive_target_path() -> None:
    config_text = """
job_name: drive-job

db:
  url: "sqlite+pysqlite:///:memory:"

downloader:
  provider: opendrive
  source_folder_id: folder-123
  api_key: key
  api_secret: secret

uploader:
  provider: google_drive
  oauth_client_id: client-id
  oauth_client_secret: client-secret
  target_path: null

intermediate_steps: []
workspace_dir: .cache/file-migration
"""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.yaml"
        config_path.write_text(config_text, encoding="utf-8")

        with pytest.raises(ValueError, match="target_path"):
            JobConfigLoader().load(str(config_path))


def test_loader_allows_noop_uploader_without_credentials() -> None:
    config_text = """
job_name: download-only-job

db:
  url: "sqlite+pysqlite:///:memory:"

downloader:
  provider: opendrive
  source_folder_id: folder-123
  api_key: key
  api_secret: secret

uploader:
  provider: noop

intermediate_steps: []
workspace_dir: .cache/file-migration
"""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.yaml"
        config_path.write_text(config_text, encoding="utf-8")

        config = JobConfigLoader().load(str(config_path))

        assert config.uploader.provider == "noop"
        assert config.uploader.oauth_client_id is None
        assert config.uploader.oauth_client_secret is None


def test_loader_allows_google_photos_without_target_path() -> None:
    config_text = """
job_name: photos-job

db:
  url: "sqlite+pysqlite:///:memory:"

downloader:
  provider: opendrive
  source_folder_id: folder-123
  api_key: key
  api_secret: secret

uploader:
  provider: google_photos
  oauth_client_id: client-id
  oauth_client_secret: client-secret
  album_name: Imported Album

intermediate_steps: []
workspace_dir: .cache/file-migration
"""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.yaml"
        config_path.write_text(config_text, encoding="utf-8")

        config = JobConfigLoader().load(str(config_path))

        assert config.uploader.provider == "google_photos"
        assert config.uploader.target_path is None


def test_loader_allows_google_drive_without_album_name() -> None:
    config_text = """
job_name: drive-job

db:
  url: "sqlite+pysqlite:///:memory:"

downloader:
  provider: opendrive
  source_folder_id: folder-123
  api_key: key
  api_secret: secret

uploader:
  provider: google_drive
  oauth_client_id: client-id
  oauth_client_secret: client-secret
  target_path: /Imports/Trip Archive

intermediate_steps: []
workspace_dir: .cache/file-migration
"""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.yaml"
        config_path.write_text(config_text, encoding="utf-8")

        config = JobConfigLoader().load(str(config_path))

        assert config.uploader.provider == "google_drive"
        assert config.uploader.album_name is None
