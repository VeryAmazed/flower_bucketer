from __future__ import annotations

import argparse
from pathlib import Path

from flower_site.config import load_build_config
from flower_site.generator import build_site


def main() -> None:
    parser = argparse.ArgumentParser(prog="flower-site")
    parser.add_argument("--config", default="config.toml", help="Path to config.toml")

    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("build", help="Generate the static flower website")

    args = parser.parse_args()

    if args.command == "build":
        config = load_build_config(Path(args.config))
        build_site(config)


if __name__ == "__main__":
    main()

