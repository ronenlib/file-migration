from __future__ import annotations

from file_migration.config.job_config import JobConfig


def validate_job_config(config: JobConfig) -> None:
    if config.downloader.provider != "opendrive":
        raise ValueError("Only opendrive downloader is currently supported.")

    uploader_provider = config.uploader.provider
    if uploader_provider not in {"google_photos", "google_drive", "noop"}:
        raise ValueError("Uploader provider must be google_photos, google_drive, or noop.")

    if uploader_provider == "noop":
        return

    if uploader_provider == "google_drive" and not config.uploader.target_path:
        raise ValueError("uploader.target_path is required for google_drive uploads.")

    if not config.uploader.oauth_client_id:
        raise ValueError("uploader.oauth_client_id is required for Google uploads.")

    if not config.uploader.oauth_client_secret:
        raise ValueError("uploader.oauth_client_secret is required for Google uploads.")

    if uploader_provider == "google_photos" and not config.uploader.album_name:
        raise ValueError("uploader.album_name is required for google_photos uploads.")
