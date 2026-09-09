/**
 * The first React island: `#org-result`, and the four states it can be in.
 *
 * **What this replaces.** `#org-result` had TWELVE `innerHTML` writers across three functions -
 * `renderInventoryResult` (2), `renderOrganizeResult` (6), `startOrganizeRun` (4) - so four
 * genuinely different states were produced as strings by twelve places and none was
 * authoritative. That is the worst structure on the screen and the thing React is actually for.
 *
 * **A pure refactor. A visual delta here is a bug.** The acceptance oracle is the unchanged e2e
 * suite: the screen must look and behave identically afterwards.
 *
 * ⚠ **`card()` STAYS IN `app.js` AND IS CALLED FROM HERE, and that is a decision rather than a
 * shortcut.** It is invoked 54 times and writes into TEN result regions across six screens
 * (`mig-result`, `rc-result`, `bk-result`, `where-result`, `ev-result`, `bake-confirm`,
 * `verify-result`, `stats-result`, `org-undo-stage`, `org-result`). Porting it would drag six
 * unrelated screens into an island scoped to one region, against a suite of ~154 Organize tests
 * asserting on its output. So the components below own the STATE MACHINE; the content is still
 * built by the existing, heavily-tested string builders. Porting those is later work, and doing
 * it here would have made a pure refactor into a rewrite.
 *
 * **The bundle hash stays published** - `test_the_served_bundle_was_built_from_these_sources`
 * is the proof this seam is live, and it reads this attribute.
 */

declare const __BUNDLE_SOURCE_HASH__: string;

import { StrictMode, useEffect, useRef, useSyncExternalStore } from "react";
import { createRoot } from "react-dom/client";

import type { components } from "./generated/api";
import { CompletionCard, type CompletionSeam, type OrganizeDone } from "./completion";
import {
  ByFormat,
  InventoryCard,
  formatters,
  toHtml,
  type ByFormatCounts,
  type Inventory,
} from "./inventory";
import {
  DateQualityNotes,
  DestinationTree,
  InferredShiftNote,
  MatchList,
  PreviewCard,
  PreviewEmptyCard,
  type DateQualityCounts,
  type InferredShifts,
  type PreviewEmpty,
  type PreviewSummary,
  type PreviewView,
} from "./preview";

// Tailwind's entry. Imported HERE rather than linked from the template because Vite has one
// entry and emits one stylesheet beside `main.js`; the template links that output. `tokens.css`
// is NOT imported - it is served standalone and must keep exactly one copy.
import "./styles/tailwind.css";

/** The summary an organize run delivers, as the contract declares it: `organize_run`'s
 *  `JobTarget[CompletionBase | OrganizeDoneSummary]`, through `openapi.json` and the generated
 *  types. `(ahn)` stage E: this was `Record<string, unknown>` - the cast that let generated types
 *  change without complaint - until 2026-09-03. This island still reads no field of it; `app.js`
 *  does, and adds `cancelled` on the way, which the wire never carries. */
type OrganizeSummary =
  | components["schemas"]["OrganizeDoneSummary"]
  | components["schemas"]["CompletionBase"];

/**
 * The four states `#org-result` can be in, as data rather than as twelve assignments.
 *
 * `complete` carries the SUMMARY rather than pre-rendered HTML, which is what gives the three
 * tests that used to write `innerHTML = organizeCompletion(s)` a props entry point. The other
 * three carry HTML because `app.js` already builds those cards with `card()`, and re-deriving
 * them here would be the rewrite this commit is avoiding.
 */
