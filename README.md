# file-migration

A generic Python CLI for state-aware file migration jobs.

## Supported providers (current)

- Downloader (source): `opendrive`
- Uploaders (target): `google_photos`, `google_drive`, `noop`

## CLI commands

```bash
file-migration export <config_path>
file-migration delete <config_path>
```

## Core architecture

Project structure is intentionally split by responsibility:

- `client/`: various external client implementation
- `downloader/`: downloader interface + provider implementations
- `uploader/`: uploader interface + provider implementations
- `migration/`: migration interfaces + implementations
- `flow/`: orchestration flows (`export`, `delete`)
- `data_accessors/`: database and provider accessors
- `context/`: domain models and migration stages
- `config/`: config schema, loader, and validation

### Export flow

`download -> (future intermediate steps) -> upload -> mark exported`

- Intermediate steps are not implemented yet.
- Config already includes `intermediate_steps` for future processors (example: ffmpeg encoding).

### Delete flow

`select EXPORTED rows -> delete source item -> mark DELETED`

## State model

State is persisted in PostgreSQL and grouped by `job_name`.

Unique key: `(job_name, source_item_id)`.

Tracked fields include:

- stage
- target provider/id
- local temporary path
- error message

## Configuration example

```yaml
job_name: trip-archive-2026

# place DB state outside of code and keep it backed up continuously
db:
  url: postgresql+psycopg://migration:migration@localhost:5432/file_migration

downloader:
  provider: opendrive
  source_folder_id: "0"   # OpenDrive directory ID
  api_key: ${OPENDRIVE_API_KEY}
  api_secret: ${OPENDRIVE_API_SECRET}

uploader:
  provider: google_photos
  oauth_client_id: ${GOOGLE_OAUTH_CLIENT_ID}
  oauth_client_secret: ${GOOGLE_OAUTH_CLIENT_SECRET}
  album_name: Imported Album

# Reserved extension point. Flow will run download, then iterate these names, then upload.
intermediate_steps:
  - noop_step_1
  - noop_step_2

workspace_dir: .cache/file-migration
```

Download-only mode:

```yaml
uploader:
  provider: noop
```

## Provider config and auth

### OpenDrive downloader

Use `downloader` like this:

```yaml
downloader:
  provider: opendrive
  source_folder_id: "0" # OpenDrive directory ID to enumerate
  api_key: ${OPENDRIVE_API_KEY}
  api_secret: ${OPENDRIVE_API_SECRET}
```

Notes:

- `source_folder_id` is the remote OpenDrive directory ID, not a local filesystem path.
- Use `"0"` to enumerate the OpenDrive root directory.
- `api_key` and `api_secret` are the OpenDrive API login credentials used to open a session.

OpenDrive auth:

- This app logs in to the OpenDrive API with `api_key` and `api_secret`, then reuses the returned session for list, download, and delete operations.
- Keep these values in environment variables or secret storage and reference them from the YAML config.

### Google Photos uploader

Use `uploader` like this:

```yaml
uploader:
  provider: google_photos
  oauth_client_id: ${GOOGLE_OAUTH_CLIENT_ID}
  oauth_client_secret: ${GOOGLE_OAUTH_CLIENT_SECRET}
  album_name: Imported Album
```

Notes:

- `album_name` is required for `google_photos`.
- The uploader is responsible for ensuring the album exists. If the album is missing, it creates it before uploading media.
- Google Photos API behavior changed on March 31, 2025: app-created albums and app-created media are the supported model for this integration.

Google Photos auth:

- `oauth_client_id` and `oauth_client_secret` must come from a Google OAuth client.
- Service accounts are not supported for Google Photos Library API access.
- The app generates a one-time consent URL at runtime, you paste back the returned authorization code, and the resulting refresh token is kept only in memory until the process exits.
- The Google Photos uploader requests both `https://www.googleapis.com/auth/photoslibrary.appendonly` and `https://www.googleapis.com/auth/photoslibrary.readonly.appcreateddata` so it can create albums, upload media, and look up app-created albums.

