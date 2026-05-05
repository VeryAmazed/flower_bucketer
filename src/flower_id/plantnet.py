from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests


BASE_URL = "https://my-api.plantnet.org/v2"


@dataclass(frozen=True)
class Identification:
    genus: str
    family: str
    genus_score: float


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
                    "detailed": "true",
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
    species_genus = species.get("genus") or {}
    species_family = species.get("family") or {}
    genus_result = _first_other_result(payload, "genus")
    family_result = _first_other_result(payload, "family")

    genus_name = _taxon_name(genus_result) or _taxon_name(species_genus)
    if not genus_name:
        raise SystemExit("Pl@ntNet result did not include a genus.")

    return Identification(
        genus=str(genus_name),
        family=str(_taxon_name(family_result) or _taxon_name(species_family) or ""),
        genus_score=_score(genus_result, fallback=float(top.get("score") or 0)),
    )


def _first_other_result(payload: dict[str, Any], key: str) -> dict[str, Any]:
    other_results = payload.get("otherResults") or {}
    results = other_results.get(key) or []
    if results:
        return results[0]
    return {}


def _taxon_name(value: Any) -> str:
    if not isinstance(value, dict):
        return ""

    taxon = value.get("taxon") or value.get("genus") or value.get("family") or value
    if not isinstance(taxon, dict):
        return str(taxon) if taxon else ""

    return str(
        taxon.get("scientificNameWithoutAuthor")
        or taxon.get("scientificName")
        or taxon.get("name")
        or ""
    )


def _score(value: dict[str, Any], fallback: float = 0) -> float:
    return float(value.get("score") if value.get("score") is not None else fallback)


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
