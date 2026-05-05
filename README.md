# Flower ID

Local flower photo bucketing using the Pl@ntNet API.

This script scans a folder of new flower photos, asks Pl@ntNet for one identification per image, and copies confident matches into genus folders. Successfully bucketed images are recorded in a CSV manifest that can be version controlled.

## Setup

Create a virtual environment and install the package:

```sh
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

`config.toml` is intentionally ignored by git because it points to local folders.

Create a Pl@ntNet account at <https://my.plantnet.org/signup>, then generate your private API key at <https://my.plantnet.org/settings/api-key>.

Put the key in `.env`:

```sh
PLANTNET_API_KEY=your-private-api-key-here
```

## Config

```toml
[paths]
inbox_dir = "/path/to/new_flower_photos"
bucket_root = "/path/to/local_flower_buckets"
low_confidence_dir = "/path/to/low_confidence_review"
manifest_csv = "data/manifest.csv"

[plantnet]
project = "all"
min_score = 0.65
nb_results = 3
```

The inbox can keep your source images. Successfully bucketed images are copied into genus folders, not moved.

## Commands

Preview the inbox without API calls, file copies, or manifest writes:

```sh
flower-id scan --dry-run
```

Run the real scan:

```sh
flower-id scan
```

Check Pl@ntNet quota:

```sh
flower-id quota
```

After manually sorting images from the low-confidence folder into genus buckets, backfill missing bucketed files into the manifest:

```sh
flower-id sync-manifest
```

Preview the backfill without writing:

```sh
flower-id sync-manifest --dry-run
```

## Behavior

- Supported images are `.jpg`, `.jpeg`, and `.png`.
- One image is sent per Pl@ntNet request.
- Pl@ntNet is queried with `detailed=true` so the script can use genus-level confidence.
- If the top genus score is below `min_score`, the image is copied to `low_confidence_dir` and not added to the CSV.
- If the image's filename already exists in the manifest, it is skipped.
- If the same filename already exists anywhere under `bucket_root`, it is skipped.
- If the same filename already exists anywhere under `low_confidence_dir`, it is skipped.
- Confident matches are copied to `<bucket_root>/<Genus>/<filename>`.
- The manifest records only successfully bucketed images.
- `sync-manifest` scans `bucket_root` and adds any bucketed image filename missing from the manifest. Rows added this way have blank Pl@ntNet fields and `notes` set to `synced from bucket folder`.
