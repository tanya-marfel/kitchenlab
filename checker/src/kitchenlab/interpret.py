"""Read one freeform message and name the cooking question and dish in it."""

from __future__ import annotations

import json
import os

import httpx
from fastapi import HTTPException

SYSTEM = """Read the user's message and identify two things:
- the cooking question they want investigated
- the dish or technique it is about
Infer both from the wording. Do not assume a particular recipe.
Return JSON only, with keys question and dish.
question is the investigative ask, including any disagreement they named.
dish is the food or method (for example crispy roast potatoes, pizza dough, steak salting).
If the message is already a question, question may be the full message.
If the dish is not named, use a short label taken from the question."""


def infer_request(message: str) -> dict[str, str]:
    text = message.strip()
    if not text:
        raise HTTPException(status_code=400, detail="A message is required.")
    key = os.environ.get("NEBIUS_API_KEY", "").strip()
    model = os.environ.get("NEBIUS_MODEL", "").strip()
    base = os.environ.get("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1").rstrip("/")
    if not key or not model:
        raise HTTPException(status_code=503, detail="The message interpreter is not configured.")
    try:
        response = httpx.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": model,
                "temperature": 0,
                "messages": [
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": text},
                ],
            },
            timeout=60,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
    except (httpx.HTTPError, KeyError, IndexError, TypeError) as exc:
        raise HTTPException(status_code=502, detail="The message could not be interpreted.") from exc
    parsed = _json_object(content)
    question = str(parsed.get("question") or text).strip()
    dish = str(parsed.get("dish") or "").strip()
    if not question:
        raise HTTPException(status_code=422, detail="The message did not name a cooking question.")
    return {"question": question, "dish": dish or question}


def _json_object(content: str) -> dict:
    start = content.find("{")
    end = content.rfind("}")
    if start < 0 or end <= start:
        raise HTTPException(status_code=502, detail="The message could not be interpreted.")
    try:
        parsed = json.loads(content[start : end + 1])
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail="The message could not be interpreted.") from exc
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=502, detail="The message could not be interpreted.")
    return parsed
