from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from kitchenlab.schema import Retrieval, Technique


def _catalog_path() -> Path:
    return Path(__file__).resolve().parent / "data" / "catalog.json"


@lru_cache(maxsize=1)
def load_catalog() -> dict:
    return json.loads(_catalog_path().read_text(encoding="utf-8"))


def _blob(item: dict) -> str:
    dishes = " ".join(item.get("dishes") or [])
    terms = " ".join(item.get("terms") or [])
    return " ".join(
        [
            item.get("id", ""),
            item.get("name", ""),
            item.get("purpose", ""),
            item.get("mechanism", ""),
            dishes,
            terms,
        ]
    ).casefold()


def search_catalog(query: str) -> dict:
    needle = " ".join(query.casefold().split())
    catalog = load_catalog()
    techniques = catalog["techniques"]
    if needle:
        techniques = [item for item in techniques if needle in _blob(item) or any(part in _blob(item) for part in needle.split())]
    return {
        "version": catalog["version"],
        "source": catalog["source"],
        "techniques": techniques,
    }


def _as_technique(item: dict) -> Technique:
    return Technique(
        id=item["id"],
        name=item["name"],
        purpose=item.get("purpose", ""),
        mechanism=item.get("mechanism", ""),
        terms=list(item.get("terms") or []),
    )


def techniques_for(dish: str, limit: int = 5) -> list[Technique]:
    hits = search_catalog(dish).get("techniques") or []
    return [_as_technique(item) for item in hits[:limit]]


def techniques_in_text(text: str, limit: int = 5) -> list[Technique]:
    blob = text.casefold()
    scored: list[tuple[int, int, dict]] = []
    for item in load_catalog()["techniques"]:
        score = 0
        if item["id"].replace("-", " ") in blob or item["name"].casefold() in blob:
            score += 5
        for term in item.get("terms") or []:
            if term and term.casefold() in blob:
                score += 2
        if score:
            scored.append((score, int(item.get("step_order") or 1000), item))
    scored.sort(key=lambda row: (-row[0], row[1]))
    return [_as_technique(item) for _, _, item in scored[:limit]]


def techniques_in_retrievals(
    retrievals: list[Retrieval],
    limit: int = 5,
    dish: str = "",
) -> list[Technique]:
    blob = " ".join(filter(None, (f"{item.title} {item.passage}" for item in retrievals)))
    mentioned = techniques_in_text(blob, limit=12)
    if dish.strip():
        relevant = {item.id for item in techniques_for(dish, limit=12)}
        if relevant:
            mentioned = [item for item in mentioned if item.id in relevant]
    return mentioned[:limit]


def catalog_entry(technique_id: str) -> dict | None:
    for item in load_catalog()["techniques"]:
        if item["id"] == technique_id:
            return item
    return None


def match_technique(text: str, techniques: list[Technique] | None = None) -> Technique | None:
    blob = text.casefold()
    catalog = techniques_for(text, limit=12)
    pool = list(techniques or []) + catalog
    seen: set[str] = set()
    scored: list[tuple[int, Technique]] = []
    for item in pool:
        if item.id in seen:
            continue
        seen.add(item.id)
        score = 0
        if item.id.replace("-", " ") in blob or item.name.casefold() in blob:
            score += 5
        for term in item.terms:
            if term.casefold() in blob:
                score += 2
        if score:
            scored.append((score, item))
    if not scored:
        return None
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return scored[0][1]
