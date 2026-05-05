from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


FIELDNAMES = [
    "filename",
    "bucket_genus",
    "bucket_relative_path",
    "plantnet_genus",
    "plantnet_family",
    "plantnet_genus_score",
    "identified_at",
    "notes",
]


@dataclass(frozen=True)
class ManifestRow:
    filename: str
    bucket_genus: str
    bucket_relative_path: str
    plantnet_genus: str
    plantnet_family: str
    plantnet_genus_score: str
    identified_at: str
    notes: str = ""

    def as_dict(self) -> dict[str, str]:
        return {
            "filename": self.filename,
            "bucket_genus": self.bucket_genus,
            "bucket_relative_path": self.bucket_relative_path,
            "plantnet_genus": self.plantnet_genus,
            "plantnet_family": self.plantnet_family,
            "plantnet_genus_score": self.plantnet_genus_score,
            "identified_at": self.identified_at,
            "notes": self.notes,
        }


def load_rows(manifest_path: Path) -> list[dict[str, str]]:
    if not manifest_path.exists():
        return []

    with manifest_path.open("r", newline="", encoding="utf-8") as manifest_file:
        return list(csv.DictReader(manifest_file))


def filename_exists(rows: list[dict[str, str]], filename: str) -> bool:
    return any(row.get("filename") == filename for row in rows)


def append_row(manifest_path: Path, row: ManifestRow) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not manifest_path.exists()

    with manifest_path.open("a", newline="", encoding="utf-8") as manifest_file:
        writer = csv.DictWriter(manifest_file, fieldnames=FIELDNAMES)
        if new_file:
            writer.writeheader()
        writer.writerow(row.as_dict())


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
