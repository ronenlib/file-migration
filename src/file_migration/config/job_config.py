from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True, slots=True)
class DbConfig:
    url: str


@dataclass(frozen=True, slots=True)
class DownloaderConfig:
    provider: str
    source_folder_id: str
    api_key: str
    api_secret: str


@dataclass(frozen=True, slots=True)
class UploaderConfig:
    provider: str
    oauth_client_id: Optional[str]
    oauth_client_secret: Optional[str]
    target_path: Optional[str]
    album_name: Optional[str]


@dataclass(frozen=True, slots=True)
class JobConfig:
    job_name: str
    db: DbConfig
    downloader: DownloaderConfig
    uploader: UploaderConfig
    intermediate_steps: tuple[str, ...]
    workspace_dir: str
