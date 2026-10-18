from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Status(str, Enum):
    OBSERVED = "OBSERVED"
    REPORTED = "REPORTED"
    INFERRED = "INFERRED"
    CONTRADICTED = "CONTRADICTED"
    UNKNOWN = "UNKNOWN"
    NOT_OBSERVED = "NOT OBSERVED"


SourceType = Literal["Primary", "Independent", "Documentation", "Code", "Unverified"]
Stage = Literal[
    "QUEUED",
    "RESEARCHING",
    "VERIFYING",
    "MAPPING",
    "COMPLETE",
    "PARTIAL",
    "FAILED",
]


class Source(BaseModel):
    ref: str
    title: str
    url: str | None = None
    source_type: SourceType
    published: str | None = None
    retrieved: str | None = None
    passage: str | None = None
    repository: str | None = None
    path: str | None = None
    line_start: int | None = None
    line_end: int | None = None


class TimelineEvent(BaseModel):
    id: str
    title: str
    summary: str
    occurred: str = "Date unknown"
    disclosed: str = "Date unknown"
    status: Status
    source_refs: list[str] = Field(default_factory=list)


class Finding(BaseModel):
    id: str
    prerequisite: str
    observation: str
    why_it_matters: str
    limitations: str
    next_check: str
    status: Status
    scope: str = ""
    evidence_refs: list[str] = Field(default_factory=list)
    atlas_ids: list[str] = Field(default_factory=list)
    mitigation_ids: list[str] = Field(default_factory=list)
    gap: bool = False

    @model_validator(mode="after")
    def not_observed_names_scope(self) -> Finding:
        if self.status == Status.NOT_OBSERVED and not self.scope.strip():
            raise ValueError("NOT OBSERVED requires an inspected scope")
        return self


class ResearchEvent(BaseModel):
    at: str
    summary: str


class Simulation(BaseModel):
    label: Literal["SIMULATION"] = "SIMULATION"
    condition: str
    before: str
    after: str
    before_status: Status
    after_status: Status
    limits: str


class ReportIn(BaseModel):
    summary_known: str = ""
    summary_unknown: str = ""
    open_questions: list[str] = Field(default_factory=list)
    recommendation: str | None = None
    recommendation_limits: str | None = None
    sources: list[Source] = Field(default_factory=list)
    timeline: list[TimelineEvent] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)


class Case(BaseModel):
    id: str
    stamp: str
    incident: str
    target: str
    sample: bool = False
    stage: Stage = "QUEUED"
    created_at: str
    updated_at: str
    scope_label: str = ""
    events: list[ResearchEvent] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    timeline: list[TimelineEvent] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    summary_known: str = ""
    summary_unknown: str = ""
    open_questions: list[str] = Field(default_factory=list)
    recommendation: str | None = None
    recommendation_limits: str | None = None
    simulation: Simulation | None = None
    error: str | None = None
    retrieved_urls: list[str] = Field(default_factory=list)
    checks: list[dict] = Field(default_factory=list)


class CreateCase(BaseModel):
    incident: str
    target: str
    sample: bool = False


class CheckRequest(BaseModel):
    case_id: str | None = None
    target: str
    include_docs: bool = False
