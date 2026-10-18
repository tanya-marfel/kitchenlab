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


SourceType = Literal["Recipe", "Science", "Independent", "Unverified"]
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


class Conflict(BaseModel):
    id: str
    topic: str
    summary: str
    positions: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    status: Status = Status.CONTRADICTED


class Finding(BaseModel):
    id: str
    technique: str
    purpose: str
    observation: str
    why_it_matters: str
    limitations: str
    next_check: str
    status: Status
    scope: str = ""
    evidence_refs: list[str] = Field(default_factory=list)
    gap: bool = False

    @model_validator(mode="after")
    def not_observed_names_scope(self) -> Finding:
        if self.status == Status.NOT_OBSERVED and not self.scope.strip():
            raise ValueError("NOT OBSERVED requires an inspected scope")
        return self


class ResearchEvent(BaseModel):
    at: str
    summary: str


class Retrieval(BaseModel):
    url: str
    title: str = ""
    passage: str = ""


class RecipeStep(BaseModel):
    id: str
    instruction: str
    why: str = ""
    technique_id: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)


class Recipe(BaseModel):
    title: str = ""
    servings: str = ""
    steps: list[RecipeStep] = Field(default_factory=list)
    notes: str = ""


class Simulation(BaseModel):
    label: Literal["EXPERIMENT"] = "EXPERIMENT"
    change: str
    technique: str
    supported: str
    predicted: str
    supported_status: Status
    predicted_status: Status
    limits: str


class Technique(BaseModel):
    id: str
    name: str
    purpose: str = ""
    mechanism: str = ""
    terms: list[str] = Field(default_factory=list)


class ReportIn(BaseModel):
    summary_known: str = ""
    summary_unknown: str = ""
    open_questions: list[str] = Field(default_factory=list)
    recommendation: str | None = None
    recommendation_limits: str | None = None
    sources: list[Source] = Field(default_factory=list)
    conflicts: list[Conflict] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    techniques: list[Technique] = Field(default_factory=list)
    recipe: Recipe | None = None


class HistoryItem(BaseModel):
    id: str
    prompt: str = ""
    question: str
    dish: str
    sample: bool = False
    stage: Stage = "QUEUED"
    created_at: str
    updated_at: str


class Case(BaseModel):
    id: str
    stamp: str
    question: str
    dish: str
    prompt: str = ""
    sample: bool = False
    stage: Stage = "QUEUED"
    created_at: str
    updated_at: str
    scope_label: str = ""
    events: list[ResearchEvent] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    conflicts: list[Conflict] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    techniques: list[Technique] = Field(default_factory=list)
    recipe: Recipe | None = None
    summary_known: str = ""
    summary_unknown: str = ""
    open_questions: list[str] = Field(default_factory=list)
    recommendation: str | None = None
    recommendation_limits: str | None = None
    simulation: Simulation | None = None
    experiment_prompt: str = ""
    error: str | None = None
    retrieved_urls: list[str] = Field(default_factory=list)
    retrievals: list[Retrieval] = Field(default_factory=list)
    checks: list[dict] = Field(default_factory=list)


class CreateCase(BaseModel):
    question: str
    dish: str = ""
    sample: bool = False
    prompt: str = ""


class CheckRequest(BaseModel):
    case_id: str | None = None
    dish: str = ""
    query: str = ""
