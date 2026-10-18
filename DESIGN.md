# BreachMirror — UI Design Rules

> **Purpose:** This document is the visual and interaction contract for BreachMirror. Give it to a designer or coding agent before any UI implementation. It is **not** a backend architecture spec. When in doubt, follow this file rather than default SaaS templates or component-library demos.

## 0. Product and visual thesis

**Product:** BreachMirror reconstructs a documented security incident, examines a user-authorized organization's currently observable code and documentation, and evaluates which *conditions* behind the historical attack may exist in the target environment.

**Visual concept:** **A forensic research workbench, not an AI chatbot.** Think incident-response desk + archival case file + modern developer tool. Calm, precise, legible, and technical. Every visible claim should feel inspectable.

**Three design promises:**
1. **Evidence before decoration.** Claims, source references, dates, and uncertainty are the visual hierarchy.
2. **Uncertainty is a first-class state.** “Unknown,” “reported,” “inferred,” and “verified” must never look interchangeable.
3. **Show the investigation, not AI theater.** Show actions and supporting evidence, not fake thinking animations or unverifiable internal reasoning.

**Design personality:** sober, editorial, investigative, intentionally dense, restrained. A tool a security engineer would use for 45 minutes, not a landing page meant to impress in five seconds.

## 1. Anti-generic rules — non-negotiable

**Do not build:**
- A full-screen gradient hero, purple/blue neon, glowing orbs, particle backgrounds, glassmorphism, or floating blur blobs.
- A centered prompt box as the entire product UI, “Ask anything…” placeholder, chat bubbles, or a ChatGPT clone.
- Six interchangeable rounded dashboard cards with icons and made-up metrics.
- Random cybersecurity imagery: shields, locks, hooded people, stock server racks, animated world maps.
- Fake confidence percentages such as “97% certain” without a defined calculation.
- Constant spinning “AI is thinking” indicators, typewriter text, staged agent monologues, or synthetic logs.
- Repeated gradients, pill-shaped everything, excessive drop shadows, or 24px-radius panels.
- Color-only status distinctions or thin/low-contrast text.
- Placeholder citations; every displayed citation must open the original, relevant source.

**Instead:** Use a clearly structured case workspace: a compact left rail, a substantial investigative canvas, and a contextual evidence inspector on the right. Treat sources as artifacts, not footnotes.

## 2. Visual identity

### 2.1 Signature

Working name: **BREACHMIRROR** (render in one word, uppercase in small places). A small `BM /` monogram is allowed; no decorative robot or shield logo.

Use **case stamps** as the visual signature:

`CASE / 004` · `INCIDENT / 2026-07` · `PUBLIC EVIDENCE` · `LAST CHECKED / 18 OCT 2026`

Labels should resemble an analytical dossier: compact uppercase mono labels with unusually good spacing and alignment, not faux classified stamps or distressed textures.

### 2.2 Color palette — light theme is primary

```css
:root {
  --canvas: #F5F4EF;         /* warm archival paper */
  --surface: #FFFFFF;        /* panels and inspector */
  --surface-2: #ECEDE7;      /* subtle sections and code backgrounds */
  --sidebar: #18211F;        /* graphite/forest-black */
  --ink: #18211F;            /* primary text */
  --muted: #56635E;          /* secondary text */
  --hairline: #C8CEC7;       /* dividers */
  --accent: #AD4529;         /* rust/orange: primary action or selected evidence */
  --accent-soft: #F7E8E1;
  --verified: #23624D;       /* supported by directly inspectable evidence */
  --reported: #385A79;       /* attributed to a source, not independently confirmed */
  --inferred: #80541E;       /* plausible, conditional */
  --contradicted: #9E3131;   /* sources materially disagree */
  --unknown: #56635E;
  --focus: #195BBF;          /* keyboard focus, distinct from risk colors */
}
```

