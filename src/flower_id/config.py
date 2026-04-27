from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path


DEFAULT_CONFIG_PATH = Path("config.toml")


@dataclass(frozen=True)
class PathsConfig:
    inbox_dir: Path
    bucket_root: Path
    manifest_csv: Path


@dataclass(frozen=True)
class PlantNetConfig:
    api_key: str | None
    project: str
    min_score: float
    nb_results: int


@dataclass(frozen=True)
class AppConfig:
    paths: PathsConfig
    plantnet: PlantNetConfig


def load_config(config_path: Path = DEFAULT_CONFIG_PATH) -> AppConfig:
    load_env_file(Path(".env"))

    if not config_path.exists():
        raise SystemExit(
            f"Missing {config_path}. Copy config.example.toml to config.toml and fill in your paths."
        )

    with config_path.open("rb") as config_file:
        raw = tomllib.load(config_file)

    paths = raw.get("paths", {})
    plantnet = raw.get("plantnet", {})
    api_key = os.environ.get("PLANTNET_API_KEY")

    return AppConfig(
        paths=PathsConfig(
            inbox_dir=_required_path(paths, "inbox_dir"),
            bucket_root=_required_path(paths, "bucket_root"),
            manifest_csv=_required_path(paths, "manifest_csv"),
        ),
        plantnet=PlantNetConfig(
            api_key=api_key,
            project=str(plantnet.get("project", "all")),
            min_score=float(plantnet.get("min_score", 0.65)),
            nb_results=int(plantnet.get("nb_results", 3)),
        ),
    )


def _required_path(section: dict, key: str) -> Path:
    value = section.get(key)
    if not value:
        raise SystemExit(f"Missing paths.{key} in config.toml.")
    return Path(str(value)).expanduser()


def require_api_key(api_key: str | None) -> str:
    if not api_key:
        raise SystemExit("Missing PLANTNET_API_KEY. Add it to your shell environment or a .env file.")
    return api_key


def load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)