type ResultState =
  | { kind: "resting" }
  // The "Look inside" card, as DATA: the island draws it from `inventory.tsx` rather than
  // receiving a string. The first content here that React renders instead of injecting.
  | { kind: "inventory"; inventory: Inventory }
  // The dedup preview, as DATA plus the decisions `app.js` made about it (`PreviewView`); and
  // its empty outcome, chosen by `app.js` rather than by the island reading `files`.
  | { kind: "preview"; preview: PreviewSummary; view: PreviewView }
  | { kind: "preview-empty"; empty: PreviewEmpty }
  | { kind: "configured"; html: string }
  | { kind: "running"; html: string }
  // `complete` carries EITHER the summary - which is what gives the tests a props entry point
  // and lets the island call `organizeCompletion` itself - or an already-built card, for the
  // outcomes `app.js` renders directly (a job error, a run that found nothing). Four states, and
  // the second payload is a payload rather than a fifth kind.
  | { kind: "complete"; summary: OrganizeSummary; html?: undefined }
  | { kind: "complete"; html: string; summary?: undefined };

/** What `app.js` still owns. `organizeCompletion` is gone - the card is a component now - and
 *  the three that replaced it are each shared with a surface this island does not own:
 *  `outcomeWord` also titles the Backups card, `cleanupOfferNote` renders on four other paths,
 *  and `showScreen` is the shell's. */
interface AppGlobals {
  outcomeWord: (summary: OrganizeSummary) => string;
  cleanupOfferNote: (cleanup: unknown) => string;
  showScreen: (name: string) => void;
  solveResultGrid: (grid: HTMLElement) => void;
}

/** `app.js` is a classic script, so its functions are window globals. Narrowed at the boundary
 *  rather than trusted: `unknown` in, checked, then used. The escape hatch stays unused, and
 *  rewording this line rather than allow-listing the file is deliberate - an allow-list entry
 *  would blind the guard to a real one in the file most likely to acquire it. */
function appGlobals(): AppGlobals | null {
  const scope = window as unknown as Record<string, unknown>;
  const word = scope.outcomeWord;
  const cleanup = scope.cleanupOfferNote;
  const screen = scope.showScreen;
  const solve = scope.solveResultGrid;
  if (
    typeof word !== "function" ||
    typeof cleanup !== "function" ||
    typeof screen !== "function" ||
    typeof solve !== "function"
  ) {
    return null;
  }
  return {
    outcomeWord: word as AppGlobals["outcomeWord"],
    cleanupOfferNote: cleanup as AppGlobals["cleanupOfferNote"],
    showScreen: screen as AppGlobals["showScreen"],
    solveResultGrid: solve as AppGlobals["solveResultGrid"],
  };
}

/**
 * Lay out every row after the card is in the DOM, and again whenever its width changes.
 *
 * **This is what the MutationObserver was standing in for.** With one owner the grid arrives
 * when this component renders it, so the solver is called directly and the observer that watched
 * `#org-result` for arbitrary `innerHTML` writes is deleted.
 */
// ⚠ Takes the REF, not `ref.current`. Reading `.current` during render passes `null` - the
// node is not attached yet - and the effect then closes over that null and never runs the
// solver. The suite stayed green because the tests were still writing innerHTML directly;
// only the panorama guard noticed.
function useRowSolver(hostRef: React.RefObject<HTMLDivElement | null>): void {
  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    const app = appGlobals();
    if (!app) return;
    const grids = [...host.querySelectorAll<HTMLElement>(".result-grid")];
    if (!grids.length) return;

    for (const grid of grids) app.solveResultGrid(grid);
    const resized = new ResizeObserver((entries) => {
      for (const entry of entries) app.solveResultGrid(entry.target as HTMLElement);
    });
    for (const grid of grids) resized.observe(grid);
    return () => resized.disconnect();
  });
}

/** A card whose HTML `app.js` already built. `dangerouslySetInnerHTML` is honest here: the
 *  string is ours, and the alternative is re-deriving ten card shapes in JSX. */
function Card({ html }: { html: string }): React.JSX.Element {
  return <div dangerouslySetInnerHTML={{ __html: html }} />;
}

