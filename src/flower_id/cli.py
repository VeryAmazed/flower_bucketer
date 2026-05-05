from __future__ import annotations

import argparse
from pathlib import Path

from flower_id.bucketing import copy_image, destination_for, find_existing_filename, iter_images
from flower_id.config import AppConfig, load_config, require_api_key
from flower_id.manifest import (
    ManifestRow,
    append_row,
    filename_exists,
    load_rows,
    utc_now,
)
from flower_id.plantnet import Identification, PlantNetClient


def main() -> None:
    parser = argparse.ArgumentParser(prog="flower-id")
    parser.add_argument("--config", default="config.toml", help="Path to config.toml")

    subparsers = parser.add_subparsers(dest="command", required=True)

    scan_parser = subparsers.add_parser("scan", help="Bucket new images from the configured inbox")
    scan_parser.add_argument("--dry-run", action="store_true", help="Preview without API calls or copying")

    subparsers.add_parser("quota", help="Show Pl@ntNet daily quota")
    sync_parser = subparsers.add_parser("sync-manifest", help="Add bucketed files missing from the manifest")
    sync_parser.add_argument("--dry-run", action="store_true", help="Preview manifest rows without writing")

    args = parser.parse_args()
    config = load_config(Path(args.config))

    if args.command == "scan":
        client = None
        if not args.dry_run:
            client = make_client(config)
        scan(
            config.paths.inbox_dir,
            config.paths.bucket_root,
            config.paths.low_confidence_dir,
            config.paths.manifest_csv,
            client,
            config.plantnet.min_score,
            args.dry_run,
        )
    elif args.command == "quota":
        client = make_client(config)
        show_quota(client)
    elif args.command == "sync-manifest":
        sync_manifest(
            config.paths.bucket_root,
            config.paths.low_confidence_dir,
            config.paths.manifest_csv,
            args.dry_run,
        )


def scan(
    inbox_dir: Path,
    bucket_root: Path,
    low_confidence_dir: Path,
    manifest_path: Path,
    client: PlantNetClient | None,
    min_score: float,
    dry_run: bool,
) -> None:
    rows = load_rows(manifest_path)
    images = iter_images(inbox_dir)

    if not images:
        print(f"No supported images found in {inbox_dir}.")
        return

    for image_path in images:
        if filename_exists(rows, image_path.name):
            print(f"SKIP already in manifest: {image_path.name}")
            continue

        existing = find_existing_filename(bucket_root, image_path.name)
        if existing:
            print(f"SKIP filename already exists in bucket root: {image_path.name} -> {existing}")
            continue

        existing_low_confidence = find_existing_filename(low_confidence_dir, image_path.name)
        if existing_low_confidence:
            print(
                "SKIP filename already exists in low-confidence folder: "
                f"{image_path.name} -> {existing_low_confidence}"
            )
            continue

        if dry_run:
            print(f"WOULD IDENTIFY: {image_path}")
            continue

        if client is None:
            raise SystemExit("Internal error: live scan requires a Pl@ntNet client.")

        identification = client.identify(image_path)
        if identification.genus_score < min_score:
            low_confidence_destination = low_confidence_dir / image_path.name
            copy_image(image_path, low_confidence_destination)
            print(
                f"LOW GENUS CONFIDENCE: {image_path.name} -> {identification.genus} "
                f"({identification.genus_score:.3f}); copied to {low_confidence_destination}"
            )
            continue

        destination = destination_for(bucket_root, identification.genus, image_path.name)
        copy_image(image_path, destination)

        row = make_manifest_row(image_path.name, bucket_root, destination, identification)
        append_row(manifest_path, row)
        rows.append(row.as_dict())
        print(f"COPIED: {image_path.name} -> {destination}")


def make_client(config: AppConfig) -> PlantNetClient:
    return PlantNetClient(
        api_key=require_api_key(config.plantnet.api_key),
        project=config.plantnet.project,
        nb_results=config.plantnet.nb_results,
    )


def make_manifest_row(
    filename: str,
    bucket_root: Path,
    destination: Path,
    identification: Identification,
) -> ManifestRow:
    return ManifestRow(
        filename=filename,
        bucket_genus=identification.genus,
        bucket_relative_path=str(destination.relative_to(bucket_root)),
        plantnet_genus=identification.genus,
        plantnet_family=identification.family,
        plantnet_genus_score=f"{identification.genus_score:.6f}",
        identified_at=utc_now(),
    )


def sync_manifest(
    bucket_root: Path,
    low_confidence_dir: Path,
    manifest_path: Path,
    dry_run: bool,
) -> None:
    if not bucket_root.exists():
        raise SystemExit(f"Bucket root does not exist: {bucket_root}")

    rows = load_rows(manifest_path)
    known_filenames = {row.get("filename") for row in rows}
    synced_count = 0

    for image_path in iter_bucketed_images(bucket_root, low_confidence_dir):
        if image_path.name in known_filenames:
            continue

        row = make_synced_manifest_row(bucket_root, image_path)
        if dry_run:
            print(f"WOULD ADD: {row.filename} -> {row.bucket_relative_path}")
        else:
            append_row(manifest_path, row)
            print(f"ADDED: {row.filename} -> {row.bucket_relative_path}")

        known_filenames.add(image_path.name)
        synced_count += 1

    if synced_count == 0:
        print("Manifest already matches bucket folders.")


def iter_bucketed_images(bucket_root: Path, low_confidence_dir: Path) -> list[Path]:
    low_confidence_dir = low_confidence_dir.resolve()
    images = []

    for path in sorted(bucket_root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
            continue
        if _is_relative_to(path.resolve(), low_confidence_dir):
            continue
        images.append(path)

    return images


def make_synced_manifest_row(bucket_root: Path, image_path: Path) -> ManifestRow:
    relative_path = image_path.relative_to(bucket_root)
    genus = relative_path.parts[0] if len(relative_path.parts) > 1 else ""

    return ManifestRow(
        filename=image_path.name,
        bucket_genus=genus,
        bucket_relative_path=str(relative_path),
        plantnet_genus="",
        plantnet_family="",
        plantnet_genus_score="",
        identified_at=utc_now(),
        notes="synced from bucket folder",
    )


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def show_quota(client: PlantNetClient) -> None:
    quota = client.quota()
    identify = (quota.get("quota") or {}).get("identify")
    if identify:
        print(
            f"Identify quota for {quota.get('day', 'today')}: "
            f"{identify.get('remaining')} remaining of {identify.get('total')} "
            f"({identify.get('count')} used)"
        )
        return

    print(quota)


if __name__ == "__main__":
    main()