Rules:
- Canvas is warm off-white, not pure gray. Side navigation is dark; main content is light.
- Use rust **sparingly**: active primary button, selected timeline event, key relationship, or meaningful alert. Never coat whole graphs in orange.
- Reserve semantic colors for semantic meaning. Do **not** use red simply to mean “important.”
- No gradients in app UI. No elevation except a subtle shadow for floating popovers/dialogs.
- Panels rely on 1px borders, whitespace, and typography rather than heavy card styling.

### 2.3 Typography

- **Interface:** `IBM Plex Sans`, fallback `Inter, system-ui, sans-serif`.
- **Technical labels, IDs, dates, file paths, code:** `IBM Plex Mono`, fallback `ui-monospace, SFMono-Regular, monospace`.
- **Case titles only (optional):** `Source Serif 4`, fallback `Georgia, serif`; use sparingly for editorial character. Never for controls, reports, or data tables.

Scale (desktop):

| Element | Font | Size / line height | Weight |
|---|---|---|---|
| Case title | Serif or Plex Sans | 32 / 38 | 500–600 |
| Section title | Plex Sans | 20 / 28 | 600 |
| Component title | Plex Sans | 15 / 22 | 600 |
| Body | Plex Sans | 14 / 21 | 400 |
| Dense row | Plex Sans | 13 / 19 | 400–500 |
| Meta label | Plex Mono | 10–11 / 16 | 500 |
| Code/source snippet | Plex Mono | 12 / 19 | 400 |

Do not use all-caps for paragraph text. Allow long source titles and technical paths to wrap, truncate only with accessible full-value reveal.

### 2.4 Spacing, borders, shape

- Base spacing unit: **4px**. Preferred increments: 8, 12, 16, 24, 32, 48.
- Radius: controls **5px**, panels **6px**, popovers **8px**, status tags **3px**. No large pill cards.
- 1px hairline dividers; 2px only for selected rails or comparison emphasis.
- Desktop content should have breathing room between major *regions*, with relatively compact rows *inside* regions.
- Icons: consistent 16px stroked set (e.g. Lucide) with no unnecessary icon for every label. Prefer text for critical actions.

## 3. Information architecture

Primary navigation (do not invent additional pages for the MVP):

1. **Cases** — recent/saved investigations, start a new case.
2. **Investigation** — incident reconstruction and agent research activity.
3. **Exposure** — mapping historical prerequisites against target evidence.
4. **Sources** — searchable source ledger and claim provenance.

Optional later: **Changes** — comparison of two research snapshots; only show if actually implemented.

A single case persists between views. The app must not lose the selected incident, target repository, or inspection context when switching sections.

### 3.1 Case setup

The entry form is a practical two-field research form, not a chatbot:

- **Incident:** incident name or primary report URL. Example: `AI infrastructure intrusion — public disclosure`.
- **Target:** user-authorized GitHub repository URL or public demo organization.
- Primary action: **Start investigation**.
- Small inline note: “Public sources only. No intrusive testing or credential validation.”

Do not require a model selector, 10 toggles, or an infrastructure inventory to start. Provide an explicit **Load sample case** action for demo reliability.

## 4. Desktop layout

Target baseline: **1440 × 900**. The interface must still work at 1280px wide.

- **Global rail:** 216px, dark background, fixed on desktop; wordmark, case navigation, footer environment label.
- **Top case header:** 64px high; breadcrumb, case identifier, source freshness, compact actions.
- **Primary workspace:** fluid, min-width 600px when inspector is open, padding 28–32px.
- **Evidence inspector:** 340–380px on the right, independently scrollable and collapsible; only opens on selection (or remains pinned if user chooses).
- **Mobile/tablet:** rail collapses; inspector becomes a drawer; graphs get an accessible list/table alternative.

The canvas is the product. Avoid centering content in a marketing-style `max-width: 800px` column or making every section a detached card.

### 4.1 Investigation screen — recommended composition

