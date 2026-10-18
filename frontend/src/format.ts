import type { Conflict, Finding, HistoryItem, RecipeStep, Source, Status } from "./types";

const GROUPS = ["Today", "Yesterday", "Previous 7 days", "Older"] as const;

export type HistoryGroup = { label: (typeof GROUPS)[number]; items: HistoryItem[] };

export function historyTitle(item: { prompt?: string; question: string; dish: string }): string {
  const prompt = item.prompt?.trim().replace(/\s+/g, " ");
  if (prompt) return prompt;
  return item.question?.trim() || item.dish?.trim() || "Question";
}

export function userQuestion(item: { prompt?: string; question: string; dish: string }): string {
  const prompt = item.prompt?.trim();
  if (prompt) return prompt;
  return item.question?.trim() || item.dish?.trim() || "this question";
}

export function groupHistory(items: HistoryItem[], now = new Date()): HistoryGroup[] {
  const buckets = new Map<string, HistoryItem[]>();
  for (const item of items) {
    const label = groupLabel(item.updated_at || item.created_at, now);
    const list = buckets.get(label) ?? [];
    list.push(item);
    buckets.set(label, list);
  }
  return GROUPS.filter((label) => buckets.has(label)).map((label) => ({
    label,
    items: buckets.get(label) ?? [],
  }));
}

export function rowStamp(iso: string, label: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  if (label === "Today" || label === "Yesterday") {
    return new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit" }).format(date);
  }
  return new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short" }).format(date);
}

export function compactScope(scope: string): string {
  const trimmed = scope.trim();
  const files = trimmed.split(",").map((part) => part.trim()).filter(Boolean);
  if (files.length <= 2 && trimmed.length <= 96) return trimmed;
  const preview = files.slice(0, 2).join(", ");
  return `${files.length} retrieved sources, including ${preview}`;
}

export function plainName(name: string): string {
  const text = name.trim();
  if (!text) return text;
  if (text.length > 1 && /[A-Z]/.test(text[0]) && /[A-Z]/.test(text[1])) return text;
  return text[0].toLowerCase() + text.slice(1);
}

export function joinAnd(names: string[]): string {
  if (names.length <= 1) return names[0] || "";
  if (names.length === 2) return `${names[0]} and ${names[1]}`;
  return `${names.slice(0, -1).join(", ")}, and ${names[names.length - 1]}`;
}

export function endSentence(text: string): string {
  const body = text.trim();
  if (!body) return "";
  return /[.!?]$/.test(body) ? body : `${body}.`;
}

export function findingSentence(finding: Finding): string {
  const name = finding.technique.trim();
  const why = finding.why_it_matters.trim() || finding.purpose.trim();
  if (finding.status === "NOT OBSERVED") {
    let body = `${name} was not in the pages we read`;
    if (finding.scope.trim()) body = `${body} (${compactScope(finding.scope)})`;
    return endSentence(body);
  }
  if (why) return endSentence(`${name} matters because ${plainName(why)}`);
  const observation = finding.observation.trim();
  return endSentence(observation ? `${name}. ${observation}` : name);
}

