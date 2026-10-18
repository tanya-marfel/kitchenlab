from __future__ import annotations

import os
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from breachmirror.atlas import search_atlas
from breachmirror.checks import run_checks
from breachmirror.github_public import materialize_github, parse_target
from breachmirror.paths import case_dir, demo_root, resolve_local_target
from breachmirror.schema import Case, CheckRequest, CreateCase, ReportIn, Simulation, Status
from breachmirror.store import CaseStore
from breachmirror.tavily_client import extract as tavily_extract
from breachmirror.tavily_client import search as tavily_search
from breachmirror.validate import ground_report

app = FastAPI(title="BreachMirror checker")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

store = CaseStore()


class EventIn(BaseModel):
    summary: str


class SearchIn(BaseModel):
    case_id: str
    query: str
    depth: str = "basic"


class ExtractIn(BaseModel):
    case_id: str
    urls: list[str] = Field(default_factory=list)


class RecheckIn(BaseModel):
    check: str = "unpinned_pretrained"


def _case_or_404(case_id: str) -> Case:
    try:
        return store.get(case_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Case not found.") from exc


def _materialize(target: str) -> Path:
    github = parse_target(target)
    if github:
        owner, repo = github
        dest = case_dir() / "mirrors" / f"{owner}-{repo}"
        token = os.environ.get("GITHUB_TOKEN", "").strip()
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            with httpx.Client(headers=headers, timeout=30, follow_redirects=False) as client:
                materialize_github(owner, repo, dest, client)
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail="GitHub read failed.") from exc
        return dest
    return resolve_local_target(target)


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/cases", response_model=Case)
def create_case(payload: CreateCase) -> Case:
    if not payload.incident.strip() or not payload.target.strip():
        raise HTTPException(status_code=400, detail="Incident and target are required.")
    return store.create(payload)


@app.get("/cases", response_model=list[Case])
def list_cases() -> list[Case]:
    return store.list_cases()


@app.get("/cases/{case_id}", response_model=Case)
def get_case(case_id: str) -> Case:
    return _case_or_404(case_id)


@app.post("/cases/{case_id}/events", response_model=Case)
def add_event(case_id: str, payload: EventIn) -> Case:
    _case_or_404(case_id)
    return store.add_event(case_id, payload.summary.strip())


@app.post("/cases/{case_id}/incident", response_model=Case)
def save_incident(case_id: str, payload: ReportIn) -> Case:
    case = _case_or_404(case_id)
    case.summary_known = payload.summary_known or case.summary_known
    case.summary_unknown = payload.summary_unknown or case.summary_unknown
    case.open_questions = payload.open_questions or case.open_questions
    if payload.sources:
        case.sources = payload.sources
    if payload.timeline:
        case.timeline = payload.timeline
    case.stage = "VERIFYING"
    store.add_event(case_id, "Incident section stored")
    case = store.get(case_id)
    case.summary_known = payload.summary_known or case.summary_known
    case.summary_unknown = payload.summary_unknown or case.summary_unknown
    case.open_questions = payload.open_questions or case.open_questions
    if payload.sources:
        case.sources = payload.sources
    if payload.timeline:
        case.timeline = payload.timeline
    case.stage = "VERIFYING"
    return store.save(case)


@app.post("/cases/{case_id}/report", response_model=Case)
def save_report(case_id: str, payload: ReportIn) -> Case:
    case = _case_or_404(case_id)
    try:
        grounded = ground_report(payload, case.retrieved_urls, case.checks)
    except ValueError as exc:
        case.stage = "PARTIAL"
        case.error = str(exc)
        store.save(case)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    case.summary_known = grounded.summary_known
    case.summary_unknown = grounded.summary_unknown
    case.open_questions = grounded.open_questions
    case.recommendation = grounded.recommendation
    case.recommendation_limits = grounded.recommendation_limits
    case.sources = grounded.sources
    case.timeline = grounded.timeline
    case.findings = grounded.findings
    case.stage = "COMPLETE" if grounded.findings else "PARTIAL"
    case.error = None
    store.add_event(case_id, "Conclusion updated · exposure report stored")
    case = store.get(case_id)
    case.summary_known = grounded.summary_known
    case.summary_unknown = grounded.summary_unknown
    case.open_questions = grounded.open_questions
    case.recommendation = grounded.recommendation
    case.recommendation_limits = grounded.recommendation_limits
    case.sources = grounded.sources
    case.timeline = grounded.timeline
    case.findings = grounded.findings
    case.stage = "COMPLETE" if grounded.findings else "PARTIAL"
    case.error = None
    return store.save(case)


