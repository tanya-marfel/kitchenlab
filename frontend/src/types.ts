export type Status =
  | "OBSERVED"
  | "REPORTED"
  | "INFERRED"
  | "CONTRADICTED"
  | "UNKNOWN"
  | "NOT OBSERVED";

export type Stage =
  | "QUEUED"
  | "RESEARCHING"
  | "VERIFYING"
  | "MAPPING"
  | "COMPLETE"
  | "PARTIAL"
  | "FAILED";

export type Source = {
  ref: string;
  title: string;
  url: string | null;
  source_type: "Primary" | "Independent" | "Documentation" | "Code" | "Unverified";
  published: string | null;
  retrieved: string | null;
  passage: string | null;
  repository: string | null;
  path: string | null;
  line_start: number | null;
  line_end: number | null;
};

export type TimelineEvent = {
  id: string;
  title: string;
  summary: string;
  occurred: string;
  disclosed: string;
  status: Status;
  source_refs: string[];
};

export type Finding = {
  id: string;
  prerequisite: string;
  observation: string;
  why_it_matters: string;
  limitations: string;
  next_check: string;
  status: Status;
  scope: string;
  evidence_refs: string[];
  atlas_ids: string[];
  mitigation_ids: string[];
  gap: boolean;
};

export type ResearchEvent = { at: string; summary: string };

export type Simulation = {
  label: "SIMULATION";
  condition: string;
  before: string;
  after: string;
  before_status: Status;
  after_status: Status;
  limits: string;
};

export type Case = {
  id: string;
  stamp: string;
  incident: string;
  target: string;
  sample: boolean;
  stage: Stage;
  created_at: string;
  updated_at: string;
  scope_label: string;
  events: ResearchEvent[];
  sources: Source[];
  timeline: TimelineEvent[];
  findings: Finding[];
  summary_known: string;
  summary_unknown: string;
  open_questions: string[];
  recommendation: string | null;
  recommendation_limits: string | null;
  simulation: Simulation | null;
  error: string | null;
};

export type View = "cases" | "investigation" | "exposure" | "sources";

export const SAMPLE_INCIDENT =
  "July 2026 OpenAI–Hugging Face intrusion. https://huggingface.co/blog/security-incident-july-2026 and https://openai.com/index/hugging-face-incident-and-the-road-ahead/";

export const SAMPLE_TARGET = "demo-target/before";
