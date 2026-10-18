import type { Case, HistoryItem } from "./types";

const ACTIVE = new Set(["QUEUED", "RESEARCHING", "VERIFYING", "MAPPING"]);

export function isActive(stage: Case["stage"]): boolean {
  return ACTIVE.has(stage);
}

export function awaitingReport(item: {
  stage: Case["stage"];
  findings?: unknown[];
  events?: { summary: string }[];
  error?: string | null;
}): boolean {
  if (item.stage === "FAILED") return false;
  if (item.stage === "PARTIAL" && item.error) return false;
  const composed = (item.events || []).some((event) => event.summary.startsWith("Report stored from retrieved pages"));
  if (composed) return false;
  if (isActive(item.stage)) return true;
  return !(item.findings && item.findings.length);
}

export async function listHistory(): Promise<HistoryItem[]> {
  const response = await fetch("/api/history");
  if (response.ok) {
    const items = (await response.json()) as HistoryItem[];
    return items.sort((a, b) => (b.updated_at || b.created_at).localeCompare(a.updated_at || a.created_at));
  }
  if (response.status !== 404) throw new Error("The question list is unavailable.");
  const legacy = await fetch("/api/cases");
  if (!legacy.ok) throw new Error("The question list is unavailable.");
  const cases = (await legacy.json()) as Case[];
  return cases
    .map((item) => ({
      id: item.id,
      prompt: item.prompt ?? "",
      question: item.question,
      dish: item.dish,
      sample: item.sample,
      stage: item.stage,
      created_at: item.created_at,
      updated_at: item.updated_at,
    }))
    .sort((a, b) => (b.updated_at || b.created_at).localeCompare(a.updated_at || a.created_at));
}

export async function getCase(id: string): Promise<Case> {
  const response = await fetch(`/api/cases/${id}`);
  if (!response.ok) throw new Error("This question was not found.");
  return response.json();
}

export async function interpretMessage(message: string): Promise<{ question: string; dish: string }> {
  const response = await fetch("/api/interpret", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || "The message could not be interpreted.");
  }
  return response.json();
}

export async function startCase(question: string, dish: string, sample: boolean, prompt = ""): Promise<string> {
  const response = await fetch("/hooks/webhook/kitchenlab", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, dish, sample, prompt }),
  });
  if (!response.ok) throw new Error("The investigation did not start. The research workflow is unavailable.");
  const body = await response.json();
  if (!body.id) throw new Error("The investigation did not start. The research workflow is unavailable.");
  return body.id as string;
}

export async function savePrompt(id: string, prompt: string): Promise<void> {
  const response = await fetch(`/api/cases/${id}/prompt`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt }),
  });
  if (!response.ok) throw new Error("The question could not be saved.");
}

export async function deleteCase(id: string): Promise<void> {
  const response = await fetch(`/api/cases/${id}`, { method: "DELETE" });
  if (!response.ok) throw new Error("The question could not be deleted.");
}

export async function simulate(id: string, change: string): Promise<Case> {
  const response = await fetch(`/api/cases/${id}/simulate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ change }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || "The experiment did not complete.");
  }
  return response.json();
}
