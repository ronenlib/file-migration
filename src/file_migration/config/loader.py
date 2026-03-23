from __future__ import annotations

from pathlib import Path
from typing import Mapping

import yaml

from file_migration.config.job_config import DbConfig, DownloaderConfig, JobConfig, UploaderConfig
from file_migration.config.validator import validate_job_config


class JobConfigLoader:
    def load(self, config_path: str) -> JobConfig:
        raw_config: Mapping[str, object]
        with Path(config_path).expanduser().open("r", encoding="utf-8") as file_handle:
            loaded = yaml.safe_load(file_handle)
            if not isinstance(loaded, dict):
                raise ValueError("Config root must be a mapping.")
            raw_config = loaded

        job_name = _read_string(raw_config, "job_name")
        db_map = _read_mapping(raw_config, "db")
        downloader_map = _read_mapping(raw_config, "downloader")
        uploader_map = _read_mapping(raw_config, "uploader")

        db_config = DbConfig(url=_read_string(db_map, "url"))
        downloader_config = DownloaderConfig(
            provider=_read_string(downloader_map, "provider"),
            source_folder_id=_read_string(downloader_map, "source_folder_id"),
            api_key=_read_string(downloader_map, "api_key"),
            api_secret=_read_string(downloader_map, "api_secret"),
        )
        uploader_config = UploaderConfig(
            provider=_read_string(uploader_map, "provider"),
            oauth_client_id=_read_optional_string(uploader_map, "oauth_client_id"),
            oauth_client_secret=_read_optional_string(uploader_map, "oauth_client_secret"),
            target_path=_read_optional_string(uploader_map, "target_path"),
            album_name=_read_optional_string(uploader_map, "album_name"),
        )

        steps_value = raw_config.get("intermediate_steps", [])
        if not isinstance(steps_value, list):
            raise ValueError("intermediate_steps must be a list of strings.")
        steps: tuple[str, ...] = tuple(
            _assert_string_value(step, "intermediate_steps entry") for step in steps_value
        )

        workspace_dir = (
            _read_optional_string(raw_config, "workspace_dir") or ".cache/file-migration"
        )

        config = JobConfig(
            job_name=job_name,
            db=db_config,
            downloader=downloader_config,
            uploader=uploader_config,
            intermediate_steps=steps,
            workspace_dir=workspace_dir,
        )
        validate_job_config(config)
        return config


def _read_mapping(data: Mapping[str, object], key: str) -> Mapping[str, object]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be an object.")
    return value


def _read_string(data: Mapping[str, object], key: str) -> str:
    value = data.get(key)
    return _assert_string_value(value, key)


def _read_optional_string(data: Mapping[str, object], key: str) -> str | None:
    value = data.get(key)
    if value is None:
        return None
    return _assert_string_value(value, key)


def _assert_string_value(value: object, key: str) -> str:
    if not isinstance(value, str) or value.strip() == "":
        raise ValueError(f"{key} must be a non-empty string.")
    return value
