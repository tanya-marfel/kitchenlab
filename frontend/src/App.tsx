import { useEffect, useMemo, useState } from "react";
import { dayStamp, getCase, isActive, listCases, recheck, startCase } from "./api";
import {
  AttackPath,
  CaseHeader,
  EvidenceBadge,
  PrerequisiteRow,
  ResearchLog,
  SectionLabel,
  SourceInspector,
  StatusMark,
  TimelineEvent,
} from "./components";
import { SAMPLE_INCIDENT, SAMPLE_TARGET, type Case, type View } from "./types";

const VIEWS: { id: View; label: string }[] = [
  { id: "cases", label: "Cases" },
  { id: "investigation", label: "Investigation" },
  { id: "exposure", label: "Exposure" },
  { id: "sources", label: "Sources" },
];

export function App() {
  const [view, setView] = useState<View>("cases");
  const [cases, setCases] = useState<Case[]>([]);
  const [current, setCurrent] = useState<Case | null>(null);
  const [incident, setIncident] = useState(SAMPLE_INCIDENT);
  const [target, setTarget] = useState(SAMPLE_TARGET);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [selectedRef, setSelectedRef] = useState<string | null>(null);
  const [sourceFilter, setSourceFilter] = useState("All");

  async function refreshList() {
    setCases(await listCases());
  }

  useEffect(() => {
    refreshList().catch((reason: Error) => setError(reason.message));
  }, []);

  useEffect(() => {
    if (!current || !isActive(current.stage)) return;
    const timer = window.setInterval(() => {
      getCase(current.id)
        .then(setCurrent)
        .catch((reason: Error) => setError(reason.message));
    }, 2000);
    return () => window.clearInterval(timer);
  }, [current?.id, current?.stage]);

  async function openCase(id: string) {
    const next = await getCase(id);
    setCurrent(next);
    setSelectedRef(next.sources[0]?.ref ?? null);
    setView("investigation");
    setError(null);
  }

  async function begin(sample: boolean) {
    setStarting(true);
    setError(null);
    try {
      const id = await startCase(
        sample ? SAMPLE_INCIDENT : incident,
        sample ? SAMPLE_TARGET : target,
        sample,
      );
      await refreshList();
      await openCase(id);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The investigation did not start.");
    } finally {
      setStarting(false);
    }
  }

  const source = current?.sources.find((item) => item.ref === selectedRef) ?? null;
  const claims = useMemo(() => {
    if (!current || !selectedRef) return [];
    return current.findings
      .filter((finding) => finding.evidence_refs.includes(selectedRef))
      .map((finding) => finding.prerequisite);
  }, [current, selectedRef]);

  const filteredSources = (current?.sources ?? []).filter((item) =>
    sourceFilter === "All" ? true : item.source_type === sourceFilter,
  );

  return (
    <div className="app">
      <aside className="rail">
        <div className="wordmark">BREACHMIRROR</div>
        <nav>
          {VIEWS.map((item) => (
            <button key={item.id} aria-current={view === item.id ? "page" : undefined} onClick={() => setView(item.id)}>
              {item.label}
            </button>
          ))}
        </nav>
        <footer>PUBLIC RESEARCH MODE</footer>
      </aside>
      <div className="main">
        <CaseHeader
          stamp={current?.stamp ?? "CASE / —"}
          title={current?.incident ?? "No case open"}
          scope={current ? (current.sample ? "PUBLIC EVIDENCE" : current.scope_label) : "NO CASE"}
          updated={current ? dayStamp(current.updated_at) : "—"}
        />
        <div className={selectedRef && view !== "cases" ? "workspace" : "workspace inspector-closed"}>
          <div className="canvas">
            {error ? <p className="panel">{error}</p> : null}
            {view === "cases" ? (
              <CasesView
                cases={cases}
                incident={incident}
                target={target}
                starting={starting}
                onIncident={setIncident}
                onTarget={setTarget}
                onStart={() => begin(false)}
                onSample={() => begin(true)}
                onOpen={(id) => openCase(id).catch((reason: Error) => setError(reason.message))}
              />
            ) : null}
            {view !== "cases" && !current ? (
              <p>No source-backed events yet. Start an investigation or load the sample case.</p>
            ) : null}
            {view === "investigation" && current ? (
              <Investigation current={current} selectedRef={selectedRef} onSelectRef={setSelectedRef} />
            ) : null}
            {view === "exposure" && current ? (
              <Exposure
                current={current}
                onSelectRef={setSelectedRef}
                onRecheck={() =>
                  recheck(current.id)
                    .then(setCurrent)
                    .catch((reason: Error) => setError(reason.message))
                }
              />
            ) : null}
            {view === "sources" && current ? (
              <Sources
                sources={filteredSources}
                filter={sourceFilter}
                onFilter={setSourceFilter}
                selectedRef={selectedRef}
                onSelectRef={setSelectedRef}
                findings={current.findings}
              />
            ) : null}
          </div>
          {view !== "cases" ? (
            <SourceInspector source={source} claims={claims} onClose={() => setSelectedRef(null)} />
          ) : null}
        </div>
      </div>
    </div>
  );
}

