from __future__ import annotations

import re

from kitchenlab.catalog import catalog_entry, techniques_in_retrievals
from kitchenlab.schema import Retrieval, Technique

STOP_TERMS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "were",
    "was",
    "have",
    "been",
    "their",
    "into",
    "recipe",
    "recipes",
}


def _observation(check: str, status: str, detail: str, evidence: list[dict], scope: str) -> dict:
    return {
        "check": check,
        "status": status,
        "detail": detail,
        "evidence": evidence[:8],
        "scope": scope,
    }


def _terms_for(item: Technique) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()
    catalog_terms = list((catalog_entry(item.id) or {}).get("terms") or [])
    for term in [*item.terms, *catalog_terms]:
        cleaned = term.strip()
        key = cleaned.casefold()
        if len(cleaned) >= 3 and key not in STOP_TERMS and key not in seen:
            seen.add(key)
            terms.append(cleaned)
    if terms:
        return terms[:12]
    for word in re.split(r"\W+", item.name):
        if len(word) >= 4 and word.casefold() not in STOP_TERMS:
            terms.append(word)
    return terms[:12]


def _short_title(title: str) -> str:
    text = re.split(r"\s+[|–—]\s+", title.strip(), maxsplit=1)[0]
    text = " ".join(text.split())
    if len(text) <= 72:
        return text or "a retrieved page"
    clipped = text[:72].rsplit(" ", 1)[0].rstrip(".,;:")
    return clipped or text[:72]


def _hit(title: str, url: str, text: str, start: int, end: int) -> dict:
    left = max(0, start - 80)
    right = min(len(text), end + 80)
    snippet = " ".join(text[left:right].split())[:240]
    return {"title": title, "url": url, "snippet": snippet}


def _corpus(retrievals: list[Retrieval]) -> list[tuple[Retrieval, str]]:
    pages = []
    for item in retrievals:
        text = " ".join(filter(None, [item.title, item.passage]))
        if text.strip():
            pages.append((item, text))
    return pages


def _scope(retrievals: list[Retrieval]) -> str:
    titles = [item.title or item.url for item in retrievals if item.title or item.url]
    if not titles:
        return "no retrieved pages"
    if len(titles) <= 3:
        return ", ".join(titles)
    return f"{len(titles)} retrieved pages, including {', '.join(titles[:2])}"


def _match_technique(item: Technique, pages: list[tuple[Retrieval, str]], scope: str) -> dict:
    terms = _terms_for(item)
    hits: list[dict] = []
    for retrieval, text in pages:
        folded = text.casefold()
        for term in terms:
            index = folded.find(term.casefold())
            if index < 0:
                continue
            hits.append(_hit(retrieval.title or retrieval.url, retrieval.url, text, index, index + len(term)))
            if len(hits) >= 8:
                break
        if len(hits) >= 8:
            break
    if hits:
        where = _short_title(hits[0].get("title") or "a retrieved page")
        return _observation(
            item.id,
            "OBSERVED",
            f"Found in {where}.",
            hits,
            scope,
        )
    if catalog_entry(item.id) or terms:
        return _observation(
            item.id,
            "NOT OBSERVED",
            "Not found in the pages we read.",
            [],
            scope,
        )
    return _observation(
        item.id,
        "UNKNOWN",
        "The pages we read do not settle this.",
        [],
        scope,
    )


def run_checks(
    retrievals: list[Retrieval],
    techniques: list[Technique] | None = None,
    dish: str = "",
) -> dict:
    chosen = list(techniques or [])[:5]
    if not chosen:
        chosen = techniques_in_retrievals(retrievals, limit=5, dish=dish)
    pages = _corpus(retrievals)
    scope = _scope(retrievals)
    observations = [_match_technique(item, pages, scope) for item in chosen]
    return {
        "include_docs": False,
        "file_count": len(retrievals),
        "scope": scope,
        "observations": observations,
        "techniques": [item.model_dump() for item in chosen],
    }
