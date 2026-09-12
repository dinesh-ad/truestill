/**
 * The completion card, drawn by the island - the third slice of `#org-result`.
 *
 * **What this replaces.** `organizeCompletion`, `resultGrid`, `toggleResultGrid`,
 * `leftInSourceNote`, `spanStory` and `yearOf`, all deleted from `app.js` in the same commit.
 * Every class, `data-testid`, attribute and sentence is reproduced; the unchanged e2e suite is
 * the referee and a visual delta here is a bug.
 *
 * **No decision moved.** Three things the card needs are still decided in `app.js` and arrive
 * through :interface:`CompletionSeam`, because each is shared with a surface this island does not
 * own: `outcomeWord` also titles the Backups card, `cleanupOfferNote` renders on four other
 * paths, and `showScreen` is the shell's. `completionCard` itself stays in `app.js` for the same
 * reason - Backups builds its card with it - so this file rebuilds that shape rather than
 * importing it, and the two are held together by the suite rather than by a shared function.
 *
 * ⚠ **`GRID_SAMPLE_LIMIT` AND THE 48-IN-RUN-ORDER CHOICE ARE PYTHON AND STAY THERE.** Nothing
 * here reselects, reorders, filters or caps anything: `shown` is rendered in the order the
 * payload lists it, and `total` is printed as the payload states it. The one client-side
 * threshold is `GRID_COLLAPSE_ABOVE`, which decides whether a *toggle* is offered and never
 * which photographs exist.
 *
 * **The toggle is React state now, not a class swap through a global.** `toggleResultGrid` was
 * reached by an inline `onclick` attribute and mutated `classList` and the button's text behind
 * React's back. The collapsed flag lives in `useState` here, so the rendered DOM and the truth
 * agree. The row solver still writes `height`/`width` onto the tiles and `--first-row-height`
 * onto the grid directly; no `style` prop is passed for those, so React does not manage or
 * clobber them.
 */

import { useState } from "react";

import type { components } from "./generated/api";
import { formatters } from "./inventory";
import { Chips, Legend, type FolderCounts } from "./preview";

/** ⚠ `cancelled` is NOT on the wire. `app.js` adds it to the summary before handing it over
 *  (`onCancelled` in `startOrganizeRun`), so the generated type is widened here rather than the
 *  contract being edited to describe a field the server never sends. */
export type OrganizeDone = components["schemas"]["OrganizeDoneSummary"] & {
  cancelled?: boolean;
};
export type CompletionSummary = OrganizeDone | components["schemas"]["CompletionBase"];

/** The three things `app.js` still owns, handed over rather than re-implemented. */
export interface CompletionSeam {
  /** The word at the top of the card, from the run's own verdict. `(aiq)`. Shared with Backups. */
  outcomeWord: (r: CompletionSummary) => string;
  /** The empty-folder offer. Rendered on four other paths, so it stays a string builder. */
  cleanupOfferNote: (cleanup: unknown) => string;
  /** The shell's navigation. */
  showScreen: (name: string) => void;
}

//: One row's worth of tiles at the widest panel the layout produces (936px inner / 148px + gap).
//: Below this a grid physically cannot push the warnings off-screen, and a "show all 3" under
//: three photos is the kind of noise that teaches people to stop reading controls.
const GRID_COLLAPSE_ABOVE = 6;

/** `window.TRUESTILL_TOKEN`, the same value `app.js` reads on its first line. */
function token(): string {
  return String((window as unknown as { TRUESTILL_TOKEN?: string }).TRUESTILL_TOKEN ?? "");
}

const yearOf = (iso: string | null | undefined): string | null =>
  iso ? String(new Date(iso).getFullYear()) : null;

/** The capture range, or null for an undated batch - no range exists to tell. */
function spanStory(r: OrganizeDone): string | null {
  const from = yearOf(r.oldest);
  const to = yearOf(r.newest);
  if (!from) return null;
  return from === to ? `all from ${from}` : `spanning ${from} – ${to}`;
}

type Sample = NonNullable<OrganizeDone["organized_sample"]>;

/**
 * Photos, addressed by content hash through `/api/thumb/{sha256}`.
 *
 * LAZY, NOT BATCHED, and that was decided before the grid was built rather than discovered
 * after. A browser opens at most 6 connections per host on HTTP/1.1 (8 in Firefox), and uvicorn
 * here is HTTP/1.1, so forty-eight tiles requested at once queue six at a time. A batch endpoint
 * defeats per-thumbnail HTTP caching and puts the whole grid behind the slowest decode; data:
 * URIs cost fourfold base64 on a payload that is otherwise counts. `loading="lazy"` spends the
 * six-connection window on tiles a person is looking at.
 *
 * `decoding="async"` keeps the decode off the main thread. Explicit width/height give the tile
 * its aspect before the bytes land, so the grid does not reflow as images arrive.
 */
