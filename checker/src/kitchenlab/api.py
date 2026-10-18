from __future__ import annotations

import threading
import time

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, model_validator

from kitchenlab.catalog import search_catalog
from kitchenlab.checks import run_checks
from kitchenlab.compose import _looks_like_summary, _mentions_techniques, _techniques_for, build_report, remember_retrieval
from kitchenlab.interpret import infer_request
from kitchenlab.schema import Case, CheckRequest, CreateCase, HistoryItem, ReportIn, Technique
from kitchenlab.simulate import simulate_change
from kitchenlab.store import CaseStore
from kitchenlab.tavily_client import extract as tavily_extract
from kitchenlab.tavily_client import search as tavily_search
from kitchenlab.validate import ground_report

app = FastAPI(title="KitchenLab checker")
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

    @model_validator(mode="before")
    @classmethod
    def split_url_text(cls, value: object) -> object:
        if isinstance(value, dict) and isinstance(value.get("urls"), str):
            parts = [part.strip() for part in value["urls"].replace(",", " ").split() if part.strip()]
            return {**value, "urls": parts}
        return value


class CatalogIn(BaseModel):
    case_id: str
    query: str = ""


class SimulateIn(BaseModel):
    change: str = ""


class InterpretIn(BaseModel):
    message: str


class FailIn(BaseModel):
    error: str = ""


class PromptIn(BaseModel):
    prompt: str = ""