### Google Drive uploader

Use `uploader` like this:

```yaml
uploader:
  provider: google_drive
  oauth_client_id: ${GOOGLE_OAUTH_CLIENT_ID}
  oauth_client_secret: ${GOOGLE_OAUTH_CLIENT_SECRET}
  target_path: /Imports/Trip Archive
```

Notes:

- `target_path` is required for `google_drive`.
- The uploader creates any missing folders in the target path before uploading the file.

Google Drive auth:

- `oauth_client_id` and `oauth_client_secret` use the same Google OAuth client model as Google Photos.
- The uploader prompts for a one-time authorization code, exchanges it for tokens, and keeps the refresh token only in memory for the current run.
- Minimum practical scope depends on how you want to use Drive:
  - `https://www.googleapis.com/auth/drive.file` is the narrower option and is preferred when the app only needs to manage files it creates.
  - Inference from the Drive scope docs: if you want this app to find and reuse arbitrary pre-existing folders anywhere in Drive, you may need the broader `https://www.googleapis.com/auth/drive` scope instead.

### No-op uploader

Use `uploader` like this for download-only runs:

```yaml
uploader:
  provider: noop
```

Notes:

- `noop` performs no remote upload.
- It exists to support download-only mode while keeping the export flow and state transitions intact.
- No credentials are required for `noop`.

### Google OAuth runtime flow

Both Google uploaders use the OAuth client values from config and do not write tokens to disk.

How it works:

- Put `uploader.oauth_client_id` and `uploader.oauth_client_secret` in the YAML config.
- Start the job.
- The app starts a temporary localhost callback listener and prints a Google consent URL for the uploader's scope.
- Open that URL and approve access. Google redirects back to the local CLI listener and the job continues automatically.
- The app exchanges the code for tokens and keeps the refresh token only in memory until the process exits.

Notes:

- `google_photos` uses `https://www.googleapis.com/auth/photoslibrary.appendonly` and `https://www.googleapis.com/auth/photoslibrary.readonly.appcreateddata`.
- `google_drive` uses `https://www.googleapis.com/auth/drive.file`.
- If the localhost callback listener cannot be used, the CLI falls back to asking you to paste the returned authorization code manually.
- If you rerun the job later, you should expect to repeat the consent/code step unless you add your own persistence layer outside this repo.

## Validation rules

- `job_name` is required and used to group all state.
- Only `opendrive` is valid downloader for now.
- Uploader must be `google_photos`, `google_drive`, or `noop`.
- Google uploaders require `uploader.oauth_client_id` and `uploader.oauth_client_secret`.
- `google_drive` requires `uploader.target_path`.
- `google_photos` requires `uploader.album_name`.
- `noop` does not require uploader credentials or target settings.

## PostgreSQL via Docker

```bash
docker compose up -d
```

The Docker setup exposes PostgreSQL on `localhost:5432` with:

- database: `file_migration`
- user: `migration`
- password: `migration`

SQLAlchemy connection URL:

```bash
postgresql+psycopg://migration:migration@localhost:5432/file_migration
```

Connect with `psql`:

```bash
psql postgresql://migration:migration@localhost:5432/file_migration
```

Simple query example:

```sql
SELECT * FROM migration_states LIMIT 1;
```

## Install

This project uses [`asdf`](https://asdf-vm.com/) and pins Python in [.tool-versions](/Users/ronenlib/dev/file-migration/.tool-versions).

```bash
asdf install
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

`asdf install` should be run first so Python 3.11 is installed before creating the virtualenv.

## Security notes

- Do not commit API keys or OAuth credentials.
- Keep secrets in secure storage and pass references in config.
- Keep state DB durable and synced (backup/replication) because resume correctness depends on it.

## Quality

This repository is configured for:

- Black formatting
- isort import sorting
- unit tests with pytest

Common commands:

```bash
make format
make ci
```
