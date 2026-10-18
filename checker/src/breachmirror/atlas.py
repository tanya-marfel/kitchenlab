from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path


def _atlas_path() -> Path:
    return Path(__file__).resolve().parent / "data" / "atlas.json"


@lru_cache(maxsize=1)
def load_atlas() -> dict:
    return json.loads(_atlas_path().read_text(encoding="utf-8"))


def search_atlas(query: str) -> dict:
    needle = query.casefold()
    catalog = load_atlas()
    techniques = [
        item
        for item in catalog["techniques"]
        if needle in item["id"].casefold()
        or needle in item["name"].casefold()
        or needle in item["summary"].casefold()
    ]
    mitigations = [
        item
        for item in catalog["mitigations"]
        if needle in item["id"].casefold()
        or needle in item["name"].casefold()
        or needle in item["summary"].casefold()
    ]
    if not needle:
        techniques = catalog["techniques"]
        mitigations = catalog["mitigations"]
    return {
        "version": catalog["version"],
        "source": catalog["source"],
        "techniques": techniques,
        "mitigations": mitigations,
    }
