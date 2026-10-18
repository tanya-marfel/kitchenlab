from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse


def repo_root() -> Path:
    configured = os.environ.get("KITCHENLAB_ROOT")
    if configured:
        return Path(configured).resolve()
    return Path(__file__).resolve().parents[3]


def case_dir() -> Path:
    configured = os.environ.get("CASE_DIR")
    path = Path(configured) if configured else repo_root() / "checker" / "data" / "cases"
    path.mkdir(parents=True, exist_ok=True)
    return path


def is_allowed_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
