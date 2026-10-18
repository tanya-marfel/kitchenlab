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
  source_type: "Recipe" | "Science" | "Independent" | "Unverified";
  published: string | null;
  retrieved: string | null;
  passage: string | null;
};

export type Conflict = {
  id: string;
  topic: string;
  summary: string;
  positions: string[];
  source_refs: string[];
  status: Status;
};

export type Finding = {
  id: string;
  technique: string;
  purpose: string;
  observation: string;
  why_it_matters: string;
  limitations: string;
  next_check: string;
  status: Status;
  scope: string;
  evidence_refs: string[];
  gap: boolean;
};

export type RecipeStep = {
  id: string;
  instruction: string;
  why: string;
  technique_id: string | null;
  evidence_refs: string[];
  step_order?: number;
};

export type Recipe = {
  title: string;
  servings: string;
  steps: RecipeStep[];
  notes: string;
};

export type ResearchEvent = { at: string; summary: string };

export type Simulation = {
  label: "EXPERIMENT";
  change: string;
  technique: string;
  supported: string;
  predicted: string;
  supported_status: Status;
  predicted_status: Status;
  limits: string;
};

export type Technique = {
  id: string;
  name: string;
  purpose: string;
  mechanism: string;
  terms: string[];
};

export type HistoryItem = {
  id: string;
  prompt: string;
  question: string;
  dish: string;
  sample: boolean;
  stage: Stage;
  created_at: string;
  updated_at: string;
};

export type Case = {
  id: string;
  stamp: string;
  question: string;
  dish: string;
  prompt?: string;
  sample: boolean;
  stage: Stage;
  created_at: string;
  updated_at: string;
  scope_label: string;
  events: ResearchEvent[];
  sources: Source[];
  conflicts: Conflict[];
  findings: Finding[];
  techniques: Technique[];
  recipe: Recipe | null;
  summary_known: string;
  summary_unknown: string;
  open_questions: string[];
  recommendation: string | null;
  recommendation_limits: string | null;
  simulation: Simulation | null;
  experiment_prompt: string;
  error: string | null;
};
