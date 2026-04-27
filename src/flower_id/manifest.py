from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


FIELDNAMES = [
    "filename",
    "bucket_genus",
    "bucket_relative_path",
    "plantnet_best_match",
    "plantnet_species_without_author",
    "plantnet_genus",
    "plantnet_family",
    "plantnet_score",
    "plantnet_gbif_id",
    "identified_at",
    "notes",
]


@dataclass(frozen=True)
class ManifestRow:
    filename: str
    bucket_genus: str
    bucket_relative_path: str
    plantnet_best_match: str
    plantnet_species_without_author: str
    plantnet_genus: str
    plantnet_family: str
    plantnet_score: str
    plantnet_gbif_id: str
    identified_at: str
    notes: str = ""

    def as_dict(self) -> dict[str, str]:
        return {
            "filename": self.filename,
            "bucket_genus": self.bucket_genus,
            "bucket_relative_path": self.bucket_relative_path,
            "plantnet_best_match": self.plantnet_best_match,
            "plantnet_species_without_author": self.plantnet_species_without_author,
            "plantnet_genus": self.plantnet_genus,
            "plantnet_family": self.plantnet_family,
            "plantnet_score": self.plantnet_score,
            "plantnet_gbif_id": self.plantnet_gbif_id,
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
