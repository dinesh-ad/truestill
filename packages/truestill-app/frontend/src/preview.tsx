/**
 * Organize's dedup preview card, rendered as components - the second slice of `#org-result`.
 *
 * **Same DOM as the `app.js` strings it replaces** (`renderOrganizeResult`, `organizeTally`,
 * `dupOrigins`, `willRemainNote`, `rearrangeNote`, `rearrangeWhere`, `matchListHtml`,
 * `dateQualityNotes`, `inferredLocalShiftNotes`, `chipsFor`, `legendFor`, all deleted in the same
 * commit): every class, `data-testid`, `data-*` hook and sentence is reproduced. The unchanged
 * e2e suite is the referee.
 *
 * **No decision is made here.** The card is handed `PreviewView`, which `app.js` computes: whether
 * undated files are being skipped (a form read), and what the "already in your library" line is -
 * nothing, a "stays" line, or the rearrange pointer with the one path it may offer. The ratio and
 * floor behind that pointer, `pointsAtRearranging`, stay in `app.js` with their reasoning, as does
 * the `!s.files` branch that chooses `NothingHereCard` and the `will_organize` gate that decides
 * whether the typed confirm renders at all.
 *
 * **What this file shares.** The match list, the date-quality notes, the inferred-shift note and
 * the folder chips with their legend are also drawn by the Import screen and the completion card,
 * which still compose strings; `markup` in `inventory.tsx` hands them the same components as
 * strings. `catTip` stays in `app.js` - the folder vocabulary has one home - and is read back
 * through the formatters seam.
 */

import { Fragment } from "react";

import type { components } from "./generated/api";
import { NothingHereCard, UnreadableBanner, ByFormat, SkippedDetails, formatters } from "./inventory";

export type PreviewSummary = components["schemas"]["OrganizePreviewSummary"];
export type PreviewEmpty = components["schemas"]["OrganizePreviewEmpty"];
type DuplicateReport = components["schemas"]["DuplicateReport"];
type MatchedDrive = components["schemas"]["MatchedDrivePayload"];

/** The decisions `app.js` makes before the card is drawn. */
export interface PreviewView {
  skippingUndated: boolean;
  already:
    | { kind: "none" }
    | { kind: "stays"; n: number }
    | { kind: "rearrange"; n: number; moving: boolean; path: string };
  /** The destination folder's own name, so the promise says where; "" when unknown. */
  destinationLabel: string;
  /** The library already holds these files AND this run will write them here - both true. */
  copiesAgain: boolean;
}

/** The fields the date-quality notes read; the Import preview carries the same three. */
export interface DateQualityCounts {
  future_rejected?: number;
  sentinel_rejected?: number;
  suspect_default?: number;
}
export interface InferredShifts {
  inferred_local_shifts?: { line?: string; name: string }[] | null;
}
export type FolderCounts = { [key: string]: number };

export function DateQualityNotes({ s }: { s: DateQualityCounts }): React.JSX.Element | null {
  const { plural } = formatters();
  const notes: React.JSX.Element[] = [];
  if (s.future_rejected) {
    notes.push(
      <div key="future">
        {plural(s.future_rejected, "file")} claimed a date in the future, so it was refused and they
        went to <span className="mono">Undated/</span>. That usually means a wrong camera clock or
        edited details; the original date cannot be recovered.
      </div>,
    );
  }
  if (s.sentinel_rejected) {
    notes.push(
      <div key="sentinel">
        {plural(s.sentinel_rejected, "file")} carried only a placeholder date (an all-zero “epoch”
        timestamp). It was refused, so they went to “Undated” rather than being filed under 1904
        or 1970.
      </div>,
    );
  }
  if (s.suspect_default) {
    notes.push(
      <div key="suspect">
        {plural(s.suspect_default, "file")} dated exactly midnight on a day cameras fall back to
        when their clock battery dies. They are filed by that date - it may well be right - but
        they are worth a look.
      </div>,
    );
  }
  return notes.length ? <div className="banner warn">{notes}</div> : null;
}

/** Informational: videos whose UTC CreateDate was shifted to local. Names and offsets, not a
 *  count alone. */
