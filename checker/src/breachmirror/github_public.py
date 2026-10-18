from __future__ import annotations

from pathlib import Path

import httpx

from breachmirror.paths import parse_github

MAX_FILES = 25
MAX_BYTES = 80_000
ALLOWED_SUFFIXES = {".py", ".md", ".yml", ".yaml", ".toml", ".json", ".txt"}


def materialize_github(owner: str, repo: str, dest: Path, client: httpx.Client) -> dict:
    dest.mkdir(parents=True, exist_ok=True)
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "breachmirror"}
    meta = client.get(f"https://api.github.com/repos/{owner}/{repo}", headers=headers)
    meta.raise_for_status()
    default_branch = meta.json().get("default_branch") or "HEAD"
    tree = client.get(
        f"https://api.github.com/repos/{owner}/{repo}/git/trees/{default_branch}",
        params={"recursive": "1"},
        headers=headers,
    )
    tree.raise_for_status()
    written: list[str] = []
    for item in tree.json().get("tree", []):
        if item.get("type") != "blob":
            continue
        path = item.get("path") or ""
        if Path(path).suffix.lower() not in ALLOWED_SUFFIXES:
            continue
        if ".." in Path(path).parts:
            continue
        blob = client.get(f"https://api.github.com/repos/{owner}/{repo}/contents/{path}", headers=headers)
        if blob.status_code != 200:
            continue
        payload = blob.json()
        if payload.get("encoding") != "base64" or payload.get("size", 0) > MAX_BYTES:
            continue
        import base64

        raw = base64.b64decode(payload.get("content") or "")
        target = (dest / path).resolve()
        if dest.resolve() not in target.parents:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        written.append(path)
        if len(written) >= MAX_FILES:
            break
    return {"owner": owner, "repo": repo, "branch": default_branch, "files": written}


def parse_target(target: str) -> tuple[str, str] | None:
    return parse_github(target)
