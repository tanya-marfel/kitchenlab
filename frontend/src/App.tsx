import { useCallback, useEffect, useRef, useState } from "react";
import { awaitingReport, deleteCase, getCase, interpretMessage, isActive, listHistory, savePrompt, simulate, startCase } from "./api";
import {
  activityLine,
  conflictBody,
  evidenceSentence,
  findingSentence,
  groupHistory,
  historyTitle,
  knownParagraph,
  limitsSentence,
  looksLikeExperiment,
  orderedSteps,
  readCaseId,
  readablePassage,
  recipeNotes,
  recipeTitle,
  rowStamp,
  sourceDates,
  sourceLabel,
  suggestedExperiment,
  tableNote,
  uniqueConflictSources,
  unknownParagraph,
  userQuestion,
} from "./format";
import { type Case, type Conflict, type Finding, type HistoryItem, type Recipe, type Source, type Status } from "./types";

const DRAFT_KEY = "kitchenlab-draft";

type OpenCitation = { source: Source; where: string };

export function App() {
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [current, setCurrent] = useState<Case | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [booting, setBooting] = useState(true);
  const [openCitation, setOpenCitation] = useState<OpenCitation | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<string | null>(null);
  const [pendingPrompt, setPendingPrompt] = useState<string | null>(null);
  const [pendingExperiment, setPendingExperiment] = useState<string | null>(null);
  const [draftReady, setDraftReady] = useState(false);
  const loadSeq = useRef(0);
  const typed = useRef(false);
  const composerRef = useRef<HTMLTextAreaElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const refreshList = useCallback(async () => {
    setHistory(await listHistory());
  }, []);

  const loadCase = useCallback(async (id: string) => {
    const seq = ++loadSeq.current;
    try {
      const next = await getCase(id);
      if (seq !== loadSeq.current) return;
      setCurrent(next);
      setOpenCitation(null);
      setPendingPrompt(null);
      setPendingExperiment(null);
      setError(null);
    } catch (reason) {
      if (seq !== loadSeq.current) return;
      setCurrent(null);
      setError(reason instanceof Error ? reason.message : "This question could not be opened.");
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    const seq = ++loadSeq.current;
    (async () => {
      try {
        const items = await listHistory();
        if (cancelled) return;
        setHistory(items);
        const draft = readDraft();
        if (draft && !typed.current) setMessage(draft);
        const id = readCaseId();
        if (id) {
          const next = await getCase(id);
          if (cancelled || seq !== loadSeq.current) return;
          setCurrent(next);
        }
      } catch (reason) {
        if (!cancelled) setError(reason instanceof Error ? reason.message : "The question list is unavailable.");
      } finally {
        if (!cancelled) {
          setDraftReady(true);
          setBooting(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!draftReady) return;
    writeDraft(message);
  }, [message, draftReady]);

  useEffect(() => {
    const onPop = () => {
      setSidebarOpen(false);
      setOpenCitation(null);
      setPendingPrompt(null);
      setPendingExperiment(null);
      setPendingDelete(null);
      const id = readCaseId();
      if (!id) {
        loadSeq.current += 1;
        setCurrent(null);
        setError(null);
        return;
      }
      void loadCase(id);
    };
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, [loadCase]);

  useEffect(() => {
    if (!current || !awaitingReport(current)) return;
    const timer = window.setInterval(() => {
      getCase(current.id)
        .then((next) => {
          setCurrent((open) => (open?.id === next.id ? next : open));
        })
        .catch((reason: Error) => setError(reason.message));
    }, 2000);
    return () => window.clearInterval(timer);
  }, [current?.id, current?.stage, current?.findings.length, current?.error]);

  useEffect(() => {
    if (!current) return;
    setHistory((items) =>
      items.map((item) =>
        item.id === current.id
          ? {
              ...item,
              prompt: current.prompt || item.prompt,
              question: current.question,
              dish: current.dish,
              stage: current.stage,
              updated_at: current.updated_at,
            }
          : item,
      ),
    );
  }, [current]);

  const activeKey = history
    .filter((item) => isActive(item.stage))
    .map((item) => item.id)
    .join(",");

  useEffect(() => {
    if (!activeKey) return;
    const timer = window.setInterval(() => {
      listHistory()
        .then(setHistory)
        .catch(() => undefined);
    }, 4000);
    return () => window.clearInterval(timer);
  }, [activeKey]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: 0 });
  }, [current?.id, pendingPrompt]);

  useEffect(() => {
    const field = composerRef.current;
    if (!field) return;
    field.style.height = "auto";
    field.style.height = `${field.scrollHeight}px`;
  }, [message, booting, current, pendingPrompt, pendingExperiment]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      setSidebarOpen(false);
      setOpenCitation(null);
      setPendingDelete(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (!current?.id) return;
    document.getElementById(`case-${current.id}`)?.scrollIntoView({ block: "nearest" });
  }, [current?.id]);

  function showCase(id: string | null, mode: "push" | "replace") {
    const hash = id ? `#/c/${encodeURIComponent(id)}` : "#/";
    const next = `${window.location.pathname}${window.location.search}${hash}`;
    const currentUrl = `${window.location.pathname}${window.location.search}${window.location.hash}`;
    if (currentUrl === next) return;
    if (mode === "replace") window.history.replaceState(null, "", next);
    else window.history.pushState(null, "", next);
  }

  async function openCase(id: string) {
    setSidebarOpen(false);
    setPendingDelete(null);
    setError(null);
    if (readCaseId() !== id) showCase(id, "push");
    await loadCase(id);
  }

  function newQuestion() {
    loadSeq.current += 1;
    setCurrent(null);
    setPendingPrompt(null);
    setPendingExperiment(null);
    setOpenCitation(null);
    setError(null);
    setSidebarOpen(false);
    setPendingDelete(null);
    if (readCaseId()) showCase(null, "push");
    window.requestAnimationFrame(() => composerRef.current?.focus());
  }

  async function runExperiment(id: string, change: string) {
    setStarting(true);
    setError(null);
    setPendingExperiment(change);
    setMessage("");
    typed.current = false;
    try {
      const next = await simulate(id, change);
      setCurrent(next);
      setPendingExperiment(null);
      await refreshList();
    } catch (reason) {
      setPendingExperiment(null);
      setMessage(change);
      setError(reason instanceof Error ? reason.message : "The experiment did not complete.");
    } finally {
      setStarting(false);
    }
  }

  async function begin() {
    const prompt = message.trim();
    if (!prompt || starting || (current && awaitingReport(current))) return;
    if (current && !awaitingReport(current) && looksLikeExperiment(prompt)) {
      await runExperiment(current.id, prompt);
      return;
    }
    const previousId = current?.id ?? null;
    setStarting(true);
    setError(null);
    setPendingPrompt(prompt);
    setPendingExperiment(null);
    setCurrent(null);
    setOpenCitation(null);
    setMessage("");
    typed.current = false;
    if (previousId) showCase(null, "replace");
    try {
      const request = await interpretMessage(prompt);
      const id = await startCase(request.question, request.dish, false, prompt);
      await savePrompt(id, prompt).catch(() => undefined);
      await refreshList();
      showCase(id, "push");
      await loadCase(id);
    } catch (reason) {
      setPendingPrompt(null);
      setMessage(prompt);
      setError(reason instanceof Error ? reason.message : "The investigation did not start.");
      if (previousId) {
        showCase(previousId, "replace");
        await loadCase(previousId);
      }
    } finally {
      setStarting(false);
    }
  }

  async function remove(id: string) {
    try {
      await deleteCase(id);
      setHistory((items) => items.filter((item) => item.id !== id));
      setPendingDelete(null);
      if (current?.id === id) {
        loadSeq.current += 1;
        setCurrent(null);
        setOpenCitation(null);
        showCase(null, "replace");
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The question could not be deleted.");
    }
  }

  const running = Boolean(current && awaitingReport(current));
  const showThread = Boolean(current || pendingPrompt);
  const title = current ? historyTitle(current) : pendingPrompt;

  return (
    <div className="shell">
      {sidebarOpen ? (
        <button className="backdrop" aria-label="Close menu" onClick={() => setSidebarOpen(false)} />
      ) : null}
      <Sidebar
        history={history}
        ready={!booting}
        currentId={current?.id ?? null}
        pendingDelete={pendingDelete}
        onNew={newQuestion}
        onOpen={(id) => openCase(id).catch((reason: Error) => setError(reason.message))}
        onAskDelete={setPendingDelete}
        onCancelDelete={() => setPendingDelete(null)}
        onDelete={(id) => void remove(id)}
        open={sidebarOpen}
      />
      <main className="thread">
        <header className="topbar">
          <button
            className="icon-button menu"
            type="button"
            aria-label="Menu"
            aria-expanded={sidebarOpen}
            aria-controls="questions"
            onClick={() => setSidebarOpen((open) => !open)}
          >
            <MenuIcon />
          </button>
          {title ? <div className="top-title">{title}</div> : <div />}
          <span />
        </header>
        <div className="scroll" ref={scrollRef}>
          <div className="column">
            {booting ? null : showThread ? (
              <Thread
                current={current}
                pendingPrompt={pendingPrompt}
                pendingExperiment={pendingExperiment}
                openCitation={openCitation}
                onOpenCitation={setOpenCitation}
                onExperiment={(change) => {
                  if (!current) return;
                  void runExperiment(current.id, change);
                }}
              />
            ) : (
              <div className="empty">
                <h1>What are we cooking?</h1>
                <p>Ask yours like this.</p>
                <Composer
                  inputRef={composerRef}
                  message={message}
                  setMessage={(value) => {
                    typed.current = true;
                    setMessage(value);
                  }}
                  disabled={starting}
                  error={error}
                  onSend={() => void begin()}
                />
              </div>
            )}
          </div>
        </div>
        {showThread ? (
          <div className="composer-wrap">
            <Composer
              inputRef={composerRef}
              message={message}
              setMessage={(value) => {
                typed.current = true;
                setMessage(value);
              }}
              disabled={starting || running}
              error={error}
              onSend={() => void begin()}
              placeholder={current && !running ? "What if I skip that step?" : "Should I boil potatoes before roasting?"}
            />
          </div>
        ) : null}
      </main>
    </div>
  );
}

function Sidebar({
  history,
  ready,
  currentId,
  pendingDelete,
  open,
  onNew,
  onOpen,
  onAskDelete,
  onCancelDelete,
  onDelete,
}: {
  history: HistoryItem[];
  ready: boolean;
  currentId: string | null;
  pendingDelete: string | null;
  open: boolean;
  onNew: () => void;
  onOpen: (id: string) => void;
  onAskDelete: (id: string) => void;
  onCancelDelete: () => void;
  onDelete: (id: string) => void;
}) {
  const groups = groupHistory(history);
  return (
    <nav id="questions" className={open ? "sidebar open" : "sidebar"} aria-label="Questions">
      <div className="sidebar-top">
        <button className="wordmark" type="button" onClick={onNew} aria-label="KitchenLab">
          <LogoMark />
          <span>KitchenLab</span>
        </button>
        <button className="new-chat" type="button" onClick={onNew}>
          <PlusIcon />
          New question
        </button>
      </div>
      <div className="history">
        {ready && groups.length === 0 ? <p className="history-empty">Questions you ask will show up here.</p> : null}
        {groups.map((group) => (
          <section key={group.label} className="history-group" aria-label={group.label}>
            <h2>{group.label}</h2>
            {group.items.map((item) => {
              const title = historyTitle(item);
              const stamp = rowStamp(item.updated_at || item.created_at, group.label);
              const selected = currentId === item.id;
              if (pendingDelete === item.id) {
                return (
                  <div key={item.id} className="history-confirm" id={`case-${item.id}`}>
                    <span>Delete?</span>
                    <button type="button" onClick={() => onDelete(item.id)}>
                      Delete
                    </button>
                    <button type="button" onClick={onCancelDelete}>
                      Cancel
                    </button>
                  </div>
                );
              }
              return (
                <div key={item.id} className="history-row" id={`case-${item.id}`} data-current={selected ? "true" : undefined}>
                  <button
                    className="history-item"
                    type="button"
                    aria-current={selected ? "true" : undefined}
                    title={title}
                    onClick={() => onOpen(item.id)}
                  >
                    {isActive(item.stage) ? <span className="dot" aria-label="In progress" /> : null}
                    <span className="history-title">{title}</span>
                    {stamp ? <time dateTime={item.updated_at || item.created_at}>{stamp}</time> : null}
                  </button>
                  <button
                    className="icon-button delete-case"
                    type="button"
                    aria-label={`Delete ${title}`}
                    onClick={() => onAskDelete(item.id)}
                  >
                    <TrashIcon />
                  </button>
                </div>
              );
            })}
          </section>
        ))}
      </div>
      <footer>Culinary research mode</footer>
    </nav>
  );
}

function Composer({
  message,
  setMessage,
  disabled,
  error,
  onSend,
  inputRef,
  placeholder = "Should I boil potatoes before roasting?",
}: {
  message: string;
  setMessage: (value: string) => void;
  disabled: boolean;
  error: string | null;
  onSend: () => void;
  inputRef: { current: HTMLTextAreaElement | null };
  placeholder?: string;
}) {
  return (
    <div className="composer-block">
      {error ? (
        <p className="error" role="alert">
          {error}
        </p>
      ) : null}
      <form
        className="composer"
        onSubmit={(event) => {
          event.preventDefault();
          if (!message.trim() || disabled) return;
          onSend();
        }}
      >
        <textarea
          ref={inputRef}
          rows={1}
          value={message}
          placeholder={placeholder}
          aria-label="Message"
          onChange={(event) => setMessage(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              if (!disabled && message.trim()) onSend();
            }
          }}
        />
        <button className="send" type="submit" disabled={disabled || !message.trim()} aria-label="Send">
          <ArrowIcon />
        </button>
      </form>
    </div>
  );
}

function Thread({
  current,
  pendingPrompt,
  pendingExperiment,
  openCitation,
  onOpenCitation,
  onExperiment,
}: {
  current: Case | null;
  pendingPrompt: string | null;
  pendingExperiment: string | null;
  openCitation: OpenCitation | null;
  onOpenCitation: (citation: OpenCitation | null) => void;
  onExperiment: (change: string) => void;
}) {
  const prompt = current ? userQuestion(current) : (pendingPrompt ?? "");
  const running = current ? awaitingReport(current) : Boolean(pendingPrompt);
  const activity = current ? activityLine(current.events) : "";
  const experimentPrompt = pendingExperiment || current?.experiment_prompt || "";

  function toggleCitation(source: Source, where: string) {
    const same = openCitation?.source.ref === source.ref && openCitation.where === where;
    if (same) {
      onOpenCitation(null);
      return;
    }
    onOpenCitation({ source, where });
    if (source.url) window.open(source.url, "_blank", "noopener,noreferrer");
  }

  return (
    <>
      <div className="turn user">
        <div className="bubble">{prompt}</div>
      </div>
      <article className="turn assistant" aria-busy={running}>
        {running ? (
          <p className="activity" aria-live="polite" title={activity || undefined}>
            {activity || "Research in progress."}
          </p>
        ) : null}
        {current?.error && !running ? <p>{current.error}</p> : null}
        {current && knownParagraph(current.summary_known, current.findings) ? (
          <p>{knownParagraph(current.summary_known, current.findings)}</p>
        ) : null}
        {current && unknownParagraph(current.summary_unknown, current.findings) ? (
          <p>{unknownParagraph(current.summary_unknown, current.findings)}</p>
        ) : null}
        {current && current.findings.length > 0 ? <TechniqueTable findings={current.findings} /> : null}
        {current && current.conflicts.length > 0 ? (
          <section className="block">
            <h2>Where recipes disagree</h2>
            <ConflictList
              conflicts={current.conflicts}
              sources={current.sources}
              openCitation={openCitation}
              onToggle={toggleCitation}
              showSources={uniqueConflictSources(current.conflicts)}
            />
          </section>
        ) : null}
        {current && current.sources.length > 0 ? (
          <section className="block">
            <h2>Sources</h2>
            <div className="sources">
              {current.sources.map((source) => (
                <SourceChip
                  key={source.ref}
                  source={source}
                  pressed={openCitation?.source.ref === source.ref && openCitation.where === "sources"}
                  onOpen={() => toggleCitation(source, "sources")}
                />
              ))}
            </div>
            {openCitation?.where === "sources" ? <SourceDetail source={openCitation.source} /> : null}
          </section>
        ) : null}
        {current && current.findings.length > 0 ? (
          <section className="block">
            <h2>Findings</h2>
            <ul className="findings">
              {current.findings.map((finding) => (
                <li key={finding.id}>
                  {findingSentence(finding)} <StatusMark status={finding.status} />
                </li>
              ))}
            </ul>
          </section>
        ) : null}
        {current?.recipe && current.recipe.steps.length > 0 ? <RecipeBlock recipe={current.recipe} /> : null}
        {current?.recommendation ? <p>{current.recommendation}</p> : null}
        {current?.recommendation_limits ? <p className="why">{limitsSentence(current.recommendation_limits)}</p> : null}
        {current &&
        (current.stage === "COMPLETE" || current.stage === "PARTIAL") &&
        current.findings.length > 0 &&
        !current.simulation &&
        !pendingExperiment ? (
          <button className="suggest" type="button" onClick={() => onExperiment(suggestedExperiment(current))}>
            {suggestedExperiment(current)}
          </button>
        ) : null}
      </article>
      {experimentPrompt ? (
        <div className="turn user">
          <div className="bubble">{experimentPrompt}</div>
        </div>
      ) : null}
      {pendingExperiment && !current?.simulation ? (
        <article className="turn assistant" aria-busy="true">
          <p className="activity">Experiment in progress.</p>
        </article>
      ) : null}
      {current?.simulation ? (
        <article className="turn assistant">
          <p>
            <strong>Experiment.</strong> {current.simulation.change}
          </p>
          <p>
            <span className="status-word">supported</span> {current.simulation.supported}
          </p>
          <p>
            <span className="status-word">predicted</span> {current.simulation.predicted}
          </p>
          <p className="why">{limitsSentence(current.simulation.limits)}</p>
        </article>
      ) : null}
    </>
  );
}

function StatusMark({ status }: { status: Status }) {
  return <span className="status-word">{status}</span>;
}

function TechniqueTable({ findings }: { findings: Finding[] }) {
  return (
    <div className="table-wrap">
      <table className="techniques">
        <caption>
          Techniques
          <span className="table-note">{tableNote(findings)}</span>
        </caption>
        <thead>
          <tr>
            <th scope="col">Technique</th>
            <th scope="col">Purpose</th>
            <th scope="col">Evidence assessment</th>
          </tr>
        </thead>
        <tbody>
          {findings.map((finding) => (
            <tr key={finding.id}>
              <th scope="row">{finding.technique}</th>
              <td>{finding.purpose}</td>
              <td>
                {evidenceSentence(finding)} <StatusMark status={finding.status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ConflictList({
  conflicts,
  sources,
  openCitation,
  onToggle,
  showSources,
}: {
  conflicts: Conflict[];
  sources: Source[];
  openCitation: OpenCitation | null;
  onToggle: (source: Source, where: string) => void;
  showSources: boolean;
}) {
  return (
    <ul className="conflicts" aria-label="Where recipes disagree">
      {conflicts.map((conflict) => {
        const where = `conflict:${conflict.id}`;
        return (
          <li key={conflict.id}>
            <strong>{conflict.topic}.</strong> {conflictBody(conflict)}
            {showSources && conflict.source_refs.length > 0 ? (
              <div className="timeline-refs">
                {conflict.source_refs.map((ref) => {
                  const source = sources.find((item) => item.ref === ref);
                  if (!source) return null;
                  return (
                    <SourceChip
                      key={ref}
                      source={source}
                      pressed={openCitation?.source.ref === ref && openCitation.where === where}
                      onOpen={() => onToggle(source, where)}
                    />
                  );
                })}
              </div>
            ) : null}
            {openCitation?.where === where ? <SourceDetail source={openCitation.source} /> : null}
          </li>
        );
      })}
    </ul>
  );
}

function RecipeBlock({ recipe }: { recipe: Recipe }) {
  return (
    <section className="recipe">
      <h2>{recipeTitle(recipe.title)}</h2>
      {recipe.servings ? <p className="servings">{recipe.servings}</p> : null}
      <ol>
        {orderedSteps(recipe.steps).map((step) => (
          <li key={step.id}>
            <span>{step.instruction}</span>
            {step.why ? (
              <p className="why">
                <span className="why-label">Why it matters. </span>
                {step.why}
              </p>
            ) : null}
          </li>
        ))}
      </ol>
      {recipe.notes ? <p className="why">{recipeNotes(recipe.notes)}</p> : null}
    </section>
  );
}

function SourceChip({ source, pressed, onOpen }: { source: Source; pressed: boolean; onOpen: () => void }) {
  return (
    <button type="button" className="chip" aria-pressed={pressed} title={source.title} onClick={onOpen}>
      {sourceLabel(source)}
    </button>
  );
}

function SourceDetail({ source }: { source: Source }) {
  return (
    <div className="passage">
      <p className="passage-meta">
        {source.source_type}
        {sourceDates(source) ? `. ${sourceDates(source)}` : ""}
      </p>
      {source.passage ? <p>{readablePassage(source.passage)}</p> : null}
      {source.url ? (
        <p>
          <a href={source.url} target="_blank" rel="noreferrer">
            Open original source
          </a>
        </p>
      ) : null}
    </div>
  );
}

function LogoMark() {
  return (
    <svg className="wordmark-mark" width="32" height="32" viewBox="0 0 32 32" aria-hidden="true">
      <rect width="32" height="32" rx="9" fill="currentColor" />
      <path
        fill="#fff"
        d="M12.2 6.4h7.6a.85.85 0 0 1 0 1.7h-.7v2.6l3.7 6.5a6.05 6.05 0 1 1-13.2 0l3.7-6.5V8.1h-.7a.85.85 0 0 1 0-1.7Z"
      />
      <circle cx="14.1" cy="20.8" r="1.45" fill="currentColor" />
    </svg>
  );
}

function PlusIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
      <path d="M8 3v10M3 8h10" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

function MenuIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
      <path d="M3 5h12M3 9h12M3 13h12" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

function ArrowIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
      <path d="M8 12.5V3.5M4 7.5 8 3.5l4 4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function TrashIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 16 16" aria-hidden="true">
      <path d="M3.5 4.5h9M6.2 4.4V3.2h3.6v1.2M5.2 4.5l.5 8h4.6l.5-8" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function readDraft(): string {
  try {
    return localStorage.getItem(DRAFT_KEY) ?? "";
  } catch {
    return "";
  }
}

function writeDraft(value: string) {
  try {
    if (value) localStorage.setItem(DRAFT_KEY, value);
    else localStorage.removeItem(DRAFT_KEY);
  } catch {
    /* The draft is optional when storage is blocked. */
  }
}