export function InferredShiftNote({ s }: { s: InferredShifts }): React.JSX.Element | null {
  const shifts = s.inferred_local_shifts ?? [];
  if (!shifts.length) return null;
  return (
    <div className="banner">
      <div>
        {formatters().plural(shifts.length, "video")} shifted from UTC CreateDate:
        <div style={{ marginTop: "var(--space-2)" }}>
          {shifts.map((x, i) => (
            <div className="mono" key={i}>
              {x.line || x.name}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export function MatchList({
  report,
  label,
}: {
  report: DuplicateReport | null | undefined;
  label: string;
}): React.JSX.Element | null {
  if (!report || !report.total) return null;
  const { nfmt } = formatters();
  const shown = report.shown ?? [];
  const hidden = report.total - shown.length;
  const heading = hidden
    ? `${label} (first ${nfmt(shown.length)} of ${nfmt(report.total)})`
    : `${label} (${nfmt(report.total)})`;
  return (
    <details className="more">
      <summary>{heading}</summary>
      <div className="k">
        {shown.map((m, i) => (
          <div key={i}>
            <span className="mono">{m.name}</span> - {m.detail}
          </div>
        ))}
      </div>
      {hidden ? <div className="k">…and {nfmt(hidden)} more</div> : null}
    </details>
  );
}

/** Folder chips. Shared with the completion card so the same folders are always described the
 *  same way; the description is `catTip`'s, which lives in `app.js`. */
export function Chips({ folders }: { folders: FolderCounts | null | undefined }): React.JSX.Element {
  const { nfmt, catTip } = formatters();
  return (
    <>
      {Object.entries(folders ?? {}).map(([k, v]) => (
        <span className="chip" title={catTip(k)} key={k}>
          {k} <span className="num">{nfmt(v)}</span>
        </span>
      ))}
    </>
  );
}

/** The first-timer legend under the chips. `(ahw)`: a VOCABULARY lookup, not a population
 *  filter - every folder gets a line, and a name `CAT_INFO` does not know gets `catTip`'s
 *  default rather than being dropped. */
export function Legend({ folders }: { folders: FolderCounts | null | undefined }): React.JSX.Element | null {
  const { catTip } = formatters();
  const names = Object.keys(folders ?? {});
  if (!names.length) return null;
  return (
    <div
      className="k"
      style={{ fontSize: "var(--type-xs)", marginTop: "var(--space-2)", lineHeight: 1.6 }}
    >
      {names.map((n, i) => (
        <Fragment key={n}>
          {i ? <br /> : null}
          <b>{n}</b> - {catTip(n)}
        </Fragment>
      ))}
    </div>
  );
}

function dupOrigins(report: DuplicateReport | null | undefined): string {
  if (!report) return "";
  const { nfmt } = formatters();
  const parts: string[] = [];
  if (report.already_in_library) parts.push(`${nfmt(report.already_in_library)} already in your library`);
  if (report.within_this_batch) parts.push(`${nfmt(report.within_this_batch)} earlier in this batch`);
  if (report.unclassified) parts.push(`${nfmt(report.unclassified)} matched elsewhere`);
  return parts.join(", ");
}

const REACH_NOTE: { [reach: string]: string } = {
  offline: " (not plugged in)",
  unknown: " (location not known yet)",
};

/** Where the matched files ACTUALLY are. Reach is three-valued and stays that way: "not plugged
 *  in" is not "gone", and "never seen on this computer" is neither. */
function rearrangeWhere(drives: MatchedDrive[]): string {
  if (!drives.length) return "";
  const { nfmt } = formatters();
  const named = drives.slice(0, 2).map((d) => d.label);
  const rest = drives.length - named.length;
  const list = named.join(" and ") + (rest > 0 ? `, and ${nfmt(rest)} more` : "");
  const first = drives[0];
  const state = drives.length === 1 && first ? (REACH_NOTE[first.reach] ?? "") : "";
  return ` on ${list}${state}`;
}

function RearrangeNote({
  s,
  n,
  moving,
  path,
  view,
}: {
  s: PreviewSummary;
  n: number;
  moving: boolean;
  path: string;
  view: PreviewView;
}): React.JSX.Element {
  const { nfmt } = formatters();
  const drives = s.matched_drives?.drives ?? [];
  return (
    <div className="banner" data-testid="org-rearrange">
      <div>
        <div className="b-title">These are already organized</div>
        <div>
          {nfmt(n)} of {nfmt(Number(s.files) || 0)} files here are already in your library
          {rearrangeWhere(drives)}. Organizing this folder again will not change how they are
          arranged.{moving ? " They stay where they are." : ""}
          {view.copiesAgain
            ? ` Organizing into ${view.destinationLabel || "this folder"} copies them again.`
            : ""}
        </div>
        <div>
          To arrange your library differently - by year, by month, by event - rearrange it where it
          is, without re-copying anything.
        </div>
        {drives.length ? (
          <div className="actions">
            <button className="btn btn-secondary" type="button" data-rearrange-go="" data-path={path}>
              Rearrange my library
            </button>
          </div>
        ) : null}
      </div>
    </div>
  );
}

function AlreadyNote({ s, view }: { s: PreviewSummary; view: PreviewView }): React.JSX.Element | null {
  const a = view.already;
  if (a.kind === "none") return null;
  if (a.kind === "rearrange")
    return <RearrangeNote s={s} n={a.n} moving={a.moving} path={a.path} view={view} />;
  const { nfmt } = formatters();
  const subject = a.n === 1 ? "file here is" : "files here are";
  const stays = a.n === 1 ? "It stays where it is." : "They stay where they are.";
  return (
    <div className="k" data-testid="org-will-remain">
      {nfmt(a.n)} {subject} already in your library and will not be moved. {stays}
    </div>
  );
}

function Tally({ s, view }: { s: PreviewSummary; view: PreviewView }): React.JSX.Element {
  const { nfmt, plural } = formatters();
  const unreadable = s.unreadable_files?.total ?? 0;
  const origins = dupOrigins(s.exact_dup_matches);
  // Neither row claims the organized set, because neither of them is it: the run organizes both.
  // `(abl)`. A zero row is noise, and the sum holds without it.
  const buckets: [number, React.ReactNode][] = [
    [s.new_unique, "new"],
    [s.near_dup, "look-alikes - organized too, and listed below"],
    [
      s.exact_dup,
      <>
        duplicates - not copied again
        {origins ? (
          <>
            <br />
            {origins}
          </>
        ) : null}
      </>,
    ],
    [unreadable, "could not be read - not organized"],
  ];
  const undatedCount = Number(s.undated) || 0;
  return (
    <>
      <div className="metrics" data-testid="org-tally" data-files={Number(s.files) || 0}>
        {buckets
          .filter(([n]) => Number(n) > 0)
          .map(([n, label], i) => (
            <div className="metric" key={i}>
              <div className="metric-value">{nfmt(n)}</div>
              <div className="metric-label">{label}</div>
            </div>
          ))}
      </div>
      <div className="k" data-testid="org-will-organize">
        {plural(Number(s.will_organize) || 0, "file")} will be organized
        {view.destinationLabel ? ` into ${view.destinationLabel}` : ""}.
      </div>
      {undatedCount > 0 ? (
        view.skippingUndated ? (
          <div className="k" data-testid="org-undated">
            {plural(undatedCount, "file")} {undatedCount === 1 ? "has" : "have"} no date and will be
            skipped, not organized.
          </div>
        ) : (
          <div className="k" data-testid="org-undated">
            Of those organized, {plural(undatedCount, "file")} {undatedCount === 1 ? "has" : "have"}{" "}
            no date and will go to “Undated”.
          </div>
        )
      ) : null}
      <AlreadyNote s={s} view={view} />
    </>
  );
}

export function PreviewCard({ s, view }: { s: PreviewSummary; view: PreviewView }): React.JSX.Element {
  const { mediaCount, fmtDuration, plural } = formatters();
  const folders = Object.keys(s.folders ?? {}).length > 0;
  return (
    <div className="card result">
      <div className="headline">{mediaCount(s)} found</div>
      {s.elapsed_seconds ? <div className="k">checked in {fmtDuration(s.elapsed_seconds)}</div> : null}
      {s.destination_limit ? (
        <div className="banner warn" data-testid="org-destination-limit">
          <div>
            <div className="b-title">This drive cannot hold this run</div>
            <div>{s.destination_limit.detail}</div>
          </div>
        </div>
      ) : null}
      <UnreadableBanner s={s} />
      <Tally s={s} view={view} />
      <MatchList report={s.exact_dup_matches} label="Show what each duplicate matched" />
      <MatchList report={s.near_dup_matches} label="Show what each look-alike resembles" />
      {folders ? (
        <>
          <h3>
            Into these folders{" "}
            <span style={{ fontWeight: 400, color: "var(--fg-muted)" }}>- hover a chip for what it means</span>
          </h3>
          <div className="chips">
            <Chips folders={s.folders} />
          </div>
          <Legend folders={s.folders} />
        </>
      ) : null}
      <ByFormat bf={s.by_format} />
      <DateQualityNotes s={s} />
      <InferredShiftNote s={s} />
      {s.heic_perceptual_skipped ? (
        <div className="banner warn">
          <div>
            {plural(s.heic_perceptual_skipped, "HEIC file")} will be backed up, but near-duplicate
            detection is unavailable for them.
          </div>
        </div>
      ) : null}
      <SkippedDetails sk={s.skipped} />
    </div>
  );
}

/** The `!s.files` outcome, chosen by `app.js`: the same card the cheap tier shows. */
export function PreviewEmptyCard({ s }: { s: PreviewEmpty }): React.JSX.Element {
  return <NothingHereCard s={s} />;
}
