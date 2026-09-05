/**
 * Organize's "Look inside" card, rendered as components - the first content inside `#org-result`
 * that React draws rather than injects.
 *
 * **Same DOM as the `app.js` strings it replaces** (`renderInventoryResult`, `renderUnreadable`,
 * `byFormat`, `renderSkippedDetails`, deleted in the same commit): every class, `data-testid`,
 * `data-reason` and sentence is reproduced, and the unchanged e2e suite is the referee. What
 * differs is only the whitespace between block elements that template literals carried as text
 * nodes; every assertion normalises it and nothing lays it out.
 *
 * **No rule lives here.** The counts, labels, reasons and remedies arrive worded in the payload
 * (`(aer)`: no reason-to-sentence map in the browser), and the formatters are read back from
 * `app.js` through `window.truestillFormatters` rather than copied - `fmtBytes` is a mirror of
 * `truestill_core.units.format_bytes` and `test_one_byte_formatter.py` holds it to one copy.
 *
 * **The reverse seam.** The unreadable block, the by-format block and the skipped block are
 * shared with the dedup preview and with Backups' drive list, which `app.js` still builds as
 * strings. Rather than keep a second copy there, `markup` renders these same components to a
 * string on demand; `app.js` reads it through `window.truestillMarkup`. One definition, two
 * consumers, until the preview moves too. Rendered through the client renderer into a detached
 * node and read back, not through `react-dom/server`: `renderToStaticMarkup` was measured first
 * and took the bundle from 191 KB to 383 KB for three fragments, and the client path yields the
 * exact DOM the island itself would draw.
 */

import { Fragment } from "react";
import { flushSync } from "react-dom";
import { createRoot } from "react-dom/client";

import type { components } from "./generated/api";

export type Inventory = components["schemas"]["OrganizeInventory"];
type UnreadableReport = components["schemas"]["UnreadableReport"];
type SkippedFolders = components["schemas"]["SkippedFolders"];
type Uncompared = components["schemas"]["Uncompared"];
type SuppressedDiagnostics = components["schemas"]["SuppressedDiagnostics"];
type ByFormatCounts = Inventory["by_format"];
type SkippedCounts = Inventory["skipped"];

/** The fields the unreadable block reads, structurally, so the inventory and the dedup preview
 *  both fit without a cast. Each is optional: the cheap tier carries only `skipped_folders`. */
export interface Unreadables {
  unreadable_files?: UnreadableReport | null;
  skipped_folders?: SkippedFolders[] | null;
  uncompared?: Uncompared[] | null;
  suppressed_diagnostics?: SuppressedDiagnostics | null;
}

interface Formatters {
  nfmt: (n: number) => string;
  plural: (n: number, word: string, suffix?: string) => string;
  sentence: (text: string) => string;
  mediaCount: (s: { photos: number; videos: number; audio: number }) => string;
  fmtBytes: (n: number) => string;
}

/** `app.js` publishes these by name; `const` at the top of a classic script is not a window
 *  property the way a `function` is. Absent means `app.js` did not run, which is loud already. */
function formatters(): Formatters {
  const f = (window as unknown as { truestillFormatters?: Formatters }).truestillFormatters;
  if (!f) throw new Error("app.js has not published its formatters");
  return f;
}

function More({ total, shown }: { total: number; shown: number }): React.JSX.Element | null {
  // Truncation is never silent: if the payload capped the list, say how many are not shown.
  if (total <= shown) return null;
  return <div className="k">… and {formatters().nfmt(total - shown)} more.</div>;
}

export function UnreadableBanner({ s }: { s: Unreadables }): React.JSX.Element | null {
  const files = s.unreadable_files ?? { total: 0, shown: [] };
  const groups = s.skipped_folders ?? [];
  const uncompared = s.uncompared ?? [];
  const noise = s.suppressed_diagnostics ?? null;
  if (!files.total && !groups.length && !uncompared.length && !noise) return null;
  const { nfmt, plural, sentence } = formatters();
  return (
    <div className="banner warn" data-testid="org-unreadable">
      <div>
        {files.total ? (
          <>
            <div className="b-title">{plural(files.total, "file")} could not be read</div>
            {files.shown.map((f, i) => (
              <div className="mono" key={i}>
                {f.name} - {f.reason}
              </div>
            ))}
            <More total={files.total} shown={files.shown.length} />
            <div className="k">
              Not organized. Fix the permission or check the disk, then preview again.
            </div>
          </>
        ) : null}
        {groups.map((g, i) => (
          <Fragment key={i}>
            <div className="b-title">
              {g.label}: {nfmt(g.total)}
            </div>
            {g.folders.map((f, j) => (
              <div className="mono" key={j}>
                {f} - contents unknown
              </div>
            ))}
            <More total={g.total} shown={g.folders.length} />
            <div className="k">Whatever is inside was not counted.</div>
            <div className="k">{sentence(g.remedy)}.</div>
          </Fragment>
        ))}
        {uncompared.map((u, i) => (
          <Fragment key={i}>
            <div className="b-title" data-reason={u.reason}>
              {u.label}: {nfmt(u.total)}
            </div>
            {u.files.map((f, j) => (
              <div className="mono" key={j}>
                {f}
              </div>
            ))}
            <More total={u.total} shown={u.files.length} />
            <div className="k">{sentence(u.remedy)}.</div>
          </Fragment>
        ))}
        {noise ? (
          <div className="k">
            {nfmt(noise.total)} diagnostic lines from the image libraries were not shown:{" "}
            {nfmt(noise.warnings)} warnings and {nfmt(noise.decoder_lines)} from the decoders. They
            name no file.
          </div>
        ) : null}
      </div>
    </div>
  );
}

