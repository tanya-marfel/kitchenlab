from __future__ import annotations

import re

from kitchenlab.schema import Finding, ReportIn, Source, Status

GUARANTEE_RE = re.compile(
    r"(?i)\b(proven in your kitchen|guaranteed crispy|always works|the best recipe is proven)\b"
)
RECIPE_TYPES = {"Recipe"}
SCIENCE_TYPES = {"Science"}


def _normalize_url(url: str | None) -> str:
    if not url:
        return ""
    return url.rstrip("/")


def ground_report(report: ReportIn, retrieved_urls: list[str], checks: list[dict]) -> ReportIn:
    allowed = {_normalize_url(url) for url in retrieved_urls}
    check_by_id = {item["check"]: item for item in checks}

    for source in report.sources:
        blob = " ".join(filter(None, [source.title, source.passage, source.url]))
        if GUARANTEE_RE.search(blob):
            raise ValueError("Report text claims a kitchen-proven result. Cite the retrieved test instead.")
        if source.source_type in {"Recipe", "Science"}:
            if not source.url or _normalize_url(source.url) not in allowed:
                source.source_type = "Unverified"
                note = "This URL was not retrieved by Tavily during this case."
                source.passage = f"{source.passage or ''} {note}".strip()

    sources = {source.ref: source for source in report.sources}
    corrected: list[Finding] = []
    for finding in report.findings:
        text = " ".join(
            [
                finding.technique,
                finding.purpose,
                finding.observation,
                finding.why_it_matters,
                finding.limitations,
                finding.next_check,
            ]
        )
        if GUARANTEE_RE.search(text):
            raise ValueError("A finding claims a kitchen-proven result.")
        if finding.status == Status.NOT_OBSERVED and not finding.scope.strip():
            raise ValueError(f"{finding.id} is NOT OBSERVED without a scope.")
        if finding.id in check_by_id:
            checked = check_by_id[finding.id]
            forced = Status(checked["status"])
            if finding.status != forced:
                finding.status = forced
                finding.limitations = (
                    f"{finding.limitations} Status was corrected to the deterministic check result."
                ).strip()
            if not finding.scope.strip():
                finding.scope = checked.get("scope") or ""
        if finding.status == Status.NOT_OBSERVED and not finding.scope.strip():
            raise ValueError(f"{finding.id} is NOT OBSERVED without a scope.")
        _require_evidence(finding, sources)
        corrected.append(finding)

    report.findings = corrected
    limit = "This was not cooked and does not test the user's kitchen."
    if report.recommendation and not report.recommendation_limits:
        report.recommendation_limits = limit
    elif report.recommendation_limits and "does not test the user's kitchen" not in report.recommendation_limits:
        report.recommendation_limits = f"{report.recommendation_limits} {limit}"
    return report


def _require_evidence(finding: Finding, sources: dict[str, Source]) -> None:
    if not finding.evidence_refs:
        raise ValueError(f"{finding.id} has no evidence refs.")
    missing = [ref for ref in finding.evidence_refs if ref not in sources]
    if missing:
        raise ValueError(f"{finding.id} cites unknown sources: {', '.join(missing)}")
    kinds = {sources[ref].source_type for ref in finding.evidence_refs}
    if finding.gap or finding.status == Status.UNKNOWN:
        return
    if not (kinds & RECIPE_TYPES) or not (kinds & SCIENCE_TYPES):
        raise ValueError(f"{finding.id} needs both a recipe source and a science source.")
