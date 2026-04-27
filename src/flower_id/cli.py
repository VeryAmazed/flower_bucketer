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
    subparsers.add_parser("restore-plan", help="Print bucket paths from the manifest")

    args = parser.parse_args()
    config = load_config(Path(args.config))

    if args.command == "scan":
        client = None
        if not args.dry_run:
            client = make_client(config)
        scan(
            config.paths.inbox_dir,
            config.paths.bucket_root,
            config.paths.manifest_csv,
            client,
            config.plantnet.min_score,
            args.dry_run,
        )
    elif args.command == "quota":
        client = make_client(config)
        show_quota(client)


def scan(
    inbox_dir: Path,
    bucket_root: Path,
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

        if dry_run:
            print(f"WOULD IDENTIFY: {image_path}")
            continue

        if client is None:
            raise SystemExit("Internal error: live scan requires a Pl@ntNet client.")

        identification = client.identify(image_path)
        if identification.score < min_score:
            print(
                f"LOW CONFIDENCE: {image_path.name} -> {identification.best_match} "
                f"({identification.score:.3f}); not copying"
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
        plantnet_best_match=identification.best_match,
        plantnet_species_without_author=identification.species_without_author,
        plantnet_genus=identification.genus,
        plantnet_family=identification.family,
        plantnet_score=f"{identification.score:.6f}",
        plantnet_gbif_id=identification.gbif_id,
        identified_at=utc_now(),
    )


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
