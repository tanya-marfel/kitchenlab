from __future__ import annotations

import os
import re
from pathlib import Path
from urllib.parse import urlparse

from fastapi import HTTPException

GITHUB_RE = re.compile(r"^https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?(?:/.*)?$")


def repo_root() -> Path:
    configured = os.environ.get("BREACHMIRROR_ROOT")
    if configured:
        return Path(configured).resolve()
    return Path(__file__).resolve().parents[3]


def demo_root() -> Path:
    configured = os.environ.get("DEMO_ROOT")
    if configured:
        return Path(configured).resolve()
    return (repo_root() / "demo-target").resolve()


def case_dir() -> Path:
    configured = os.environ.get("CASE_DIR")
    path = Path(configured) if configured else repo_root() / "checker" / "data" / "cases"
    path.mkdir(parents=True, exist_ok=True)
    return path


def parse_github(target: str) -> tuple[str, str] | None:
    match = GITHUB_RE.match(target.strip())
    if not match:
        return None
    return match.group(1), match.group(2)


def resolve_local_target(target: str) -> Path:
    raw = Path(target)
    if raw.is_absolute():
        path = raw.resolve()
    else:
        path = (repo_root() / target).resolve()
    allowed = demo_root()
    if path != allowed and allowed not in path.parents:
        raise HTTPException(
            status_code=400,
            detail="Local targets must stay inside demo-target. Use a public GitHub URL for anything else.",
        )
    if not path.is_dir():
        raise HTTPException(status_code=404, detail="Target directory was not found.")
    return path


def is_allowed_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
