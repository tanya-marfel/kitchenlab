from __future__ import annotations

import re

from breachmirror.schema import Finding, ReportIn, Source, Status

BLOCKED_RE = re.compile(
    r"(?i)\b(proof[- ]of[- ]concept|shellcode|metasploit|reverse shell|base64 payload)\b"
)
SECURE_RE = re.compile(r"(?i)\b(application is now secure|all systems secure|you are safe)\b")
INCIDENT_TYPES = {"Primary", "Independent"}
TARGET_TYPES = {"Documentation", "Code"}


def _normalize_url(url: str | None) -> str:
    if not url:
        return ""
    return url.rstrip("/")


def ground_report(report: ReportIn, retrieved_urls: list[str], checks: list[dict]) -> ReportIn:
    allowed = {_normalize_url(url) for url in retrieved_urls}
    check_by_id = {item["check"]: item for item in checks}
    conditioned = {
        "exposed-credentials": "exposed_token_literal",
        "untrusted-load": "unpinned_pretrained",
        "agent-tools": "write_or_network_tool",
        "authorization": "authorization_step",
        "isolation": "isolation",
    }

    for source in report.sources:
        blob = " ".join(filter(None, [source.title, source.passage, source.url]))
        if BLOCKED_RE.search(blob):
            raise ValueError("Report text includes reproduction detail. Cite the condition instead.")
        if source.source_type == "Primary":
            if not source.url or _normalize_url(source.url) not in allowed:
                source.source_type = "Unverified"
                note = "This URL was not retrieved by Tavily during this case."
                source.passage = f"{source.passage or ''} {note}".strip()

    sources = {source.ref: source for source in report.sources}
    corrected: list[Finding] = []
    for finding in report.findings:
        text = " ".join(
            [
                finding.prerequisite,
                finding.observation,
                finding.why_it_matters,
                finding.limitations,
                finding.next_check,
            ]
        )
        if BLOCKED_RE.search(text) or SECURE_RE.search(text):
            raise ValueError("A finding claims exploit procedure or global safety.")
        if finding.status == Status.NOT_OBSERVED and not finding.scope.strip():
            raise ValueError(f"{finding.id} is NOT OBSERVED without a scope.")
        check_id = conditioned.get(finding.id)
        if check_id and check_id in check_by_id:
            checked = check_by_id[check_id]
            forced = Status(checked["status"])
            if finding.status != forced:
                finding.status = forced
                finding.limitations = (
                    f"{finding.limitations} Status was corrected to the deterministic check result."
                ).strip()
            if forced == Status.NOT_OBSERVED and not finding.scope.strip():
                finding.scope = checked.get("scope") or "inspected files"
            if forced != Status.NOT_OBSERVED and not finding.scope.strip():
                finding.scope = checked.get("scope") or ""
        if finding.status == Status.NOT_OBSERVED and not finding.scope.strip():
            raise ValueError(f"{finding.id} is NOT OBSERVED without a scope.")
        _require_evidence(finding, sources)
        corrected.append(finding)

    report.findings = corrected
    if report.recommendation and not report.recommendation_limits:
        report.recommendation_limits = "This does not establish that the application is secure."
    elif report.recommendation_limits and "does not establish that the application is secure" not in report.recommendation_limits:
        report.recommendation_limits = (
            f"{report.recommendation_limits} This does not establish that the application is secure."
        )
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
    if not (kinds & INCIDENT_TYPES) or not (kinds & TARGET_TYPES):
        raise ValueError(f"{finding.id} needs both an incident source and a target source.")