function OrganizeResult({ state }: { state: ResultState }): React.JSX.Element | null {
  const host = useRef<HTMLDivElement>(null);
  useRowSolver(host);

  if (state.kind === "resting") return null;
  if (state.kind === "inventory") {
    // The same depth as `Card` - host, wrapper, then `.card.result` - so the DOM is unchanged.
    return (
      <div ref={host}>
        <div>
          <InventoryCard s={state.inventory} />
        </div>
      </div>
    );
  }
  if (state.kind === "preview") {
    // The tree is a SECOND card, beside the preview rather than inside it, because it answers a
    // different question: the preview says what is in the folder, the tree says what the library
    // will look like afterwards. `app.js` never built this one, so there is no DOM to preserve.
    return (
      <div ref={host}>
        <div>
          <PreviewCard s={state.preview} view={state.view} />
          <DestinationTree
            tree={state.preview.destination_tree}
            label={state.view.destinationLabel}
          />
        </div>
      </div>
    );
  }
  if (state.kind === "preview-empty") {
    return (
      <div ref={host}>
        <div>
          <PreviewEmptyCard s={state.empty} />
        </div>
      </div>
    );
  }
  if (state.kind === "complete") {
    if (state.summary !== undefined) {
      const app = appGlobals();
      // Absent is said, not rendered as nothing - a blank card where the receipt should be is
      // the silence `(aer)` exists to prevent.
      if (!app) {
        throw new Error("app.js has not published its globals, so this run cannot be drawn.");
      }
      const seam: CompletionSeam = {
        outcomeWord: app.outcomeWord,
        cleanupOfferNote: app.cleanupOfferNote,
        showScreen: app.showScreen,
      };
      // The same depth as `Card` - host, wrapper, then `.card.result` - so the DOM is unchanged.
      return (
        <div ref={host}>
          <div>
            <CompletionCard r={state.summary as OrganizeDone} seam={seam} />
          </div>
        </div>
      );
    }
    return (
      <div ref={host}>
        <Card html={state.html} />
      </div>
    );
  }
  return (
    <div ref={host}>
      <Card html={state.html} />
    </div>
  );
}

/**
 * WHAT THE FORM SAYS, published by `app.js`.
 *
 * The action bar's summary has to name the mode and the destination, and no payload carries
 * either: they are the state of two controls `app.js` owns and reads at run time. So they are
 * pushed in rather than read out - `window.organizeResult.setForm(...)` - and the island stays
 * the one thing that renders. It never touches the DOM to find them, which is the rule that
 * stopped `#org-result` having twelve writers.
 */
export interface FormFacts {
  /** `copy` | `move` | `inplace`, the radio's own value. */
  mode: string;
  /** The destination path as typed. `""` until it has one. */
  destination: string;
}

interface IslandState {
  result: ResultState;
  form: FormFacts;
  /**
   * What Look inside found, CARRIED ACROSS the states that do not restate it.
   *
   * ⚠ The figures beside the folder field used to vanish the instant the run started, because
   * `running` and `complete` carry an html/summary payload and not the inventory, so the
   * extractor returned `null` and three numbers blinked out at the moment of most attention.
   * Nothing had changed about the folder; the island had simply stopped being told. Remembering
   * the last answer is the fix, and it is a memo rather than a second source: it is only ever
   * written from a state that carries the figures.
   */
  found: FoundInFolder | null;
}

interface FoundInFolder {
  photos: number;
  videos: number;
  bytes: number;
}

/**
 * ONE state, three roots.
 *
 * `#org-result`, `#org-stepper`, `#org-source-counts` and `#org-summary` are four separate nodes
 * in three separate parts of the page, and every one of them is a view of the SAME answer. A
 * second `useState` per root would be four states that can disagree - which is the defect this
 * island was created to remove, reintroduced at a larger scale. An external store with
 * `useSyncExternalStore` is the supported way to have one source and many subscribers, and it
 * also retires the `publish` capture below, which StrictMode's double render made fragile.
 */
