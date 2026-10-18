from __future__ import annotations

import os

import httpx
from fastapi import HTTPException


def _key() -> str:
    key = os.environ.get("TAVILY_API_KEY", "").strip()
    if not key:
        raise HTTPException(status_code=400, detail="TAVILY_API_KEY is not set.")
    return key


def search(query: str, depth: str = "basic") -> dict:
    chosen = depth if depth in {"basic", "advanced"} else "basic"
    response = httpx.post(
        "https://api.tavily.com/search",
        json={
            "api_key": _key(),
            "query": query,
            "max_results": 5,
            "search_depth": chosen,
            "include_answer": False,
        },
        timeout=45,
    )
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail="Tavily search failed.")
    body = response.json()
    results = []
    for item in body.get("results") or []:
        results.append(
            {
                "title": item.get("title") or "",
                "url": item.get("url") or "",
                "content": (item.get("content") or "")[:1200],
            }
        )
    return {"query": query, "depth": chosen, "results": results}


def extract(urls: list[str]) -> dict:
    cleaned = [url for url in urls if url.startswith("https://")][:5]
    if not cleaned:
        raise HTTPException(status_code=400, detail="Extract requires https URLs.")
    response = httpx.post(
        "https://api.tavily.com/extract",
        json={"api_key": _key(), "urls": cleaned},
        timeout=45,
    )
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail="Tavily extract failed.")
    body = response.json()
    pages = []
    for item in body.get("results") or []:
        pages.append(
            {
                "url": item.get("url") or "",
                "content": (item.get("raw_content") or item.get("content") or "")[:2000],
            }
        )
    return {"results": pages}