function ResultGrid({ sample }: { sample: Sample | null | undefined }): React.JSX.Element | null {
  const { nfmt, plural } = formatters();
  const [collapsed, setCollapsed] = useState(true);
  const shown = sample?.shown ?? [];
  if (!shown.length) return null;
  const total = sample?.total || shown.length;
  const collapsible = shown.length > GRID_COLLAPSE_ABOVE;
  const isCollapsed = collapsible && collapsed;
  return (
    <>
      <div
        className={`result-grid${isCollapsed ? " is-collapsed" : ""}`}
        data-testid="org-grid"
        data-total={total}
        data-shown={shown.length}
      >
        {shown.map((t) => (
          <img
            className="tile"
            key={t.sha256}
            loading="lazy"
            decoding="async"
            width={t.w || 1}
            height={t.h || 1}
            src={`/api/thumb/${encodeURIComponent(t.sha256)}?token=${encodeURIComponent(token())}`}
            alt={t.name}
            title={t.name}
          />
        ))}
      </div>
      {/* A real <button> with aria-expanded, not a styled div: this shows and hides content,
          which is exactly what that element and that attribute are for. */}
      {collapsible ? (
        <button
          type="button"
          className="btn grid-toggle"
          aria-expanded={!collapsed}
          onClick={() => setCollapsed((was) => !was)}
        >
          {collapsed ? `Show all ${nfmt(shown.length)} photos` : "Show fewer"}
        </button>
      ) : null}
      {/* Truncation is stated, never implied - the same rule the duplicate and unreadable lists
          obey. A grid quietly showing 48 of 200 reads as "this is what you organized". */}
      {total > shown.length ? (
        <div className="k grid-more">
          Showing {nfmt(shown.length)} of {plural(total, "photo")}.
        </div>
      ) : null}
    </>
  );
}

/** A collapsed per-file list, stated rather than implied. Shared by the failure and the
 *  metadata notes, which print the same shape over different fields. */
export function NamedFiles({
  files,
}: {
  files: { total: number; shown?: { name: string; detail: string }[] } | null | undefined;
}): React.JSX.Element | null {
  const { nfmt, plural } = formatters();
  const shown = files?.shown ?? [];
  if (!files || !shown.length) return null;
  return (
    <details className="more">
      <summary>Show which &#9662;</summary>
      <div className="mono">
        {shown.map((x, i) => (
          <span key={i}>
            {i ? <br /> : null}
            {x.name} - {x.detail}
          </span>
        ))}
      </div>
      {files.total > shown.length ? (
        <div className="k">
          Showing {nfmt(shown.length)} of {plural(files.total, "file")}.
        </div>
      ) : null}
    </details>
  );
}

/**
 * WHAT THE MOVE LEFT. A move skips a file already in the library and never touches its original -
 * right, and it was silent, so the source came back PARTIALLY emptied with no explanation for the
 * files still in it. The sentence names the folder because "3 files remain" is weaker than
 * "3 files remain in D/E", and the payload carries the folder.
 *
 * The wording mirrors `truestill_core.left_behind.describe_left_behind`, which the CLI prints;
 * `tests/e2e/test_the_move_says_what_it_left.py` pins these words, per §9.
 */
