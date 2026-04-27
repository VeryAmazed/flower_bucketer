from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests


BASE_URL = "https://my-api.plantnet.org/v2"


@dataclass(frozen=True)
class Identification:
    best_match: str
    species_without_author: str
    genus: str
    family: str
    score: float
    gbif_id: str


class PlantNetClient:
    def __init__(self, api_key: str, project: str = "all", nb_results: int = 3) -> None:
        self.api_key = api_key
        self.project = project
        self.nb_results = nb_results

    def quota(self) -> dict[str, Any]:
        response = requests.get(
            f"{BASE_URL}/quota/daily",
            params={"api-key": self.api_key},
            timeout=30,
        )
        _raise_for_status(response)
        return response.json()

    def identify(self, image_path: Path) -> Identification:
        with image_path.open("rb") as image_file:
            response = requests.post(
                f"{BASE_URL}/identify/{self.project}",
                params={
                    "api-key": self.api_key,
                    "nb-results": self.nb_results,
                    "lang": "en",
                },
                files={"images": (image_path.name, image_file, _mime_type(image_path))},
                timeout=90,
            )

        _raise_for_status(response)
        return parse_identification(response.json())


def parse_identification(payload: dict[str, Any]) -> Identification:
    results = payload.get("results") or []
    if not results:
        raise SystemExit("Pl@ntNet returned no species results.")

    top = results[0]
    species = top.get("species") or {}
    genus = species.get("genus") or {}
    family = species.get("family") or {}
    gbif = top.get("gbif") or {}

    genus_name = genus.get("scientificNameWithoutAuthor") or genus.get("scientificName")
    if not genus_name:
        raise SystemExit("Pl@ntNet result did not include a genus.")

    return Identification(
        best_match=str(payload.get("bestMatch") or species.get("scientificName") or ""),
        species_without_author=str(species.get("scientificNameWithoutAuthor") or ""),
        genus=str(genus_name),
        family=str(family.get("scientificNameWithoutAuthor") or family.get("scientificName") or ""),
        score=float(top.get("score") or 0),
        gbif_id=str(gbif.get("id") or ""),
    )


def _raise_for_status(response: requests.Response) -> None:
    if response.ok:
        return

    message = response.text.strip()
    if len(message) > 500:
        message = message[:500] + "..."
    raise SystemExit(f"Pl@ntNet request failed with HTTP {response.status_code}: {message}")


def _mime_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".png":
        return "image/png"
    raise SystemExit(f"Unsupported image type: {path}")
