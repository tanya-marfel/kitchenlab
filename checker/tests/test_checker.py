from __future__ import annotations

import base64
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from breachmirror.api import app, store
from breachmirror.checks import run_checks
from breachmirror.github_public import materialize_github, parse_target
from breachmirror.paths import repo_root
from breachmirror.schema import Finding, ReportIn, Source, Status
from breachmirror.validate import ground_report


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CASE_DIR", str(tmp_path))
    store.root = tmp_path
    counter = tmp_path / "counter.txt"
    if counter.exists():
        counter.unlink()
    return TestClient(app)


def test_before_and_after_checks():
    before = run_checks(repo_root() / "demo-target" / "before", include_docs=False)
    by_id = {item["check"]: item for item in before["observations"]}
    assert by_id["unpinned_pretrained"]["status"] == "OBSERVED"
    assert by_id["write_or_network_tool"]["status"] == "OBSERVED"
    assert by_id["exposed_token_literal"]["status"] == "NOT OBSERVED"
    assert by_id["authorization_step"]["status"] == "UNKNOWN"
    assert by_id["isolation"]["status"] == "UNKNOWN"
    assert "app/main.py" in by_id["unpinned_pretrained"]["scope"]

    with_docs = run_checks(repo_root() / "demo-target" / "before", include_docs=True)
    docs = {item["check"]: item for item in with_docs["observations"]}
    assert docs["authorization_step"]["status"] == "OBSERVED"
    assert "docs/controls.md" in docs["authorization_step"]["scope"]

    after = run_checks(repo_root() / "demo-target" / "after", include_docs=False)
    pinned = {item["check"]: item for item in after["observations"]}
    assert pinned["unpinned_pretrained"]["status"] == "NOT OBSERVED"
    assert pinned["unpinned_pretrained"]["scope"]


def test_atlas_search(client: TestClient):
    response = client.get("/atlas/search", params={"q": "tool invocation"})
    assert response.status_code == 200
    ids = [item["id"] for item in response.json()["techniques"]]
    assert "AML.T0053" in ids


def test_not_observed_requires_scope():
    with pytest.raises(ValueError):
        Finding(
            id="exposed-credentials",
            prerequisite="Exposed credentials",
            observation="None found",
            why_it_matters="The disclosure describes credential use.",
            limitations="Scope is limited.",
            next_check="Review secret storage.",
            status=Status.NOT_OBSERVED,
            evidence_refs=["01"],
        )


def test_report_requires_both_source_kinds():
    report = ReportIn(
        sources=[
            Source(ref="01", title="Disclosure", url="https://example.com/a", source_type="Primary"),
        ],
        findings=[
            Finding(
                id="custom",
                prerequisite="A condition",
                observation="Seen",
                why_it_matters="It matters.",
                limitations="Limited.",
                next_check="Look again.",
                status=Status.REPORTED,
                evidence_refs=["01"],
            )
        ],
    )
    with pytest.raises(ValueError):
        ground_report(report, ["https://example.com/a"], [])


def test_primary_url_must_have_been_retrieved():
    report = ReportIn(
        sources=[
            Source(
                ref="01",
                title="Disclosure",
                url="https://example.com/not-retrieved",
                source_type="Primary",
                passage="A sentence.",
            ),
            Source(ref="02", title="app/main.py", source_type="Code", path="app/main.py", line_start=1, line_end=2),
        ],
        findings=[
            Finding(
                id="custom",
                prerequisite="A condition",
                observation="Seen",
                why_it_matters="It matters.",
                limitations="Limited.",
                next_check="Look again.",
                status=Status.INFERRED,
                evidence_refs=["01", "02"],
            )
        ],
    )
    with pytest.raises(ValueError):
        ground_report(report, ["https://example.com/other"], [])


