import type { Finding, ResearchEvent, Source, Status, TimelineEvent as TimelineItem } from "./types";
import { clock } from "./api";

const STATUS_CLASS: Record<Status, string> = {
  OBSERVED: "status-observed",
  REPORTED: "status-reported",
  INFERRED: "status-inferred",
  CONTRADICTED: "status-contradicted",
  UNKNOWN: "status-unknown",
  "NOT OBSERVED": "status-not-observed",
};

export function SectionLabel({ children }: { children: string }) {
  return <p className="section-label">{children}</p>;
}

export function StatusMark({ status }: { status: Status }) {
  return (
    <span className={`status ${STATUS_CLASS[status]}`}>
      <i aria-hidden="true" />
      {status}
    </span>
  );
}

export function EvidenceBadge({
  sourceRef,
  pressed,
  onSelect,
}: {
  sourceRef: string;
  pressed: boolean;
  onSelect: (ref: string) => void;
}) {
  return (
    <button className="badge" aria-pressed={pressed} onClick={() => onSelect(sourceRef)}>
      [REF {sourceRef}]
    </button>
  );
}

export function CaseHeader({
  stamp,
  title,
  scope,
  updated,
}: {
  stamp: string;
  title: string;
  scope: string;
  updated: string;
}) {
  return (
    <header className="case-header">
      <div>
        <div className="stamps">
          <span>{stamp}</span>
          <span>{scope}</span>
          <span>LAST CHECKED / {updated}</span>
        </div>
        <h1>{title}</h1>
      </div>
    </header>
  );
}

export function TimelineEvent({
  event,
  pressed,
  onSelect,
  selectedRef,
  onSelectRef,
}: {
  event: TimelineItem;
  pressed: boolean;
  onSelect: () => void;
  selectedRef: string | null;
  onSelectRef: (ref: string) => void;
}) {
  return (
    <li>
      <button className="timeline-event" aria-pressed={pressed} onClick={onSelect}>
        <time dateTime={event.occurred}>Occurred {event.occurred}</time>
        <i aria-hidden="true" />
        <span>
          <strong>{event.title}</strong>
          <span>{event.summary}</span>
          <span className="note">Disclosed {event.disclosed}</span>
          <StatusMark status={event.status} />
        </span>
      </button>
      <div className="refs">
        {event.source_refs.map((ref) => (
          <EvidenceBadge key={ref} sourceRef={ref} pressed={selectedRef === ref} onSelect={onSelectRef} />
        ))}
      </div>
    </li>
  );
}

export function ClaimRow({ finding, onSelect }: { finding: Finding; onSelect: () => void }) {
  return (
    <tr aria-selected={false} onClick={onSelect}>
      <td>
        <button className="text-button" onClick={onSelect}>
          {finding.prerequisite}
        </button>
        <span className="scope">{finding.atlas_ids.join(" · ")}</span>
      </td>
      <td>
        {finding.observation}
        {finding.status === "NOT OBSERVED" ? <span className="scope">Scope: {finding.scope}</span> : null}
      </td>
      <td>
        <StatusMark status={finding.status} />
      </td>
    </tr>
  );
}

export function PrerequisiteRow({ finding, onSelect }: { finding: Finding; onSelect: () => void }) {
  return <ClaimRow finding={finding} onSelect={onSelect} />;
}

export function ResearchLog({ events }: { events: ResearchEvent[] }) {
  if (events.length === 0) {
    return <p className="note">No recorded tool calls yet.</p>;
  }
  return (
    <ol className="log">
      {events.map((event, index) => (
        <li key={`${event.at}-${index}`}>
          <time dateTime={event.at}>{clock(event.at)}</time>
          <span>{event.summary}</span>
        </li>
      ))}
    </ol>
  );
}

function edgeKind(status: Status): string {
  if (status === "NOT OBSERVED") return "blocked";
  if (status === "INFERRED" || status === "UNKNOWN" || status === "CONTRADICTED") return "dashed";
  return "solid";
}

export function AttackPath({
  findings,
  onSelect,
}: {
  findings: Finding[];
  onSelect: (finding: Finding) => void;
}) {
  const shown = findings.slice(0, 7);
  return (
    <div className="path" aria-label="Conditional attack path">
      <article className="path-node">
        <small>HISTORICAL STEP</small>
        Documented incident
      </article>
      {shown.map((finding) => (
        <span key={finding.id} style={{ display: "contents" }}>
          <span className={`path-edge ${edgeKind(finding.status)}`}>
            {edgeKind(finding.status) === "dashed" ? "IF" : edgeKind(finding.status) === "blocked" ? "BLOCKED" : "LINK"}
          </span>
          <button className="path-node" onClick={() => onSelect(finding)}>
            <small>{finding.status}</small>
            {finding.prerequisite}
          </button>
        </span>
      ))}
    </div>
  );
}

export function SourceInspector({
  source,
  claims,
  onClose,
}: {
  source: Source | null;
  claims: string[];
  onClose: () => void;
}) {
  if (!source) {
    return (
      <aside className="inspector">
        <SectionLabel>EVIDENCE</SectionLabel>
        <p className="note">Select a source badge, timeline event, or finding.</p>
      </aside>
    );
  }
  return (
    <aside className="inspector">
      <SectionLabel>{`EVIDENCE / ${source.ref}`}</SectionLabel>
      <h2>{source.title}</h2>
      <p className="note">{source.source_type}</p>
      <p>Published {source.published || "Date unknown"}</p>
      <p>Retrieved {source.retrieved || "Date unknown"}</p>
      {source.path ? (
        <p className="mono">
          {source.path}
          {source.line_start ? ` lines ${source.line_start}–${source.line_end}` : ""}
        </p>
      ) : null}
      {source.passage ? <blockquote className="mono">{source.passage}</blockquote> : null}
      <SectionLabel>CLAIMS SUPPORTED</SectionLabel>
      {claims.length === 0 ? <p className="note">No linked claim in this case.</p> : claims.map((claim) => <p key={claim}>{claim}</p>)}
      {source.url ? (
        <p>
          <a href={source.url} target="_blank" rel="noreferrer">
            Open original source
          </a>
        </p>
      ) : null}
      <button className="button" onClick={onClose}>
        Close inspector
      </button>
    </aside>
  );
}
