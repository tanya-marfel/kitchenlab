#!/usr/bin/env python3
"""Create the local n8n owner, Token Factory credential, and active workflow."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = os.environ.get("N8N_URL", "http://localhost:5678")
EMAIL = os.environ.get("BOOTSTRAP_EMAIL", "judge@example.com")
PASSWORD = os.environ.get("BOOTSTRAP_PASSWORD", "KitchenLab-demo-1")
WORKFLOW = ROOT / "n8n" / "workflows" / "kitchenlab.json"


def request(method: str, path: str, payload: dict | None = None, cookie: str = "") -> tuple[int, dict, str]:
    data = None if payload is None else json.dumps(payload).encode()
    headers = {"Content-Type": "application/json"}
    if cookie:
        headers["Cookie"] = cookie
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            raw = response.read().decode()
            set_cookie = response.headers.get("Set-Cookie", "")
            body = json.loads(raw) if raw else {}
            return response.status, body, set_cookie
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            body = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            body = {"raw": raw}
        return exc.code, body, ""


def cookie_from(header: str) -> str:
    parts = []
    for chunk in header.split(","):
        piece = chunk.split(";", 1)[0].strip()
        if "=" in piece and piece.startswith("n8n"):
            parts.append(piece)
    return "; ".join(parts)


def wait_until_ready() -> None:
    for _ in range(60):
        try:
            request("GET", "/healthz")
            return
        except Exception:
            time.sleep(2)
    raise SystemExit("n8n did not become ready at " + BASE)


def main() -> None:
    key = os.environ.get("NEBIUS_API_KEY", "").strip()
    if not key:
        raise SystemExit("Set NEBIUS_API_KEY before bootstrapping n8n.")
    wait_until_ready()
    status, _, set_cookie = request(
        "POST",
        "/rest/owner/setup",
        {"email": EMAIL, "firstName": "Judge", "lastName": "Demo", "password": PASSWORD},
    )
    cookie = cookie_from(set_cookie)
    if status not in {200, 201}:
        status, _, set_cookie = request(
            "POST",
            "/rest/login",
            {"emailOrLdapLoginId": EMAIL, "password": PASSWORD},
        )
        cookie = cookie_from(set_cookie)
        if status not in {200, 201}:
            raise SystemExit(
                "Could not create or sign in the n8n owner. "
                "Open http://localhost:5678 and create the owner, then rerun this script. "
                f"Last status: {status}"
            )
    status, created, _ = request(
        "POST",
        "/rest/credentials",
        {
            "name": "Token Factory",
            "type": "openAiApi",
            "data": {
                "apiKey": key,
                "url": "https://api.tokenfactory.nebius.com/v1",
            },
        },
        cookie,
    )
    if status not in {200, 201}:
        raise SystemExit(f"Could not create the Token Factory credential ({status}). {created}")
    credential_id = created.get("id") or created.get("data", {}).get("id")
    if not credential_id:
        raise SystemExit(f"Credential response did not include an id: {created}")
    workflow = json.loads(WORKFLOW.read_text(encoding="utf-8"))
    for node in workflow["nodes"]:
        credentials = node.get("credentials") or {}
        if "openAiApi" in credentials:
            credentials["openAiApi"]["id"] = credential_id
    status, stored, _ = request("POST", "/rest/workflows", workflow, cookie)
    if status not in {200, 201}:
        raise SystemExit(f"Could not import the workflow ({status}). {stored}")
    workflow_id = stored.get("id") or stored.get("data", {}).get("id")
    status, _, _ = request("PATCH", f"/rest/workflows/{workflow_id}", {"active": True}, cookie)
    if status not in {200, 201}:
        request("POST", f"/api/v1/workflows/{workflow_id}/activate", cookie=cookie)
    print(f"Workflow {workflow_id} is ready at {BASE}/webhook/kitchenlab")


if __name__ == "__main__":
    main()