function CasesView({
  cases,
  incident,
  target,
  starting,
  onIncident,
  onTarget,
  onStart,
  onSample,
  onOpen,
}: {
  cases: Case[];
  incident: string;
  target: string;
  starting: boolean;
  onIncident: (value: string) => void;
  onTarget: (value: string) => void;
  onStart: () => void;
  onSample: () => void;
  onOpen: (id: string) => void;
}) {
  return (
    <div className="stack">
      <section className="panel">
        <SectionLabel>NEW CASE</SectionLabel>
        <label className="field">
          <span>INCIDENT</span>
          <input value={incident} onChange={(event) => onIncident(event.target.value)} />
        </label>
        <label className="field">
          <span>TARGET</span>
          <input value={target} onChange={(event) => onTarget(event.target.value)} />
        </label>
        <div className="row-actions">
          <button className="button primary" disabled={starting} onClick={onStart}>
            Start investigation
          </button>
          <button className="button" disabled={starting} onClick={onSample}>
            Load sample case
          </button>
        </div>
        <p className="note">Public sources only. No intrusive testing or credential validation.</p>
      </section>
      <section>
        <SectionLabel>CASES</SectionLabel>
        {cases.length === 0 ? (
          <p>No source-backed events yet. Start an investigation or load the sample case.</p>
        ) : (
          <table className="case-list">
            <thead>
              <tr>
                <th>Case</th>
                <th>Stage</th>
                <th>Target</th>
              </tr>
            </thead>
            <tbody>
              {cases.map((item) => (
                <tr key={item.id}>
                  <td>
                    <button className="link" onClick={() => onOpen(item.id)}>
                      {item.stamp}
                      {item.sample ? " · sample" : ""}
                    </button>
                  </td>
                  <td>{item.stage}</td>
                  <td>{item.target}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}

function Investigation({
  current,
  selectedRef,
  onSelectRef,
}: {
  current: Case;
  selectedRef: string | null;
  onSelectRef: (ref: string) => void;
}) {
  return (
    <div className="stack">
      {current.stage === "PARTIAL" ? (
        <p className="panel">Timeline available. Target permissions could not be verified; exposure assessment is incomplete.</p>
      ) : null}
      {isActive(current.stage) ? <p className="section-label">RESEARCH IN PROGRESS · {current.stage}</p> : null}
      <div className="summary">
        <section className="panel">
          <SectionLabel>KNOWN</SectionLabel>
          <p>{current.summary_known || "No source-backed summary yet."}</p>
        </section>
        <section className="panel">
          <SectionLabel>NOT KNOWN</SectionLabel>
          <p>{current.summary_unknown || "Unknowns appear here after the incident section is stored."}</p>
        </section>
      </div>
      <section>
        <SectionLabel>TIMELINE</SectionLabel>
        {current.timeline.length === 0 ? (
          <p>No source-backed events yet. Start an investigation or load the sample case.</p>
        ) : (
          <ol className="timeline">
            {current.timeline.map((event) => (
              <TimelineEvent
                key={event.id}
                event={event}
                pressed={event.source_refs.includes(selectedRef || "")}
                onSelect={() => onSelectRef(event.source_refs[0] || "")}
                selectedRef={selectedRef}
                onSelectRef={onSelectRef}
              />
            ))}
          </ol>
        )}
      </section>
      <section className="panel">
        <SectionLabel>{`OPEN QUESTIONS / ${String(current.open_questions.length).padStart(2, "0")}`}</SectionLabel>
        {current.open_questions.length === 0 ? <p className="note">None recorded.</p> : current.open_questions.map((item) => <p key={item}>{item}</p>)}
      </section>
      <section className="panel">
        <SectionLabel>RESEARCH LOG</SectionLabel>
        <ResearchLog events={current.events} />
      </section>
    </div>
  );
}

function Exposure({ current, onSelectRef, onRecheck }: { current: Case; onSelectRef: (ref: string) => void; onRecheck: () => void }) {
  return (
    <div className="stack">
      <SectionLabel>HISTORICAL CONDITIONS ⇄ TARGET REPOSITORY</SectionLabel>
      {current.findings.length === 0 ? (
        <p>No exposure findings yet. The assessment stays empty until both investigations return evidence.</p>
      ) : (
        <table className="matrix">
          <thead>
            <tr>
              <th>Historical prerequisite</th>
              <th>Target observation</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {current.findings.map((finding) => (
              <PrerequisiteRow key={finding.id} finding={finding} onSelect={() => onSelectRef(finding.evidence_refs[0] || "")} />
            ))}
          </tbody>
        </table>
      )}
      <AttackPath findings={current.findings} onSelect={(finding) => onSelectRef(finding.evidence_refs[0] || "")} />
      <section className="panel">
        <SectionLabel>WHAT WOULD BREAK THIS PATH</SectionLabel>
        <p>{current.recommendation || "No recommendation stored."}</p>
        {current.recommendation_limits ? <p className="note">{current.recommendation_limits}</p> : null}
        <div className="refs">
          {current.findings.flatMap((finding) => finding.evidence_refs).filter((ref, index, all) => all.indexOf(ref) === index).map((ref) => (
            <EvidenceBadge key={ref} sourceRef={ref} pressed={false} onSelect={onSelectRef} />
          ))}
        </div>
        {current.stage === "COMPLETE" || current.stage === "PARTIAL" ? (
          <button className="button" onClick={onRecheck}>
            Re-check unpinned revision
          </button>
        ) : null}
      </section>
      {current.simulation ? (
        <section className="panel">
          <SectionLabel>SIMULATION</SectionLabel>
          <div className="summary">
            <div>
              <p>Before</p>
              <StatusMark status={current.simulation.before_status} />
              <p>{current.simulation.before}</p>
            </div>
            <div>
              <p>After</p>
              <StatusMark status={current.simulation.after_status} />
              <p>{current.simulation.after}</p>
            </div>
          </div>
          <p className="note">{current.simulation.limits}</p>
        </section>
      ) : null}
    </div>
  );
}

function Sources({
  sources,
  filter,
  onFilter,
  selectedRef,
  onSelectRef,
  findings,
}: {
  sources: Case["sources"];
  filter: string;
  onFilter: (value: string) => void;
  selectedRef: string | null;
  onSelectRef: (ref: string) => void;
  findings: Case["findings"];
}) {
  const filters = ["All", "Primary", "Independent", "Documentation", "Code", "Unverified"];
  return (
    <div className="stack">
      <div className="filters">
        {filters.map((item) => (
          <button key={item} className="button" aria-pressed={filter === item} onClick={() => onFilter(item)}>
            {item}
          </button>
        ))}
      </div>
      <table className="ledger">
        <tbody>
          {sources.map((source) => {
            const linked = findings.filter((finding) => finding.evidence_refs.includes(source.ref)).length;
            return (
              <tr key={source.ref}>
                <td>
                  <EvidenceBadge sourceRef={source.ref} pressed={selectedRef === source.ref} onSelect={onSelectRef} />
                </td>
                <td>{source.source_type}</td>
                <td>{source.title}</td>
                <td>Published {source.published || "Date unknown"}</td>
                <td>{linked} linked claims</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
