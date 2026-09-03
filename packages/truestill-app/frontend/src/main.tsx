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

import { StrictMode, useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";

import type { components } from "./generated/api";

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
  | { kind: "configured"; html: string }
  | { kind: "running"; html: string }
  // `complete` carries EITHER the summary - which is what gives the tests a props entry point
  // and lets the island call `organizeCompletion` itself - or an already-built card, for the
  // outcomes `app.js` renders directly (a job error, a run that found nothing). Four states, and
  // the second payload is a payload rather than a fifth kind.
  | { kind: "complete"; summary: OrganizeSummary; html?: undefined }
  | { kind: "complete"; html: string; summary?: undefined };

interface AppGlobals {
  organizeCompletion: (summary: OrganizeSummary) => string;
  solveResultGrid: (grid: HTMLElement) => void;
}

/** `app.js` is a classic script, so its functions are window globals. Narrowed at the boundary
 *  rather than trusted: `unknown` in, checked, then used. The escape hatch stays unused, and
 *  rewording this line rather than allow-listing the file is deliberate - an allow-list entry
 *  would blind the guard to a real one in the file most likely to acquire it. */
function appGlobals(): AppGlobals | null {
  const scope = window as unknown as Record<string, unknown>;
  const completion = scope.organizeCompletion;
  const solve = scope.solveResultGrid;
  if (typeof completion !== "function" || typeof solve !== "function") return null;
  return {
    organizeCompletion: completion as AppGlobals["organizeCompletion"],
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
  if (state.kind === "complete") {
    const app = appGlobals();
    const html =
      state.summary !== undefined ? (app ? app.organizeCompletion(state.summary) : "") : state.html;
    return (
      <div ref={host}>
        <Card html={html} />
      </div>
    );
  }
  return (
    <div ref={host}>
      <Card html={state.html} />
    </div>
  );
}

/** The one writer of `#org-result`. `app.js` calls `set(...)`; nothing else touches the node. */
function mount(node: HTMLElement): { set: (next: ResultState) => void } {
  let publish: ((next: ResultState) => void) | null = null;

  function Island(): React.JSX.Element | null {
    const [state, setState] = useState<ResultState>({ kind: "resting" });
    publish = setState;
    return <OrganizeResult state={state} />;
  }

  const root = createRoot(node);
  root.render(
    <StrictMode>
      <Island />
    </StrictMode>,
  );
  return {
    set: (next: ResultState) => {
      if (publish) publish(next);
    },
  };
}

document.documentElement.dataset.bundle = __BUNDLE_SOURCE_HASH__;

const target = document.getElementById("org-result");
if (target) {
  const island = mount(target);
  // The seam `app.js` and the e2e suite drive. Named on `window` because `app.js` is a classic
  // script and cannot import a module.
  (window as unknown as Record<string, unknown>).organizeResult = island;
}