export function ByFormat({ bf }: { bf: ByFormatCounts | null | undefined }): React.JSX.Element | null {
  if (!bf) return null;
  const line = (grp: string, label: string): string => {
    const entries = Object.entries(bf[grp] ?? {});
    return entries.length ? `${label}: ${entries.map(([x, n]) => `${x} ${n}`).join(" · ")}` : "";
  };
  const rows = [line("photos", "photos"), line("videos", "videos"), line("audio", "audio")].filter(
    Boolean,
  );
  if (!rows.length) return null;
  return (
    <details className="more">
      <summary>By format ▾</summary>
      <div className="k mono" style={{ lineHeight: 1.8, marginTop: "var(--space-2)" }}>
        {rows.map((row, i) => (
          <Fragment key={i}>
            {i ? <br /> : null}
            {row}
          </Fragment>
        ))}
      </div>
    </details>
  );
}

export function SkippedDetails({
  sk,
}: {
  sk: SkippedCounts | null | undefined;
}): React.JSX.Element | null {
  const groups = Object.entries(sk ?? {})
    .map(([name, counts]) => [name, Object.entries(counts ?? {})] as const)
    .filter(([, entries]) => entries.length);
  const total = groups.reduce((a, [, entries]) => a + entries.reduce((b, [, n]) => b + n, 0), 0);
  if (!total) return null;
  return (
    <details className="more">
      <summary>{formatters().plural(total, "file")} skipped (not photos or videos) ▾</summary>
      <table className="table">
        <tbody>
          {groups.map(([name, entries]) => (
            <tr key={name}>
              <td>{name.replace(/_/g, " ")}</td>
              <td className="num">{entries.map(([e, n]) => `${e} ×${n}`).join(", ")}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  );
}

/** The cheap tier's card. Knows none of the panel's facts (no dates, no duplicates), and says so. */
export function InventoryCard({ s }: { s: Inventory }): React.JSX.Element {
  const { mediaCount, fmtBytes } = formatters();
  if (!s.files) {
    // The unreadable block goes FIRST: a walk that could not open a folder has not established
    // that there is nothing in it, so "Nothing to organize here" is very likely the wrong answer
    // and the reason has to be read before it.
    return (
      <div className="card result">
        <UnreadableBanner s={s} />
        <div className="banner warn">
          <div>
            <div className="b-title">Nothing to organize here</div>
            <div>No photos or videos in this folder - is it the right one?</div>
          </div>
        </div>
      </div>
    );
  }
  return (
    <div className="card result">
      <div className="headline">{mediaCount(s)} found</div>
      <div className="k">
        {fmtBytes(s.total_bytes || 0)} of media - no dates or duplicates checked yet
      </div>
      <UnreadableBanner s={s} />
      <ByFormat bf={s.by_format} />
      <SkippedDetails sk={s.skipped} />
      <div className="banner">
        <div>
          Next: check for duplicates (reads each file for dates and look-alikes). That is the slow
          step on a network drive.
        </div>
      </div>
    </div>
  );
}

/** Render an element into a detached node and hand back its HTML. `flushSync` makes the render
 *  land before `innerHTML` is read; the root is unmounted so nothing lingers. */
function toHtml(element: React.ReactElement): string {
  const host = document.createElement("div");
  const root = createRoot(host);
  flushSync(() => root.render(element));
  const html = host.innerHTML;
  root.unmount();
  return html;
}

/** The same three blocks as strings, for the `app.js` builders that still compose HTML. */
export const markup = {
  unreadable: (s: Unreadables): string => toHtml(<UnreadableBanner s={s} />),
  byFormat: (bf: ByFormatCounts | null | undefined): string => toHtml(<ByFormat bf={bf} />),
  skippedDetails: (sk: SkippedCounts | null | undefined): string =>
    toHtml(<SkippedDetails sk={sk} />),
};