@app.get("/atlas/search")
def atlas_search(q: str = "", case_id: str | None = None) -> dict:
    result = search_atlas(q)
    if case_id:
        _case_or_404(case_id)
        store.add_event(case_id, f"ATLAS lookup · {q or 'catalog'}")
    return result


@app.post("/checks/run")
def checks_run(payload: CheckRequest) -> dict:
    root = _materialize(payload.target)
    result = run_checks(root, include_docs=payload.include_docs)
    if payload.case_id:
        case = _case_or_404(payload.case_id)
        case.checks = result["observations"]
        case.scope_label = result["scope"]
        case.stage = "MAPPING"
        store.save(case)
        docs = "docs included" if payload.include_docs else "source files only"
        store.add_event(
            payload.case_id,
            f"Checked {result['file_count']} files · {docs}",
        )
    return result


@app.post("/inspect")
def inspect(payload: CheckRequest) -> dict:
    root = _materialize(payload.target)
    result = run_checks(root, include_docs=payload.include_docs)
    files = []
    for observation in result["observations"]:
        for evidence in observation["evidence"]:
            files.append(evidence)
    if payload.case_id:
        _case_or_404(payload.case_id)
        store.add_event(payload.case_id, f"Inspected target · {result['file_count']} files")
    return {"scope": result["scope"], "file_count": result["file_count"], "hits": files}


@app.post("/tools/tavily/search")
def tool_search(payload: SearchIn) -> dict:
    case = _case_or_404(payload.case_id)
    result = tavily_search(payload.query, payload.depth)
    for item in result["results"]:
        if item["url"] and item["url"] not in case.retrieved_urls:
            case.retrieved_urls.append(item["url"])
    case.stage = "RESEARCHING"
    store.save(case)
    store.add_event(payload.case_id, f"Tavily search · {payload.query[:80]}")
    return result


@app.post("/tools/tavily/extract")
def tool_extract(payload: ExtractIn) -> dict:
    case = _case_or_404(payload.case_id)
    result = tavily_extract(payload.urls)
    for item in result["results"]:
        if item["url"] and item["url"] not in case.retrieved_urls:
            case.retrieved_urls.append(item["url"])
    store.save(case)
    store.add_event(payload.case_id, f"Extracted {len(result['results'])} pages")
    return result


@app.post("/cases/{case_id}/recheck", response_model=Case)
def recheck(case_id: str, payload: RecheckIn) -> Case:
    case = _case_or_404(case_id)
    before = next((item for item in case.checks if item["check"] == payload.check), None)
    if before is None:
        raise HTTPException(status_code=409, detail="That check has not been run on this case.")
    after = run_checks(demo_root() / "after", include_docs=True)
    after_obs = next(item for item in after["observations"] if item["check"] == payload.check)
    case.simulation = Simulation(
        condition=payload.check,
        before=before["detail"],
        after=after_obs["detail"],
        before_status=Status(before["status"]),
        after_status=Status(after_obs["status"]),
        limits="Only this condition was re-checked against demo-target/after. This does not establish that the application is secure.",
    )
    for finding in case.findings:
        if finding.id == "untrusted-load" and payload.check == "unpinned_pretrained":
            finding.status = Status(after_obs["status"])
            finding.observation = after_obs["detail"]
            finding.scope = after_obs["scope"]
            finding.limitations = case.simulation.limits
    store.add_event(case_id, f"Simulation re-check · {payload.check} · {after_obs['status']}")
    case = store.get(case_id)
    case.simulation = Simulation(
        condition=payload.check,
        before=before["detail"],
        after=after_obs["detail"],
        before_status=Status(before["status"]),
        after_status=Status(after_obs["status"]),
        limits="Only this condition was re-checked against demo-target/after. This does not establish that the application is secure.",
    )
    for finding in case.findings:
        if finding.id == "untrusted-load" and payload.check == "unpinned_pretrained":
            finding.status = Status(after_obs["status"])
            finding.observation = after_obs["detail"]
            finding.scope = after_obs["scope"]
            finding.limitations = case.simulation.limits
    return store.save(case)