export function evidenceSentence(finding: Finding): string {
  let text = finding.observation.trim();
  text = text.replace(/^[\w][\w '’/-]+ (?:shows up|is mentioned) in /i, "Found in ");
  text = text.replace(/^Retrieved pages mention /i, "Found in ");
  if (finding.status === "NOT OBSERVED" && !/not found/i.test(text)) {
    return "Not found in the pages we read.";
  }
  if (finding.status === "UNKNOWN" && !text) {
    return "The pages we read do not settle this.";
  }
  return endSentence(text);
}

const CANNED_UNKNOWN = "Named techniques that were not established in the retrieved pages remain open.";
const OLD_UNKNOWN = "Recipes still disagree about which of these steps are necessary.";

const STATUS_MEANING: Record<Status, string> = {
  OBSERVED: "it appeared in the pages we read",
  REPORTED: "a published test reported this",
  INFERRED: "we inferred this; it was not cooked",
  CONTRADICTED: "the pages disagree",
  UNKNOWN: "the pages do not settle this",
  "NOT OBSERVED": "it was not in these pages — that does not mean it fails",
};

const STATUS_ORDER: Status[] = ["OBSERVED", "REPORTED", "INFERRED", "CONTRADICTED", "UNKNOWN", "NOT OBSERVED"];

export function statusMeaning(status: Status): string {
  return STATUS_MEANING[status] || "";
}

export function statusLegend(findings: Finding[]): string {
  const seen = new Set(findings.map((finding) => finding.status));
  const parts = STATUS_ORDER.filter((status) => seen.has(status)).map((status) => `${status} means ${statusMeaning(status)}`);
  return parts.map(endSentence).join(" ");
}

export function tableNote(findings: Finding[]): string {
  const legend = statusLegend(findings);
  return legend
    ? `These rows describe the pages we read, not your kitchen. ${legend}`
    : "These rows describe the pages we read, not your kitchen.";
}

export function knownParagraph(summary: string, findings: Finding[]): string {
  const text = summary.trim();
  if (!text) return "";
  if (/^Retrieved pages mention /i.test(text) || /^The retrieved pages name /i.test(text)) {
    const observed = findings.filter((finding) => finding.status === "OBSERVED").map((finding) => plainName(finding.technique));
    if (observed.length) return `The pages we read use ${joinAnd(observed)}.`;
  }
  return text;
}

export function unknownParagraph(summary: string, findings: Finding[]): string {
  const text = summary.trim();
  const missing = findings.filter((finding) => finding.status === "UNKNOWN" || finding.status === "NOT OBSERVED");
  if (text === CANNED_UNKNOWN || text === OLD_UNKNOWN || !text) {
    if (missing.length) {
      return `We did not find ${joinAnd(missing.map((finding) => plainName(finding.technique)))} in those pages. That does not mean those steps fail.`;
    }
    if (!text) return "";
    return "Recipes still disagree about whether you need every one of those steps.";
  }
  return text;
}

export function limitsSentence(text: string): string {
  return text.replace(/\bthe user's kitchen\b/g, "your kitchen");
}

export function conflictBody(conflict: Conflict): string {
  const camps = conflictCamps(conflict);
  if (camps.length >= 2) return camps.map(endSentence).join(" ");
  return endSentence(conflict.summary);
}

export function uniqueConflictSources(conflicts: Conflict[]): boolean {
  if (conflicts.length < 2) return true;
  const keys = conflicts.map((conflict) => [...conflict.source_refs].sort().join("|"));
  return new Set(keys).size > 1;
}

export function recipeNotes(notes: string): string {
  if (notes.includes("culinary catalog")) {
    return "This method follows the retrieved pages. It was not cooked.";
  }
  return notes;
}

export function recipeTitle(title: string, dish = ""): string {
  const stripped = title.replace(/^An evidence-backed method for\s+/i, "").trim();
  const text = stripped || dish.trim();
  if (!text) return "Method";
  return text.slice(0, 1).toUpperCase() + text.slice(1);
}

const COOK_ORDER: Record<string, number> = {
  "baking-soda": 10,
  parboiling: 20,
  roughening: 30,
  drying: 40,
  "high-heat": 50,
  "salt-ahead": 10,
  "oil-in-water": 10,
  "short-ferment": 10,
  "long-ferment": 20,
  "egg-replacer": 10,
};

export function orderedSteps(steps: RecipeStep[]): RecipeStep[] {
  return steps
    .map((step, index) => ({ step, index }))
    .sort((a, b) => {
      const left = a.step.step_order || COOK_ORDER[a.step.technique_id || ""] || 1000 + a.index;
      const right = b.step.step_order || COOK_ORDER[b.step.technique_id || ""] || 1000 + b.index;
      return left - right || a.index - b.index;
    })
    .map(({ step }) => step);
}

export function conflictCamps(conflict: Conflict): string[] {
  const given = conflict.positions.map((item) => item.trim()).filter(Boolean);
  if (given.length > 0) return given;
  const parts = conflict.summary
    .split(/;\s+/)
    .map((part) => part.trim().replace(/[.]+$/g, ""))
    .filter(Boolean);
  if (parts.length < 2) return [];
  return parts.slice(0, 2).map((part) => (part.toLowerCase().startsWith("others ") ? `Others ${part.slice(7)}` : part));
}

export function sourceLabel(source: Source): string {
  const title = source.title.replace(/\s+/g, " ").trim();
  const cut = title.split(/\s+[|–—]\s+/)[0]?.trim() || title;
  return cut || "Source";
}

export function readablePassage(text: string): string {
  return text
    .replace(/skip to (?:main )?content/gi, " ")
    .replace(/\s+/g, " ")
    .trim();
}

export function sourceDates(source: Source): string | null {
  const bits = [];
  if (source.published) bits.push(`Published ${source.published}`);
  if (source.retrieved) bits.push(`Retrieved ${source.retrieved}`);
  if (!bits.length) return null;
  return `${bits.join(". ")}.`;
}

export function activityLine(events: { summary: string }[]): string {
  const unique: string[] = [];
  for (const event of events) {
    const summary = humanizeEvent(event.summary.trim());
    if (summary && !unique.includes(summary)) unique.push(summary);
  }
  return unique.slice(-3).join(" · ");
}

function humanizeEvent(summary: string): string {
  if (summary.startsWith("Tavily search · ")) return `Searched ${summary.slice("Tavily search · ".length)}`;
  if (summary.startsWith("Extracted ")) return summary.replace("Extracted", "Read");
  if (summary === "Recipe section stored") return "Saved recipe notes";
  if (summary.startsWith("Catalog lookup")) return "Checked the technique catalog";
  if (summary.startsWith("Checked ")) return summary.replace("Checked", "Reviewed");
  if (summary.startsWith("Report stored")) return "Wrote the report";
  if (summary.startsWith("Conclusion updated")) return "Updated the report";
  return summary;
}

export function readCaseId(): string | null {
  const match = window.location.hash.match(/^#\/c\/([^/?#]+)$/);
  if (!match) return null;
  try {
    return decodeURIComponent(match[1]);
  } catch {
    return match[1];
  }
}

export function looksLikeExperiment(message: string): boolean {
  return /\b(what if|skip |omit |without |instead of |replace )\b/i.test(message);
}

export function suggestedExperiment(item: { findings?: Finding[]; techniques?: { name: string }[] }): string {
  const named = item.techniques?.[0]?.name || item.findings?.[0]?.technique;
  return named ? `What if I skip ${named.toLowerCase()}?` : "What if I skip that step?";
}

function groupLabel(iso: string, now: Date): (typeof GROUPS)[number] {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "Older";
  const startToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const start = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  const days = (startToday.getTime() - start.getTime()) / 86_400_000;
  if (days < 1) return "Today";
  if (days < 2) return "Yesterday";
  if (days < 7) return "Previous 7 days";
  return "Older";
}