```text
┌──────────────────┬──────────────────────────────────────────┬────────────────────────┐
│ BREACHMIRROR     │ CASE / 004     INCIDENT RECONSTRUCTION  │ EVIDENCE / 07          │
│                  │                                          │                        │
│ Cases            │ Incident title                           │ SOURCE DETAIL          │
│ Investigation  ● │ Summary: what is known / not known      │ Original title + URL   │
│ Exposure         │ ──────────────────────────────────────── │ Published / retrieved  │
│ Sources          │                                          │                        │
│                  │ [Timeline] [Attack path] [Research log]  │ Exact supporting       │
│                  │                                          │ passage and file lines │
│                  │  JUL 10  ── EVENT 01   [REF 01, REF 03] │                        │
│                  │              ↓                           │ Claim(s) supported     │
│                  │  JUL 16  ── DISCLOSURE [REF 02]         │ Confidence + scope     │
│                  │              ↓                           │                        │
│                  │  AUG 26  ── REPORT     [REF 04]          │ [Open original source] │
│                  │                                          │                        │
│                  │  OPEN QUESTIONS / 03                     │                        │
└──────────────────┴──────────────────────────────────────────┴────────────────────────┘
```

The right inspector should show **why** a selected assertion appears in the timeline, not repeat the whole report.

### 4.2 Exposure screen — recommended composition

```text
HISTORICAL CONDITIONS  ⇄  TARGET REPOSITORY

Historical prerequisite            Target observation              Status
───────────────────────────────────────────────────────────────────────────
Untrusted data reaches tool       External retrieval path found  OBSERVED
Tool can change protected files   Permissions not documented     UNKNOWN
Human approval missing           Approval gate found in config NOT OBSERVED*

* NOT OBSERVED means not observed in inspected scope, not globally absent.

Below: conditional attack-path graph + "What would break this path?" panel.
```

Do not display a fake single-number “Breach Probability.” Show a **prerequisite matrix**, supported relationships, unknowns, and evidence gaps.

## 5. Components — detailed design and behavior

### 5.1 The evidence badge

Format: `[REF 07]` or `[SRC 07]` in mono, 11px, with a subtle outline.

On click: open inspector with original source URL, publisher/author, publication date (if available), retrieval date, exact claim-supported passage, and context. For source code: repository, commit SHA, file path, line range, and commit-pinned link.

Never attach one vague citation to five unrelated claims. If a source does not support the specific claim, mark the claim as **UNSUPPORTED** and trigger a research-gap state.

### 5.2 Claim status vocabulary — use these exact meanings

| Label | Meaning | Visual treatment |
|---|---|---|
| **OBSERVED** | Verified in directly inspected code/config/artifact within stated scope | dark green dot + text |
| **REPORTED** | Claimed by an identified source; not independently confirmed | blue square + text |
| **INFERRED** | Analyst/model interpretation conditional on stated assumptions | amber diamond + dashed border |
| **CONTRADICTED** | Materially conflicting evidence on the same proposition | red split icon + text |
| **UNKNOWN** | Available evidence cannot establish the condition | gray question-mark icon + text |
| **NOT OBSERVED** | Not present in the explicitly inspected scope | outlined circle + text; must show scope |

**Never substitute** “SAFE” for NOT OBSERVED, “VULNERABLE” for INFERRED, or “CONFIRMED COMPROMISE” for a condition match.

Each finding must include `Observation`, `Why it matters`, `Evidence`, `Limitations`, and `Next check`.

### 5.3 Event timeline

- Vertical timeline is the default; avoid an elaborate horizontal timeline that's difficult to scan.
- **Two dates are mandatory:** `Occurred` and `Disclosed`. If unknown, show `Date unknown`; never quietly use the publication date as event date.
- Each event shows: short factual title, one sentence, source badges, status.
- Clicking an event selects it, scrolls inspector to its strongest cited evidence, and highlights matching nodes in the attack path.
- Disagreements appear as annotations in the same timeline rather than as a separate sensational “corporate spin exposed” panel.

