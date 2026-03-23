from __future__ import annotations

from enum import StrEnum


class MigrationStage(StrEnum):
    PENDING = "pending"
    DOWNLOADED = "downloaded"
    UPLOADED = "uploaded"
    EXPORTED = "exported"
    DELETING = "deleting"
    DELETED = "deleted"
    FAILED = "failed"
