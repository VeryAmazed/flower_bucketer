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

Copy the example config and fill in your local paths:

```sh
cp config.example.toml config.toml
```

`config.toml` is intentionally ignored by git because it points to local folders.

Create a Pl@ntNet account at <https://my.plantnet.org/signup>, then generate your private API key at <https://my.plantnet.org/settings/api-key>.

Put the key in `.env`:

```sh
cp .env.example .env
```

Then edit `.env`:

```sh
PLANTNET_API_KEY=your-private-api-key-here
```

## Config

```toml
[paths]
inbox_dir = "/path/to/new_flower_photos"
bucket_root = "/path/to/local_flower_buckets"
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

Print the paths recorded in the manifest:

```sh
flower-id restore-plan
```

## Behavior

- Supported images are `.jpg`, `.jpeg`, and `.png`.
- One image is sent per Pl@ntNet request.
- The top Pl@ntNet result is used.
- If the top score is below `min_score`, the image is not copied and not added to the CSV.
- If the image's filename already exists in the manifest, it is skipped.
- If the same filename already exists anywhere under `bucket_root`, it is skipped.
- Confident matches are copied to `<bucket_root>/<Genus>/<filename>`.
- The manifest records only successfully bucketed images.