### 5.4 Conditional attack-path graph

- Favor a **left-to-right, 4–8-node directed path** for MVP. No force-directed hairball network.
- Node categories: `Historical step`, `Attack prerequisite`, `Target observation`, `Control`, `Unknown`.
- **Solid edge:** a relationship established by cited evidence.
- **Dashed edge:** conditional or inferred relationship. Add a visible `IF` label where the condition matters.
- **Blocked edge:** condition interrupted by a documented control; display a bar/slash icon, not color alone.
- Each edge is clickable; inspector explains its supporting evidence or unmet prerequisite.
- Do not animate a path into a “breach achieved” state based solely on hypothetical edges.

### 5.5 Research activity / agent trace

A small, collapsible **Research log** panel lists verifiable process events:

`11:42:08  Tavily search · primary disclosure`  
`11:42:14  Extracted 2 articles · 1 primary source`  
`11:42:25  Evidence gap detected · initial access unclear`  
`11:42:26  Follow-up query issued`  
`11:42:38  Source verified · claim updated`

This is an **action trace**, not private model chain-of-thought. Only render tool invocations, evidence decisions, and conclusion changes actually recorded by the application. Never invent logs for the demo.

States: `QUEUED`, `RESEARCHING`, `VERIFYING`, `MAPPING`, `COMPLETE`, `PARTIAL`, `FAILED`. Show the current stage and what succeeded even if a later step fails.

### 5.6 Source ledger

Compact rows, not cards:

`REF 07  |  Primary disclosure  |  Published 26 AUG 2026  |  3 linked claims  |  Open →`

Filters: `Primary`, `Independent`, `Documentation`, `Code`, `Unverified`. Each row shows source type and linked claims. Dates must be labeled `Published`, `Updated`, or `Retrieved`; do not conflate them.

### 5.7 Comparisons and counterfactuals

The core comparison view should read like a technical diff:

```text
HISTORICAL CONDITION          CURRENT TARGET                 RESULT
Write-capable identity        Permissions inaccessible       UNKNOWN
Unpinned model reference      Pinned to commit SHA          NOT OBSERVED
```

For hypothetical remediation, label it **SIMULATION**. Display **Before** and **After** side by side, with the specific attack prerequisite affected. Never claim global safety after one mitigation.

## 6. Motion and state

Motion should communicate **newly verified state**, not simulate intelligence.

- Hover/focus: 100–150ms.
- Inspector slide: 180–220ms.
- Timeline insertion: subtle 160ms fade/shift, only when real data arrives.
- Graph edges should appear once the relationship is evaluated, never draw fake progress paths.
- Respect `prefers-reduced-motion`; with reduced motion, use instant state updates.
- Long investigations must reveal meaningful partial results, with clear `LAST UPDATED` and `RESEARCH IN PROGRESS` labels.

Always design **loading, empty, partial, stale, error, and success** states for the four primary pages.

**Example empty state:** “No source-backed events yet. Start an investigation or load the sample case.”

**Example partial state:** “Timeline available. Target permissions could not be verified; exposure assessment is incomplete.”

## 7. UX copy rules

Voice: clipped, precise, non-dramatic. Write like a careful security analyst, not a marketing site or an AI persona.

**Use:**
- “Evidence supports this relationship.”
- “No evidence found in 14 inspected files.”
- “Further verification required.”
- “This attack path depends on an unverified permission.”
- “View source lines 42–53.”

**Avoid:**
- “Our AI uncovered a critical breach!”
- “You are 94% likely to be hacked.”
- “Military-grade autonomous protection.”
- “Beam is thinking deeply…”
- “All systems secure.”

Keep conclusion titles boring enough to be trusted. Prefer **“Unpinned reference observed”** to **“Critical supply-chain compromise detected.”**

## 8. Accessibility and responsive behavior

