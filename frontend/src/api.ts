import type { Case } from "./types";

const ACTIVE = new Set(["QUEUED", "RESEARCHING", "VERIFYING", "MAPPING"]);

export function isActive(stage: Case["stage"]): boolean {
  return ACTIVE.has(stage);
}

export async function listCases(): Promise<Case[]> {
  const response = await fetch("/api/cases");
  if (!response.ok) throw new Error("The case list is unavailable.");
  return response.json();
}

export async function getCase(id: string): Promise<Case> {
  const response = await fetch(`/api/cases/${id}`);
  if (!response.ok) throw new Error("This case was not found.");
  return response.json();
}

export async function startCase(incident: string, target: string, sample: boolean): Promise<string> {
  const response = await fetch("/hooks/webhook/breachmirror", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ incident, target, sample }),
  });
  if (!response.ok) throw new Error("The investigation did not start. The research workflow is unavailable.");
  const body = await response.json();
  if (!body.id) throw new Error("The investigation did not start. The research workflow is unavailable.");
  return body.id as string;
}

export async function recheck(id: string): Promise<Case> {
  const response = await fetch(`/api/cases/${id}/recheck`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ check: "unpinned_pretrained" }),
  });
  if (!response.ok) throw new Error("The re-check did not complete.");
  return response.json();
}

export function clock(iso: string): string {
  const match = iso.match(/T(\d{2}:\d{2}:\d{2})/);
  return match ? `${match[1]} UTC` : iso;
}

export function dayStamp(iso: string): string {
  const [date] = iso.split("T");
  if (!date) return "DATE UNKNOWN";
  const [year, month, day] = date.split("-");
  const months = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"];
  return `${day} ${months[Number(month) - 1] || month} ${year}`;
}
