from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MigrationItem:
    item_id: str
    name: str
    source_path: str
    mime_type: str
    size_bytes: int