function createStore(): {
  get: () => IslandState;
  subscribe: (listener: () => void) => () => void;
  setResult: (next: ResultState) => void;
  setForm: (next: FormFacts) => void;
} {
  let state: IslandState = {
    result: { kind: "resting" },
    form: { mode: "copy", destination: "" },
    found: null,
  };
  const listeners = new Set<() => void>();
  const emit = (): void => {
    for (const listener of [...listeners]) listener();
  };
  return {
    get: () => state,
    subscribe: (listener) => {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
    setResult: (next) => {
      state = { ...state, result: next, found: carryFound(state.found, next) };
      emit();
    },
    setForm: (next) => {
      state = { ...state, form: next };
      emit();
    },
  };
}

const store = createStore();

function useIsland(): IslandState {
  return useSyncExternalStore(store.subscribe, store.get, store.get);
}

// --------------------------------------------------------------------------------- the stepper

/** The four steps, in order. The labels are the maintainer's. */
const STEPS = ["Configure", "Preview", "Apply", "Done"] as const;

/**
 * WHICH STEP A RESULT STATE IS, and this is the whole of the stepper's logic.
 *
 * A PROJECTION, not a second state machine: every kind of `ResultState` maps onto exactly one
 * step, so the row cannot say "Preview" while the screen shows a finished run. `configured` has
 * no writer in `app.js` today and is mapped anyway - a kind that exists in the type and is
 * missing from this table would fall through to Configure and read as the screen going backwards.
 *
 * ⚠ **THE STEP IS WHERE THE PERSON IS, NOT WHICH PAYLOAD ARRIVED, and that distinction is the
 * fix of 2026-09-09.** `kind` alone put "Preview" on the row while the typed confirm was on
 * screen: `app.js` sets `preview` and, eight lines later, draws the control that STARTS THE RUN
 * from the same handler. Reading `kind` was reading the last response the server sent; the
 * question a stepper answers is what the reader is being asked to do. A tracker has to say what
 * is done, what is current and what is ahead, and it was calling the current step a finished one.
 *
 * ⚠ **`will_organize > 0` IS NOT A SECOND SOURCE OF TRUTH - it is the SAME expression the confirm
 * is drawn from.** `app.js` computes `kept = Number(s.will_organize) || 0` and renders
 * `renderOrganizeRunConfirm` if and only if `kept` is truthy. So this cannot disagree with the
 * screen: if the control is there, the step says Apply; if the preview came back with nothing to
 * organize, there is no control, no decision to make, and the step stays on Preview.
 */
function stepFor(state: ResultState): number {
  switch (state.kind) {
    case "resting":
      return 0;
    case "inventory":
      return 1;
    case "preview":
      // The typed confirm is up exactly when the run has files to take, so this IS the Apply
      // decision - the preview above it has already been read.
      return (Number(state.preview.will_organize) || 0) > 0 ? 2 : 1;
    case "preview-empty":
      return 1;
    case "configured":
    case "running":
      return 2;
    case "complete":
      return 3;
  }
}

function Stepper(): React.JSX.Element {
  const current = stepFor(useIsland().result);
  return (
    <ol className="stepper" data-testid="org-stepper">
      {STEPS.map((name, i) => {
        const state = i === current ? "current" : i < current ? "done" : "todo";
        return (
          <li
            className="step"
            data-step={name.toLowerCase()}
            data-state={state}
            aria-current={i === current ? "step" : undefined}
            key={name}
          >
            <span className="step-dot" aria-hidden="true">
              {i + 1}
            </span>
            <span className="step-name">{name}</span>
          </li>
        );
      })}
    </ol>
  );
}

// ------------------------------------------------------------------ the source field's counts

/** What Look inside found, from whichever state carries it. `null` before it has run. */
function foundInFolder(state: ResultState): FoundInFolder | null {
  const s =
    state.kind === "inventory"
      ? state.inventory
      : state.kind === "preview"
        ? state.preview
        : null;
  if (!s) return null;
  return {
    photos: Number(s.photos) || 0,
    videos: Number(s.videos) || 0,
    bytes: Number((s as { bytes?: number }).bytes) || 0,
  };
}

/**
 * WHAT THE FIGURES BESIDE THE FOLDER FIELD SHOULD SAY IN A STATE THAT DOES NOT RESTATE THEM.
 *
 * Three rules, and each is about whether the sentence is still TRUE rather than about polish:
 *
 * - **`resting`** clears. The screen has been invalidated - a field changed, or the result was
 *   thrown away - so the last answer describes a folder nobody is asking about now.
 * - **`running`** KEEPS them. Nothing about the folder has changed, the run is about exactly the
 *   set they describe, and this is the moment the reader is most likely to be looking. This is
 *   the blink the fix is for.
 * - **`complete`** CLEARS them, and this is the half worth arguing. The completion card below
 *   states what the run did, so leaving "1,204 photos · 88 videos" beside the field invites a
 *   comparison between two numbers taken at different moments - and after a MOVE or an in-place
 *   run the source folder no longer holds them at all, so the figure is not stale, it is false.
 *   A count that may be a false statement about the folder it names is worse than no count.
 */
function carryFound(previous: FoundInFolder | null, next: ResultState): FoundInFolder | null {
  const fresh = foundInFolder(next);
  if (fresh) return fresh;
  return next.kind === "running" ? previous : null;
}

/**
 * Photos, videos and size beside the folder field.
 *
 * ⚠ NOTHING AT REST, and that is the requirement rather than a nicety. Zeros here would be three
 * confident figures about a folder nothing has opened, which is the class
 * `test_the_resting_screen_invents_no_metrics` exists to refuse - and it asserts on `.metric`,
 * which is what this renders, so that test is this one's guard too.
 */
function SourceCounts(): React.JSX.Element | null {
  // The CARRIED answer, not the live one: `carryFound` is what keeps these three from blinking
  // out when the run starts, and what clears them when the run is over.
  const found = useIsland().found;
  if (!found) return null;
  const { nfmt, fmtBytes } = formatters();
  const figures: [number | string, string][] = [
    [nfmt(found.photos), found.photos === 1 ? "photo" : "photos"],
    [nfmt(found.videos), found.videos === 1 ? "video" : "videos"],
  ];
  if (found.bytes) figures.push([fmtBytes(found.bytes), "on disk"]);
  return (
    <div className="source-counts" data-testid="org-source-counts">
      {figures.map(([value, label]) => (
        <div className="metric" key={label}>
          <div className="metric-value">{value}</div>
          <div className="metric-label">{label}</div>
        </div>
      ))}
    </div>
  );
}

// ------------------------------------------------------------------------------ the action bar

const MODE_WORD: { [mode: string]: string } = {
  copy: "Copy",
  move: "Move",
  inplace: "Reorganize in place",
};

/** The folder's own name, the same reading `previewView`'s `destinationLabel` takes. */
function folderName(path: string): string {
  const trimmed = path.replace(/[\\/]+$/, "");
  if (!trimmed) return "";
  const parts = trimmed.split(/[\\/]/);
  return parts[parts.length - 1] || trimmed;
}

/**
 * ONE LINE SAYING WHAT IS ABOUT TO HAPPEN: `Copy · 412 files → Truestill`.
 *
 * **It fills in as the form fills in, and it never states a part it does not have.** A summary
 * that printed "0 files" before Look inside, or the word "destination" where a folder name goes,
 * would be the screen making a promise out of a blank field - the same defect as the counts
 * above, one line to the right. The mode is always known, so the line always has a first clause;
 * everything after it appears when it is true.
 *
 * ⚠ **NO SIZE, AND THE SIZE IS NOT COMING BACK AS A PAYLOAD FIELD.** This line used to read
 * `Copy · 400 files · 3.2 GB` where the COUNT came from `will_organize` - the files the run will
 * actually take - and the BYTES came from `foundInFolder`, the inventory's total for the whole
 * folder. On a run with duplicates those are two different sets, stated six pixels apart in one
 * sentence, and the reader has no way to see that they are. `(abl)` is what this repo already
 * pays when two surfaces derive one quantity separately; this was one surface doing it to itself.
 *
 * Dropped rather than fixed. The alternative was a "bytes the run will write" field on the
 * preview payload, which does not exist today - and adding one means the payload, `openapi.json`
 * and the frozen oracle pair regenerated to put a decoration back on a line that reads correctly
 * without it. **The count is the number that matters beside a button that starts a run**; the
 * size is available in full in the preview card directly above.
 */
function ActionSummary(): React.JSX.Element | null {
  const { result, form } = useIsland();
  const { nfmt, plural } = formatters();
  const found = foundInFolder(result);
  const destination = form.mode === "inplace" ? "" : folderName(form.destination);
  const parts: React.ReactNode[] = [<b key="mode">{MODE_WORD[form.mode] ?? MODE_WORD.copy}</b>];
  if (result.kind === "preview") {
    // The number the run will actually take, not the number in the folder: this line sits beside
    // the button that starts it, and `(abl)` is what happens when two surfaces derive that
    // separately. `will_organize` is the field both the tally and the confirm already render.
    parts.push(<span key="n">{plural(Number(result.preview.will_organize) || 0, "file")}</span>);
  } else if (found) {
    parts.push(<span key="n">{nfmt(found.photos + found.videos)} files</span>);
  }
  return (
    <div className="org-summary" data-testid="org-summary">
      {parts.map((part, i) => (
        <span key={i}>
          {i ? <span className="sep">·</span> : null}
          {part}
        </span>
      ))}
      {destination ? (
        <span>
          <span className="sep">→</span>
          <b>{destination}</b>
        </span>
      ) : null}
    </div>
  );
}

// --------------------------------------------------------------------------------------- mount

/** Render one projection into its node, when the page has that node. */
function mountAt(id: string, view: React.JSX.Element): void {
  const node = document.getElementById(id);
  if (!node) return;
  createRoot(node).render(<StrictMode>{view}</StrictMode>);
}

function OrganizeResultIsland(): React.JSX.Element | null {
  return <OrganizeResult state={useIsland().result} />;
}

document.documentElement.dataset.bundle = __BUNDLE_SOURCE_HASH__;

// The reverse seam: the blocks the island owns, as strings for the `app.js` builders that still
// compose HTML - the completion card (chips, legend), the Import preview (match lists, date
// notes) and Backups' drive list (by-format). Published before the island mounts so no click can
// find it absent. Each entry disappears when its last string consumer becomes a component.
const markup = {
  byFormat: (bf: ByFormatCounts | null | undefined): string => toHtml(<ByFormat bf={bf} />),
  matchList: (report: Parameters<typeof MatchList>[0]["report"], label: string): string =>
    toHtml(<MatchList report={report} label={label} />),
  dateQuality: (s: DateQualityCounts): string => toHtml(<DateQualityNotes s={s} />),
  inferredShifts: (s: InferredShifts): string => toHtml(<InferredShiftNote s={s} />),
};
(window as unknown as Record<string, unknown>).truestillMarkup = markup;

mountAt("org-result", <OrganizeResultIsland />);
mountAt("org-stepper", <Stepper />);
mountAt("org-source-counts", <SourceCounts />);
mountAt("org-summary", <ActionSummary />);

// The seam `app.js` and the e2e suite drive. Named on `window` because `app.js` is a classic
// script and cannot import a module. `set` is unchanged and is still the only way the result
// region is written; `setForm` is the second, smaller channel the action bar's summary needs.
(window as unknown as Record<string, unknown>).organizeResult = {
  set: store.setResult,
  setForm: store.setForm,
};