def test_case_check_and_recheck(client: TestClient):
    created = client.post(
        "/cases",
        json={"incident": "July 2026 disclosure", "target": "demo-target/before", "sample": True},
    )
    assert created.status_code == 200
    case_id = created.json()["id"]
    checked = client.post(
        "/checks/run",
        json={"case_id": case_id, "target": "demo-target/before", "include_docs": False},
    )
    assert checked.status_code == 200
    assert checked.json()["observations"][1]["status"] == "OBSERVED"

    report = {
        "summary_known": "Two primary accounts describe the July 2026 intrusion.",
        "summary_unknown": "Runtime isolation is not in the repository.",
        "open_questions": ["Where do runtime secrets live?"],
        "recommendation": "Pin the model revision.",
        "recommendation_limits": "Only the inspected files were reviewed.",
        "sources": [
            {
                "ref": "01",
                "title": "Security incident disclosure — July 2026",
                "url": "https://huggingface.co/blog/security-incident-july-2026",
                "source_type": "Primary",
                "published": "2026-07-16",
                "retrieved": "2026-10-18",
                "passage": "Earlier this week, we detected and responded to an intrusion into part of our production infrastructure.",
            },
            {
                "ref": "02",
                "title": "app/main.py",
                "source_type": "Code",
                "path": "app/main.py",
                "line_start": 8,
                "line_end": 9,
                "passage": "AutoModel.from_pretrained(\"example-org/customer-model\")",
            },
        ],
        "timeline": [
            {
                "id": "hf-disclosure",
                "title": "Hugging Face discloses the intrusion",
                "summary": "Hugging Face published its disclosure.",
                "occurred": "2026-07-10",
                "disclosed": "2026-07-16",
                "status": "REPORTED",
                "source_refs": ["01"],
            }
        ],
        "findings": [
            {
                "id": "untrusted-load",
                "prerequisite": "Untrusted model content was loaded without a pinned revision.",
                "observation": "from_pretrained is called without a revision pin.",
                "why_it_matters": "The disclosures describe code execution that started from untrusted dataset and model handling.",
                "limitations": "The file does not prove this repository is deployed.",
                "next_check": "Confirm whether production loads this file.",
                "status": "OBSERVED",
                "scope": "app/main.py",
                "evidence_refs": ["01", "02"],
                "atlas_ids": ["AML.T0010.003"],
                "mitigation_ids": ["AML.M0030"],
            }
        ],
    }
    case = client.get(f"/cases/{case_id}").json()
    case["retrieved_urls"] = ["https://huggingface.co/blog/security-incident-july-2026"]
    # The public API does not accept a raw case write. Seed the URL through the store.
    stored = store.get(case_id)
    stored.retrieved_urls = case["retrieved_urls"]
    store.save(stored)

    posted = client.post(f"/cases/{case_id}/report", json=report)
    assert posted.status_code == 200, posted.text
    body = posted.json()
    assert body["stage"] == "COMPLETE"
    assert "does not establish that the application is secure" in body["recommendation_limits"]

    rechecked = client.post(f"/cases/{case_id}/recheck", json={"check": "unpinned_pretrained"})
    assert rechecked.status_code == 200, rechecked.text
    simulation = rechecked.json()["simulation"]
    assert simulation["label"] == "SIMULATION"
    assert simulation["before_status"] == "OBSERVED"
    assert simulation["after_status"] == "NOT OBSERVED"
    finding = rechecked.json()["findings"][0]
    assert finding["status"] == "NOT OBSERVED"


def test_github_materialize_reads_public_blobs(tmp_path):
    content = base64.b64encode(b"print('hello')\n").decode()

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/repos/acme/widgets":
            return httpx.Response(200, json={"default_branch": "main"})
        if path == "/repos/acme/widgets/git/trees/main":
            return httpx.Response(200, json={"tree": [{"path": "app.py", "type": "blob"}]})
        if path == "/repos/acme/widgets/contents/app.py":
            return httpx.Response(200, json={"encoding": "base64", "content": content, "size": 14})
        return httpx.Response(404)

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        result = materialize_github("acme", "widgets", tmp_path, http)
    assert result["files"] == ["app.py"]
    assert (tmp_path / "app.py").read_text(encoding="utf-8") == "print('hello')\n"
    assert parse_target("https://github.com/acme/widgets") == ("acme", "widgets")


def test_local_target_rejects_paths_outside_demo(client: TestClient):
    response = client.post("/checks/run", json={"target": "/etc", "include_docs": False})
    assert response.status_code == 400
    assert json.loads(response.text)["detail"]
