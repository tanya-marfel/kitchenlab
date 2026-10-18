# KitchenLab — Chat layout

The interface mirrors the ChatGPT web app. A narrow sidebar of past threads, a centered conversation, and a rounded composer fixed to the bottom. The product is still an evidence-backed investigation. The chrome is a chat.

## Visual system

Light theme, the ChatGPT light palette.

```css
:root {
  --bg: #ffffff;
  --sidebar: #f9f9f9;
  --text: #0d0d0d;
  --muted: #6e6e80;
  --line: #ececec;
  --hover: #ececec;
  --user: #f4f4f4;
  --chip: #f4f4f4;
}
```

- Type: `ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`. No serif, no mono labels except source ids.
- Body text 16px / 26px. Empty-state title 28px / 36px, weight 500.
- Sidebar 260px, background `#f9f9f9`, 1px right border `#ececec`.
- Conversation column max-width 768px, centered, padding 24px.
- User turns sit in a `#f4f4f4` bubble, radius 24px, aligned to the end of the column.
- Assistant turns are plain text on white, full column width, no bubble and no avatar.
- Composer is one rounded rectangle, radius 28px, 1px border `#e5e5e5`, a soft shadow `0 0 0 1px rgba(0,0,0,0.02), 0 8px 24px rgba(0,0,0,0.06)`. It stays at the bottom of the thread.
- Send control is a 32px black circle with a white arrow. It is disabled while a run is in progress.
- Focus ring is a 2px `#0d0d0d` outline. Respect `prefers-reduced-motion`.

Do not use a paper canvas, a dark lab rail, rust accents, case stamps, serif titles, or a multi-column research desk.

## Information architecture

One screen. The sidebar is the question list. The thread is the investigation.

Sidebar, top to bottom:

- Wordmark `KitchenLab`
- **New question**
- Previous questions, newest first, one line each, the way ChatGPT lists chats
- Footer: `Culinary research mode`

Empty thread, centered in the column. The title and the composer sit together in the vertical middle of the thread. The composer is not pinned to the bottom until a question is open.

- Title: `What are we cooking?`
- One sentence: `Ask yours like this.`

Composer, one rounded box:

- One freeform field, placeholder `Should I boil potatoes before roasting?`
- The text sits in the vertical middle of the field
- Send
- The message is read as a whole. The model names the question and the dish from that text.

## Thread content

The user's first turn is the cooking question.

The assistant turn is the report, in this order:

1. A one-line activity row while research is running, using only recorded tool calls. Example: `Searched recipes · Extracted 2 pages`. No fake thinking text.
2. What is known, then what is not known, as normal paragraphs.
3. A technique table with three columns: Technique, Purpose, Evidence assessment. Each row is one investigated method. The evidence cell is a short sentence plus a status word.
4. Where recipes disagree, a short list of conflicts. Each item names the disagreement and the camps, then the source chips for that conflict. Clicking a chip reveals the passage.
5. A source row, the ChatGPT search pattern: small horizontal chips with the source title. Clicking a chip opens the original URL. The chip also reveals the supporting passage.
6. Findings as a short list. Each item is a sentence plus a status word: `OBSERVED`, `REPORTED`, `INFERRED`, `CONTRADICTED`, `UNKNOWN`, `NOT OBSERVED`. `NOT OBSERVED` includes the inspected scope in the same sentence.
7. An optimized recipe. A title, then numbered steps. Each important step has a one-sentence scientific why.
8. One recommendation paragraph. It must say that the result was not cooked and does not test the user's kitchen.
9. After an experiment, a second user turn with the what-if, then a second assistant turn labeled `Experiment` that separates supported published tests from predicted outcomes.

Suggested follow-up, styled like a ChatGPT reply chip under the answer: `What if I skip {first technique}?` when techniques exist.

## Evidence rules that stay

- Do not show a confidence score, a chat persona, or a claim that a recipe is proven.
- Do not invent research log lines. If a tool call was not recorded, it does not appear.
- Every important claim keeps a source the user can open, or an explicit gap.
- Published and retrieved dates stay distinct when a source sentence includes them.
- `NOT OBSERVED` means not found in the inspected sources.
- Experiment lines must say `supported` or `predicted`.

## Responsive

Below 760px the sidebar collapses behind a menu button. The composer remains full width with 12px page padding. Source chips wrap. The technique table scrolls horizontally if needed.
