from __future__ import annotations

import re
import shutil
from pathlib import Path


SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def iter_images(inbox_dir: Path) -> list[Path]:
    if not inbox_dir.exists():
        raise SystemExit(f"Inbox directory does not exist: {inbox_dir}")
    if not inbox_dir.is_dir():
        raise SystemExit(f"Inbox path is not a directory: {inbox_dir}")

    return sorted(
        path
        for path in inbox_dir.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    )


def sanitize_genus(genus: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9_. -]+", "", genus).strip()
    clean = re.sub(r"\s+", "_", clean)
    if not clean:
        raise SystemExit(f"Could not make a folder name from genus: {genus!r}")
    return clean


def find_existing_filename(bucket_root: Path, filename: str) -> Path | None:
    if not bucket_root.exists():
        return None

    for path in bucket_root.rglob(filename):
        if path.is_file():
            return path
    return None


def destination_for(bucket_root: Path, genus: str, filename: str) -> Path:
    return bucket_root / sanitize_genus(genus) / filename


def copy_image(source: Path, destination: Path) -> None:
    if destination.exists():
        raise SystemExit(f"Destination already exists, not overwriting: {destination}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(source), str(destination))
