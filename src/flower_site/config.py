from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from flower_id.config import AppConfig, load_config


@dataclass(frozen=True)
class SiteConfig:
    title: str
    description: str
    content_toml: Path
    output_dir: Path


@dataclass(frozen=True)
class BuildConfig:
    app: AppConfig
    site: SiteConfig


def load_build_config(config_path: Path) -> BuildConfig:
    app_config = load_config(config_path)
    raw = _load_raw_config(config_path)
    site = raw.get("site", {})

    return BuildConfig(
        app=app_config,
        site=SiteConfig(
            title=str(site.get("title", "Flower Buckets")),
            description=str(site.get("description", "")),
            content_toml=_path_from_config(config_path, site.get("content_toml", "site.toml")),
            output_dir=_path_from_config(config_path, site.get("output_dir", "docs")),
        ),
    )


def _load_raw_config(config_path: Path) -> dict:
    if not config_path.exists():
        return {}

    with config_path.open("rb") as config_file:
        return tomllib.load(config_file)


def _path_from_config(config_path: Path, value: object) -> Path:
    path = Path(str(value)).expanduser()
    if path.is_absolute():
        return path
    return config_path.parent / path