- Meet **WCAG 2.2 AA** contrast and interaction requirements. Verify implementation contrast, don't assume token values automatically pass in every context.
- Text contrast target ≥4.5:1; essential UI graphics/indicators ≥3:1.
- Interactive targets: minimum 24×24px, aim 36–40px for primary controls.
- All clickable graph edges and timeline events must be reachable with keyboard and listed in an equivalent table/list.
- Tooltips aren't the sole container of important information.
- Status meanings conveyed through label + shape/icon + color.
- At widths <1100px, right inspector becomes overlay drawer; <760px, the left rail becomes compact nav, and comparison tables become stacked sections with persistent labels.
- Never horizontally scroll the entire page; limit scrolling to tables/code panels where clearly indicated.

## 9. UI implementation guidance

- **Preferred:** React + Tailwind CSS + shadcn/ui primitives customized to these tokens; React Flow for the attack path if time permits.
- Start with CSS variables and reusable primitives: `CaseHeader`, `SectionLabel`, `EvidenceBadge`, `StatusMark`, `ClaimRow`, `SourceInspector`, `TimelineEvent`, `PrerequisiteRow`, `ResearchLog`.
- Override shadcn defaults where they look like a stock dashboard: smaller radii, tighter spacing, no giant muted cards, darker text, visible table separators.
- Render UI from real structured data. Never hard-code fabricated statuses or source links into production components.
- It is acceptable to use a **clearly labeled sample case** for a hackathon demo. Never disguise sample data as live research.
- Default entry point is a saved/open investigation workspace, **not** a marketing landing page. A separate marketing page is out of MVP scope.

## 10. The two-minute demo UX

Judges should be able to understand the whole product by watching the screen with sound off.

1. **0:00–0:15 — Case setup.** Incident URL/name + authorized demo repository. Click **Start investigation**.
2. **0:15–0:45 — Agent research.** Real search actions become visible; first source badges appear on the timeline.
3. **0:45–1:10 — Evidence gap.** Investigator detects an unknown prerequisite; issues a follow-up search. Show a real state change.
4. **1:10–1:35 — Exposure analysis.** Side-by-side prerequisite matrix and attack-path graph distinguish observed conditions from unknowns.
5. **1:35–2:00 — Source verification.** Click one event and one target finding to show source-level proof; end on one actionable recommendation with stated limits.

If the actual run exceeds two minutes, **reduce scope or reduce model/search calls**; do not fake, preanimate, or cut around the hard part. The track values one authentic run more than polished theater.

## 11. Acceptance checklist — reject the UI if any answer is “no”

- [ ] Does the screen look like a dedicated investigation workbench rather than a SaaS template?
- [ ] Is there a clear difference between historical incident facts and target-environment observations?
- [ ] Can a judge click any important assertion and find its original supporting source?
- [ ] Do observed, reported, inferred, and unknown conclusions look and read differently?
- [ ] Is the investigated scope visible wherever “not observed” appears?
- [ ] Does the app show concrete research actions without claiming to expose private model reasoning?
- [ ] Are dates identified as occurrence, publication, or retrieval dates?
- [ ] Can a user understand which path steps are conditional or blocked?
- [ ] Are errors, incomplete research, and unavailable data handled without inventing conclusions?
- [ ] Are keyboard access, reduced motion, and responsive layouts implemented?
- [ ] Is the interface usable when populated with real long URLs, code paths, and imperfect sources?
- [ ] Does the MVP foreground one high-quality investigation instead of ten empty dashboard features?

---

## One-line direction for any UI-generating coding agent

> Build BreachMirror as an **editorial forensic analysis workbench**: warm paper canvas, dark fixed rail, Plex typography, rust accents, evidence-first timelines, compact source tables, a right-side source inspector, and a conditional attack-path visualization. Avoid generic AI dashboards, marketing hero sections, purple gradients, glass cards, chat-first UI, invented metrics, and decorative AI animations. Follow the component, provenance, and uncertainty rules in `design.md` exactly.