function LeftInSourceNote({
  left,
}: {
  left: OrganizeDone["left_in_source"];
}): React.JSX.Element | null {
  const { nfmt, plural } = formatters();
  if (!left || !left.total) return null;
  const folders = left.folders ?? [];
  const named = (f: { folder?: string | null }) => f.folder || "the folder you selected";
  const hidden = (left.folders_total || folders.length) - folders.length;
  // The bare "in D/E" reads best, and is only honest when D/E is the whole story - one folder
  // AND nothing cut by the cap. Otherwise the counted list, which admits what it left out.
  const only = folders.length === 1 && hidden <= 0 ? folders[0] : undefined;
  const where = only
    ? `in ${named(only)}`
    : `in ${folders.map((f) => `${named(f)} (${nfmt(f.files)})`).join(", ")}` +
      (hidden > 0 ? `, and ${nfmt(hidden)} more folders` : "");
  const head = `${plural(left.total, "file")} ${left.total === 1 ? "remains" : "remain"} ${where}`;
  // With both reasons present no single "because" clause is true of every file, so the sentence
  // stops claiming one and states the split instead - the same rule the CLI follows.
  interface Reason {
    n: number;
    because: string;
    counted: string;
  }
  const reasons: Reason[] = [
    {
      n: left.already_in_library,
      because: "they were already in your library",
      counted: `${nfmt(left.already_in_library)} already in your library`,
    },
    {
      n: left.within_this_batch,
      because: "an identical file from this batch was moved instead",
      counted: `${nfmt(left.within_this_batch)} matched another file earlier in this batch`,
    },
    {
      n: left.unclassified,
      because: "they matched a file recorded somewhere this build does not name",
      counted: `${nfmt(left.unclassified)} matched a file recorded somewhere this build does not name`,
    },
  ].filter((r) => Number(r.n) > 0);
  const single = reasons.length === 1 ? reasons[0] : undefined;
  const body = single
    ? `${head} because ${single.because}.`
    : `${head}. Of those, ${reasons.map((r) => r.counted).join("; ")}.`;
  return (
    <div className="banner warn" data-testid="org-left-in-source">
      <div>
        <div className="b-title">Not everything was moved</div>
        <div>{body} Nothing of yours was deleted.</div>
      </div>
    </div>
  );
}

/** A note whose HTML `app.js` still builds. Honest here: the string is ours, and the alternative
 *  is porting a builder four other paths render. */
function HtmlNote({ html }: { html: string }): React.JSX.Element | null {
  if (!html) return null;
  return <div dangerouslySetInnerHTML={{ __html: html }} />;
}

/**
 * The finished run.
 *
 * `grid` sits ABOVE the numbers, and that ordering is the point rather than a layout preference:
 * this is a photo organizer, and the payoff for organizing photos should be the photos. The tally
 * reads as what it is - supporting detail - once something is above it. Nothing sits between the
 * headline and the photographs; every count appears as one line beneath them.
 */