def _case_or_404(case_id: str) -> Case:
    try:
        return store.get(case_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Question not found.") from exc


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/interpret")
def interpret(payload: InterpretIn) -> dict:
    return infer_request(payload.message)


@app.post("/cases", response_model=Case)
def create_case(payload: CreateCase) -> Case:
    if not payload.question.strip():
        raise HTTPException(status_code=400, detail="A cooking question is required.")
    return store.create(payload)


@app.get("/cases", response_model=list[Case])
def list_cases() -> list[Case]:
    return store.list_cases()


@app.get("/history", response_model=list[HistoryItem])
def list_history() -> list[HistoryItem]:
    return [
        HistoryItem(
            id=case.id,
            prompt=case.prompt,
            question=case.question,
            dish=case.dish,
            sample=case.sample,
            stage=case.stage,
            created_at=case.created_at,
            updated_at=case.updated_at,
        )
        for case in store.list_cases()
    ]


@app.get("/cases/{case_id}", response_model=Case)
def get_case(case_id: str) -> Case:
    return _case_or_404(case_id)


@app.post("/cases/{case_id}/prompt", response_model=Case)
def set_prompt(case_id: str, payload: PromptIn) -> Case:
    case = _case_or_404(case_id)
    text = payload.prompt.strip()
    if text:
        case.prompt = text
        store.save(case)
    return case


@app.delete("/cases/{case_id}", status_code=204)
def delete_case(case_id: str) -> None:
    try:
        store.delete(case_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Question not found.") from exc


def _apply_report(case: Case, report: ReportIn, *, finalize: bool = True) -> Case:
    case.summary_known = report.summary_known
    case.summary_unknown = report.summary_unknown
    case.open_questions = report.open_questions
    case.recommendation = report.recommendation
    case.recommendation_limits = report.recommendation_limits
    case.sources = report.sources
    case.conflicts = report.conflicts
    case.findings = report.findings
    if report.techniques:
        case.techniques = report.techniques
    if report.recipe:
        case.recipe = report.recipe
    if finalize:
        case.stage = "COMPLETE" if report.findings else "PARTIAL"
    elif case.stage not in {"COMPLETE", "PARTIAL", "FAILED"}:
        case.stage = "MAPPING"
    case.error = None
    return case


def _analyst_report(case: Case) -> bool:
    return any(finding.why_it_matters.strip() for finding in case.findings)


def _checks_cover_techniques(case: Case) -> bool:
    if not case.techniques:
        return bool(case.checks)
    ids = {item.get("check") for item in case.checks}
    return all(item.id in ids for item in case.techniques)


def _observation_statuses(observations: list) -> list[str]:
    statuses = []
    for item in observations or []:
        status = item.get("status") if isinstance(item, dict) else getattr(item, "status", None)
        statuses.append(status.value if hasattr(status, "value") else status)
    return [status for status in statuses if status]


def _extract_targets(case: Case) -> list[str]:
    have = {item.url: item for item in case.retrievals}
    already = any(event.summary.startswith("Extracted ") for event in case.events)
    urls = [url for url in case.retrieved_urls if url.startswith("https://")]
    if already:
        urls = [url for url in urls if have.get(url) is None or len(have[url].passage or "") < 10000]
    ranked = [url for url in urls if "youtube.com" not in url] + [url for url in urls if "youtube.com" in url]
    return ranked[:5]


def _needs_page_extract(case: Case, observations: list) -> bool:
    targets = _extract_targets(case)
    if not targets:
        return False
    statuses = _observation_statuses(observations)
    if not statuses:
        return True
    already = any(event.summary.startswith("Extracted ") for event in case.events)
    if already:
        return any(status in {"NOT OBSERVED", "UNKNOWN"} for status in statuses)
    return all(status in {"NOT OBSERVED", "UNKNOWN"} for status in statuses)


def _extract_retrieved(case: Case) -> Case:
    targets = _extract_targets(case)
    try:
        extracted = tavily_extract(targets)
    except HTTPException:
        extracted = {"results": []}
    for item in extracted["results"]:
        remember_retrieval(case, item["url"], passage=item["content"])
    if not case.retrievals:
        for url in case.retrieved_urls:
            remember_retrieval(case, url)
    store.save(case)
    store.add_event(case.id, f"Extracted {len(extracted['results'])} pages")
    return store.get(case.id)


def _run_page_checks(case: Case) -> Case:
    chosen = _techniques_for(case)
    result = run_checks(case.retrievals, techniques=chosen, dish=case.dish or case.question)
    case.checks = result["observations"]
    case.scope_label = result["scope"]
    case.techniques = chosen or [Technique.model_validate(item) for item in result["techniques"]]
    store.save(case)
    store.add_event(case.id, f"Checked {result['file_count']} retrieved pages")
    case = store.get(case.id)
    case.checks = result["observations"]
    case.scope_label = result["scope"]
    return case


@app.post("/cases/{case_id}/compose", response_model=Case)
def compose_case(case_id: str) -> Case:
    case = _case_or_404(case_id)
    existing = [{"status": finding.status} for finding in case.findings]
    stale = {item.id for item in case.findings} != {item.id for item in _techniques_for(case)}
    if (
        case.stage in {"COMPLETE", "PARTIAL"}
        and case.findings
        and _analyst_report(case)
        and not stale
        and not _needs_page_extract(case, existing or case.checks)
        and _looks_like_summary(case.summary_known or "", case.techniques or _techniques_for(case))
        and (case.summary_unknown or "").strip()
        not in {
            "",
            "Named techniques that were not established in the retrieved pages remain open.",
            "Recipes still disagree about which of these steps are necessary.",
        }
        and all(
            _mentions_techniques(source.passage or "", case.techniques or _techniques_for(case))
            for source in case.sources
            if source.passage
        )
    ):
        return case
    if stale or not case.checks or not _checks_cover_techniques(case) or _needs_page_extract(case, case.checks or existing):
        case = _run_page_checks(case)
    if _needs_page_extract(case, case.checks):
        case = _extract_retrieved(case)
        case = _run_page_checks(case)
    try:
        report = build_report(case, case.checks)
    except ValueError as exc:
        case.stage = "PARTIAL"
        case.error = str(exc)
        return store.save(case)
    case = _apply_report(case, report)
    store.save(case)
    store.add_event(case_id, "Report stored from retrieved pages and catalog checks")
    case = store.get(case_id)
    return store.save(_apply_report(case, report))


@app.post("/cases/{case_id}/fail", response_model=Case)
def fail_case(case_id: str, payload: FailIn) -> Case:
    _case_or_404(case_id)
    message = payload.error.strip() or "The investigation stopped before a report was stored."
    store.add_event(case_id, "Investigation stopped")
    case = store.get(case_id)
    case.stage = "FAILED"
    case.error = message
    return store.save(case)


@app.post("/cases/{case_id}/events", response_model=Case)
def add_event(case_id: str, payload: EventIn) -> Case:
    _case_or_404(case_id)
    return store.add_event(case_id, payload.summary.strip())


@app.post("/cases/{case_id}/recipes", response_model=Case)
def save_recipes(case_id: str, payload: ReportIn) -> Case:
    case = _case_or_404(case_id)
    if case.stage in {"COMPLETE", "PARTIAL"} and case.findings and _analyst_report(case):
        if payload.techniques and not case.techniques:
            case.techniques = payload.techniques[:5]
            return store.save(case)
        return case
    case.summary_known = payload.summary_known or case.summary_known
    case.summary_unknown = payload.summary_unknown or case.summary_unknown
    case.open_questions = payload.open_questions or case.open_questions
    if payload.sources:
        case.sources = payload.sources
    if payload.conflicts:
        case.conflicts = payload.conflicts
    if payload.techniques:
        case.techniques = payload.techniques[:5]
    case.stage = "VERIFYING"
    store.add_event(case_id, "Recipe section stored")
    case = store.get(case_id)
    case.summary_known = payload.summary_known or case.summary_known
    case.summary_unknown = payload.summary_unknown or case.summary_unknown
    case.open_questions = payload.open_questions or case.open_questions
    if payload.sources:
        case.sources = payload.sources
    if payload.conflicts:
        case.conflicts = payload.conflicts
    if payload.techniques:
        case.techniques = payload.techniques[:5]
    case.stage = "VERIFYING"
    stored = store.save(case)
    _finish_later(case_id)
    return stored


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
    case = _apply_report(case, grounded, finalize=False)
    store.add_event(case_id, "Conclusion updated · technique report stored")
    case = store.get(case_id)
    return store.save(_apply_report(case, grounded, finalize=False))


def _catalog_lookup(query: str, case_id: str | None) -> dict:
    result = search_catalog(query)
    if case_id:
        _case_or_404(case_id)
        store.add_event(case_id, f"Catalog lookup · {query or 'catalog'}")
    return result


@app.get("/catalog/search")
def catalog_search(q: str = "", case_id: str | None = None) -> dict:
    return _catalog_lookup(q, case_id)


@app.post("/catalog/search")
def catalog_search_post(payload: CatalogIn) -> dict:
    return _catalog_lookup(payload.query, payload.case_id)


@app.post("/checks/run")
def checks_run(payload: CheckRequest) -> dict:
    case = _case_or_404(payload.case_id) if payload.case_id else None
    techniques = case.techniques if case else []
    dish = (case.dish if case else "") or payload.dish
    retrievals = case.retrievals if case else []
    result = run_checks(retrievals, techniques=techniques, dish=dish or payload.query)
    if payload.case_id:
        case = _case_or_404(payload.case_id)
        case.checks = result["observations"]
        case.scope_label = result["scope"]
        if result["techniques"] and not case.techniques:
            case.techniques = [Technique.model_validate(item) for item in result["techniques"]]
        if case.stage not in {"FAILED", "COMPLETE", "PARTIAL"}:
            case.stage = "MAPPING"
        store.save(case)
        store.add_event(payload.case_id, f"Checked {result['file_count']} retrieved pages")
    return result


def _keep_finished(case: Case) -> Case:
    latest = store.get(case.id)
    if latest.stage in {"COMPLETE", "PARTIAL", "FAILED"} and (latest.findings or latest.summary_known or latest.error):
        known = {item.url for item in latest.retrievals}
        for item in case.retrievals:
            if item.url not in known:
                latest.retrievals.append(item)
        latest.retrieved_urls = list(dict.fromkeys([*latest.retrieved_urls, *case.retrieved_urls]))
        return latest
    case.events = latest.events
    case.dish = latest.dish
    return case


def _finish_later(case_id: str) -> None:
    def run() -> None:
        time.sleep(20)
        try:
            current = store.get(case_id)
        except KeyError:
            return
        if current.findings and current.stage in {"COMPLETE", "PARTIAL", "FAILED"}:
            return
        if not current.retrievals and not current.retrieved_urls:
            return
        try:
            compose_case(case_id)
        except HTTPException:
            return

    threading.Thread(target=run, daemon=True).start()


@app.post("/tools/tavily/search")
def tool_search(payload: SearchIn) -> dict:
    case = _case_or_404(payload.case_id)
    result = tavily_search(payload.query, payload.depth)
    for item in result["results"]:
        remember_retrieval(case, item["url"], item["title"], item["content"])
    case = _keep_finished(case)
    if case.stage not in {"COMPLETE", "PARTIAL", "FAILED"}:
        case.stage = "RESEARCHING"
    store.save(case)
    store.add_event(payload.case_id, f"Tavily search · {payload.query[:80]}")
    _finish_later(payload.case_id)
    return result


@app.post("/tools/tavily/extract")
def tool_extract(payload: ExtractIn) -> dict:
    case = _case_or_404(payload.case_id)
    result = tavily_extract(payload.urls)
    for item in result["results"]:
        remember_retrieval(case, item["url"], passage=item["content"])
    case = _keep_finished(case)
    store.save(case)
    store.add_event(payload.case_id, f"Extracted {len(result['results'])} pages")
    _finish_later(payload.case_id)
    return result


@app.post("/cases/{case_id}/simulate", response_model=Case)
def simulate(case_id: str, payload: SimulateIn) -> Case:
    case = _case_or_404(case_id)
    try:
        simulation = simulate_change(case, payload.change)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    store.add_event(case_id, f"Experiment · {simulation.technique}")
    case = store.get(case_id)
    case.simulation = simulation
    case.experiment_prompt = payload.change.strip()
    return store.save(case)