export function CompletionCard({
  r,
  seam,
}: {
  r: OrganizeDone;
  seam: CompletionSeam;
}): React.JSX.Element {
  const { nfmt, plural, fmtBytes, fmtDuration } = formatters();
  const moved = (r.moved_in_place || 0) + (r.moved_by_copy || 0);
  const verb = moved && !r.organized ? "moved" : "organized";
  const kinds = [
    r.photos ? plural(r.photos, "photo") : "",
    r.videos ? plural(r.videos, "video") : "",
    r.audio ? `${nfmt(r.audio)} audio` : "",
  ]
    .filter(Boolean)
    .join(" · ");
  // SIX FACTS AS FIGURES, not one run-on line. Each is a value and a label, so the eye can find
  // "how much" without reading a sentence - and the block stays the muted CAPTION the card's own
  // test argues for, positioned after the photographs. It is deliberately NOT `.tally`, the
  // two-column block `test_the_grid_is_the_result` forbids above the grid: the photographs are
  // the result and these are what they cost.
  const facts: [string, string][] = [
    [String(r.organized || 0), plural(r.organized || 0, "file").replace(/^[\d,]+\s/, "")],
    [kinds, ""],
    [spanStory(r) ?? "", ""],
    [r.bytes_organized ? fmtBytes(r.bytes_organized) : "", "organized"],
    [
      r.duplicates ? fmtBytes(r.bytes_saved) : "",
      r.duplicates ? `saved, ${plural(r.duplicates, "duplicate")} skipped` : "",
    ],
    [r.elapsed_seconds ? fmtDuration(r.elapsed_seconds) : "", "taken"],
  ].filter(([value]) => value) as [string, string][];
  const folders = (r.folders || {}) as FolderCounts;
  const hasFolders = Object.keys(folders).length > 0;
  const cleanup = r.leftover_empty_folders?.count
    ? seam.cleanupOfferNote(r.leftover_empty_folders)
    : "";

  return (
    <div className="card result">
      <div className="done-mark">{seam.outcomeWord(r)}</div>
      <div className="headline">
        {plural(r.organized || 0, "file")} {verb}
        {r.cancelled ? " before you stopped it" : ""}
      </div>
      <ResultGrid sample={r.organized_sample} />
      {facts.length ? (
        <div className="k result-numbers">
          {facts.map(([value, label], i) => (
            <span className="result-fact" key={i}>
              <b>{value}</b>
              {label ? ` ${label}` : ""}
            </span>
          ))}
        </div>
      ) : null}

      {/* ⚠ VIDEOS ARE ORGANIZED AND CANNOT BE DRAWN. `thumbnails.render` is PIL, so an MP4 has no
          tile and the card used to say "42 videos" above a grid containing none of them - the
          count promising something the picture then denied. This is not a thumbnail and does not
          pretend to be: it is a counted row that says the videos are there and that no preview
          exists yet. Building video thumbnailing is a different feature. */}
      {r.videos ? (
        <div className="k video-row" data-testid="org-videos">
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
            focusable="false"
          >
            <rect x="2" y="5" width="14" height="14" rx="2" />
            <path d="m22 8-6 4 6 4V8Z" />
          </svg>
          <span>
            {plural(r.videos, "video")} organized. Videos have no preview yet.
          </span>
        </div>
      ) : null}
      {/* WHERE DID MY PHOTOS GO. After a bulk move this is the question people actually ask, and
          this card is the only place it is answered - so the chips carry weight rather than
          trailing the card as a footnote. */}
      {hasFolders ? (
        <div className="result-folders">
          <h3>Into these folders</h3>
          <div className="chips">
            <Chips folders={folders} />
          </div>
          <Legend folders={folders} />
        </div>
      ) : null}

      {r.near_dup ? (
        <div className="banner warn">
          <div>
            {plural(r.near_dup, "look-alike")} flagged for review - {fmtBytes(r.bytes_near_dup)} if
            you decide to remove them. They were kept, not dropped.
          </div>
        </div>
      ) : null}

      {r.moved_in_place ? (
        <div className="banner">
          <div>
            {nfmt(r.moved_in_place)} moved by rename on the drive (no bytes copied). Undo with{" "}
            <code>truestill undo-organize</code>.
          </div>
        </div>
      ) : null}

      {r.single_copy ? (
        <div className="banner warn">
          <div>
            {plural(r.single_copy, "file")} now exist in only one place.{" "}
            <a
              href="#"
              onClick={(e) => {
                e.preventDefault();
                seam.showScreen("backups");
              }}
            >
              Make it safe in 2 places
            </a>
            .
          </div>
        </div>
      ) : null}

      {/* `(ajl)`. The count was the WHOLE message until 2026-09-01: a run that failed 1,130 of
          1,324 files said "1,130 files could not be organized." and named none of them, while the
          CLI has named up to `models.FAILURE_PREVIEW_LIMIT` of them since `(afd)`. Never a flat
          failure that hides which files, never a flat success that hides them either. Collapsed
          by default, and truncation stated: twenty filenames are detail, not the headline. */}
      {r.failed ? (
        <div className="banner warn">
          <div>
            {plural(r.failed, "file")} could not be {verb}.
            <NamedFiles files={r.failed_files} />
          </div>
        </div>
      ) : null}

      {/* `(ajn)`. Copied and safe, but the drive refused timestamps or permissions - the CLI has
          said this under METADATA NOT SET since `(aie)`, and the app said nothing: 2,519 files in
          one real run landed with today's date behind "organized". */}
      {r.metadata_files?.total ? (
        <div className="banner warn" data-testid="org-metadata-not-set">
          <div>
            {plural(r.metadata_files.total, "file")}{" "}
            {r.metadata_files.total === 1 ? "was" : "were"} copied and{" "}
            {r.metadata_files.total === 1 ? "is" : "are"} safe, but this drive did not let Truestill
            set {r.metadata_files.total === 1 ? "its" : "their"} timestamps or permissions - a file
            manager will show today&#39;s date on{" "}
            {r.metadata_files.total === 1 ? "it" : "them"}.
            <NamedFiles files={r.metadata_files} />
          </div>
        </div>
      ) : null}

      {/* ⚠ The run WORKED and its record did not. Said because the record is automatic, so a user
          never asked for it and would never know it was missing - which is what makes its absence
          the news rather than the file. The CLI prints the same fact; one wording, two surfaces.
          `(afu)` */}
      {r.record_error ? (
        <div className="banner warn">
          <div>This run is not written down: {r.record_error}</div>
        </div>
      ) : null}

      {/* BEFORE the cleanup offer, deliberately. The offer names the folders the move emptied and
          is silent about the ones it did not (`plan_cleanup` drops anything OCCUPIED), so reading
          it first leaves a person thinking the source is now tidy while their photos sit in it. */}
      <LeftInSourceNote left={r.left_in_source} />
      <HtmlNote html={cleanup} />
    </div>
  );
}
