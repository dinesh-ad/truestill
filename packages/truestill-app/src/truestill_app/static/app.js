"use strict";
const TOKEN = window.TRUESTILL_TOKEN;
const $ = (id) => document.getElementById(id);

// The run block is authored once in index.html and cloned into every `[data-run]` mount, with
// `<prefix>-<part>` ids stamped on. It runs HERE, at the top, and not in a DOMContentLoaded
// handler: thirty statements later in this file wire `$("org-cancel").onclick` and friends at
// top level, so the elements have to exist by the time execution reaches them.
function mountRunBlocks() {
  // No `if (!template) return` on purpose: a missing template means every job's controls are
  // absent, and failing quietly here would surface as thirty unrelated null-derefs instead.
  const template = document.getElementById("tpl-run");
  for (const mount of document.querySelectorAll("[data-run]")) {
    const prefix = mount.dataset.run;
    const clone = template.content.cloneNode(true);
    for (const el of clone.querySelectorAll("[data-id]")) {
      el.id = `${prefix}-${el.dataset.id}`;
      el.removeAttribute("data-id");
    }
    if (mount.dataset.runClass) clone.firstElementChild.classList.add(mount.dataset.runClass);
    mount.replaceWith(clone);
  }
}
mountRunBlocks();
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const nfmt = (n) => Number(n).toLocaleString();
// "2 files", "1 file" -- never "file(s)". Counts are read aloud in a user's head, and the
// parenthesised plural is the sound of a form letter.
const plural = (n, word, suffix = "s") => `${nfmt(n)} ${word}${Number(n) === 1 ? "" : suffix}`;

// A stale server serving a fresh browser (found for real: a long-running process pinned to
// pre-13.3b code returned {"clusters": [...]} while the shipped app.js expected {"cards": [...]})
// used to throw deep inside a handler with nothing checking the response first, and the click
// that triggered it left a blank screen -- no cards, no error, no "none found" message. `api()`
// now rejects anything that is not a 2xx with a legible error (status + body), so every caller
// gets a real `Error` to catch instead of quietly parsing whatever came back.
async function api(path, body) {
  const opts = { headers: { "X-Truestill-Token": TOKEN } };
  if (body !== undefined) {
    opts.method = "POST";
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(path, opts);
  const text = await res.text();
  if (!res.ok) {
    throw new Error(`${path} failed (${res.status} ${res.statusText}): ${text.slice(0, 500) || "no body"}`);
  }
  try {
    return JSON.parse(text);
  } catch {
    throw new Error(`${path} did not return JSON: ${text.slice(0, 200)}`);
  }
}
const get = (path) => api(path);

// The one place a thrown error becomes something a user can actually see. Every screen shares
// this banner (it lives outside the per-screen sections in index.html) so a failure is visible
// regardless of which screen was open when it happened.
function showFatalError(message) {
  $("global-error-message").textContent = message;
  $("global-error").classList.remove("hidden");
}
function hideFatalError() {
  $("global-error").classList.add("hidden");
}

// Wraps a click handler (or any async/callback function) so a thrown error or a rejected
// promise renders as a visible banner instead of vanishing. This is the fix for the class of
// bug above: every handler that calls `api()`/`get()` goes through this, so a failure -
// wrong shape, a non-2xx response, a genuine bug - always has somewhere to go.
function guarded(fn) {
  return async (...args) => {
    hideFatalError();
    try {
      await fn(...args);
    } catch (err) {
      showFatalError(err instanceof Error ? err.message : String(err));
    }
  };
}
// Last-resort backstop for anything guarded() does not wrap (a rejection from code outside a
// click handler, a genuine unforeseen bug) - never silent, even when nothing anticipated it.
window.addEventListener("unhandledrejection", (e) => {
  const reason = e.reason;
  showFatalError(reason instanceof Error ? reason.message : String(reason));
});
window.onerror = (message) => {
  showFatalError(String(message));
  return false;
};

// Terminal events come in two shapes -- a completion carries `summary`, a failure carries
// `message` -- and every caller used to read `summary.error`, which a failure never has. The
// result was a failed verify rendering `nfmt(undefined)` three times: "NaN verified · NaN
// missing · NaN changed". Normalising here means no caller can get that wrong again.
function streamJob(jobId, onProgress, onDone) {
  const es = new EventSource(`/api/jobs/${jobId}/events?token=${encodeURIComponent(TOKEN)}`);
  es.onmessage = (e) => {
    const d = JSON.parse(e.data);
    if (d.type === "progress") { onProgress(d); return; }
    es.close();
    const failed = d.type === "error";
    onDone({
      ok: !failed,
      status: d.status || (failed ? "error" : "done"),
      error: failed ? (d.message || "something went wrong") : null,
      code: d.code || null,
      summary: failed ? {} : (d.summary || {}),
    });
  };
  es.onerror = () => es.close();
  return es;
}

/** Promise form of streamJob so withBusy can await the whole run (and always release). */
function awaitJob(jobId, onProgress) {
  return new Promise((resolve) => {
    streamJob(jobId, onProgress || (() => {}), resolve);
  });
}

/**
 * Shared job-run skeleton for every awaitJob call site.
 *
 * Owns: withBusy (optional), soft-refuse, progress start/stop, job-id handle, optional
 * #undo-card parking, awaitJob, and the cancelled / error / success dispatch.
 * Callers own: refuse HTML, cancelled/success/error copy, and post-terminal side effects.
 *
 * Cancel arrives as ok:true — the cancelled branch here is what keeps all thirteen sites
 * honest after a stop (F38 B). Deliberate differences are parameters, not forks of this body.
 */
async function runJob({
  button = null,
  busyLabel = null,
  setStatus: outerSetStatus = null,
  start,
  setJob,
  progress,
  progressLabel,
  progressBeforeStart = false,
  parkUndoCardIn = null,
  onRefuse,
  abortStart = null,
  statusVerb = null,
  unit = "files",
  statusForProgress = null,
  onCancelled,
  onSuccess,
  onError,
  beforeOutcome = null,
  after = null,
}) {
  const work = async ({ setStatus }) => {
    if (progressBeforeStart) progress.start(progressLabel);
    const started = await start();
    if (started && started.ok === false) {
      if (progressBeforeStart) progress.stop();
      onRefuse(started);
      return;
    }
    if (abortStart && await abortStart(started)) {
      if (progressBeforeStart) progress.stop();
      return;
    }
    setJob(started.job_id);
    const stage = typeof parkUndoCardIn === "function" ? parkUndoCardIn() : parkUndoCardIn;
    if (stage) {
      stage.innerHTML = "";
      stage.appendChild($("undo-card"));
    }
    if (!progressBeforeStart) progress.start(progressLabel);
    const d = await awaitJob(started.job_id, (p) => {
      progress.update(p);
      if (statusForProgress) statusForProgress(p, setStatus);
      else if (p.total && statusVerb) setStatus(scaleStatus(statusVerb, p.done, p.total, unit));
    });
    progress.stop();
    setJob(null);
    if (stage) {
      document.body.appendChild($("undo-card"));
      $("undo-card").classList.add("hidden");
    }
    if (beforeOutcome) await beforeOutcome(d);
    // Central cancelled branch: one fix reaches all thirteen (mutation target for F38 commit 2).
    if (!d.ok) await onError(d);
    else if (d.status === "cancelled") await onCancelled(d);
    else await onSuccess(d);
    if (after) await after(d);
  };
  if (button) return withBusy(button, busyLabel, work);
  return work({ setStatus: outerSetStatus || (() => {}) });
}

// Known failures worth answering with a next step rather than an apology. Matched on an
// exception name from the server, never on message text, which would break the moment
// anyone reworded it.
const FRIENDLY_ERRORS = {
  NotABackupDriveError:
    "This folder isn't set up as a backup drive yet. Use <b>Copy your library to another drive</b> " +
    "below and Truestill will set it up.",
};

function jobErrorCard(d) {
  const friendly = d.code && FRIENDLY_ERRORS[d.code];
  return card(`<div class="banner warn"><div>${friendly || esc(d.error)}</div></div>`);
}
function setBar(barId, countId, done, total) {
  const pct = total ? Math.round((done / total) * 100) : 0;
  $(barId).style.width = pct + "%";
  // "0 / 0" before a total is known reads as broken; say nothing until there is a number.
  $(countId).textContent = total ? `${nfmt(done)} / ${nfmt(total)}` : "";
}

// ---------- progress ----------
// One tracker for every long operation, so organize / verify / backup / migrate / trips
// cannot drift into five different ideas of what a wait looks like.
//
// Time remaining is deliberately withheld until the rate settles. An estimate that appears
// instantly and then swings from "8 minutes" to "40 seconds" and back teaches a user to
// distrust the whole display; accurate-or-absent is the rule, so nothing is shown until
// there is enough evidence to be roughly right, and then only coarsely.
const ETA_MIN_SECONDS = 10;   // both gates must pass, so a fast run never flashes an estimate
const ETA_MIN_FRACTION = 0.05;
const RATE_SMOOTHING = 0.25;  // EMA weight on the newest sample

function fmtDuration(seconds) {
  const s = Math.max(0, Math.round(seconds));
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ${String(s % 60).padStart(2, "0")}s`;
  return `${Math.floor(m / 60)}h ${String(m % 60).padStart(2, "0")}m`;
}

// Coarse buckets on purpose: "about 2 min" stays true for a while, where "1:47" is wrong a
// second after it is drawn and invites the user to watch it rather than their library.
function fmtRemaining(seconds) {
  if (seconds < 45) return "less than a minute remaining";
  const minutes = Math.round(seconds / 60);
  if (minutes <= 1) return "about a minute remaining";
  if (minutes < 10) return `about ${minutes} min remaining`;
  if (minutes < 60) return `about ${Math.round(minutes / 5) * 5} min remaining`;
  const hours = seconds / 3600;
  return `about ${hours < 1.75 ? "an hour" : Math.round(hours) + " hours"} remaining`;
}

function createProgress(prefix) {
  const el = (suffix) => $(`${prefix}-${suffix}`);
  let started = 0, rate = 0, lastDone = 0, lastAt = 0, shownRemaining = "", ticker = null;

  const paint = (done, total) => {
    const now = performance.now() / 1000;
    const elapsed = now - started;
    const parts = [`elapsed ${fmtDuration(elapsed)}`];
    if (rate > 0) parts.push(`${rate < 10 ? rate.toFixed(1) : Math.round(rate)} files/sec`);
    // Both gates, per the accurate-or-absent rule: enough seconds AND enough of the work.
    if (total && elapsed >= ETA_MIN_SECONDS && done / total >= ETA_MIN_FRACTION && rate > 0) {
      const next = fmtRemaining((total - done) / rate);
      // Hold the previous wording unless the estimate genuinely moved to another bucket --
      // that is what stops the line flickering between two neighbouring values.
      if (next !== shownRemaining) shownRemaining = next;
      parts.push(shownRemaining);
    }
    const meta = el("meta");
    if (meta) meta.textContent = parts.join(" · ");
  };

  return {
    start(label) {
      started = performance.now() / 1000;
      rate = 0; lastDone = 0; lastAt = started; shownRemaining = "";
      el("card").classList.remove("hidden");
      setBar(`${prefix}-bar`, `${prefix}-count`, 0, 0);
      const phase = el("phase");
      if (phase) phase.textContent = label || "starting";
      const activity = el("activity");
      if (activity) activity.textContent = "";
      const tally = el("tally");
      if (tally) tally.innerHTML = "";
      // Repaint on a timer as well as on events: elapsed must keep moving while a single
      // large file is being hashed or copied, or the run looks wedged when it is not.
      clearInterval(ticker);
      ticker = setInterval(() => paint(lastDone, this._total || 0), 1000);
    },
    update(d) {
      const now = performance.now() / 1000;
      const dt = now - lastAt;
      if (dt > 0.25 && d.done > lastDone) {
        const sample = (d.done - lastDone) / dt;
        rate = rate ? rate + RATE_SMOOTHING * (sample - rate) : sample;
        lastDone = d.done; lastAt = now;
      }
      this._total = d.total;
      setBar(`${prefix}-bar`, `${prefix}-count`, d.done, d.total);
      const phase = el("phase");
      if (phase && d.phase) phase.textContent = d.phase;
      const activity = el("activity");
      if (activity) activity.textContent = d.item ? `· ${d.item}` : "";
      const tally = el("tally");
      if (tally && d.tally) {
        tally.innerHTML = Object.entries(d.tally)
          .map(([k, v]) => `<span><b>${nfmt(v)}</b> ${esc(k)}</span>`)
          .join("");
      }
      paint(d.done, d.total);
    },
    stop() {
      clearInterval(ticker);
      ticker = null;
      el("card").classList.add("hidden");
    },
    elapsed() { return performance.now() / 1000 - started; },
  };
}
function fmtBytes(n) {
  if (!n) return "0 B";
  const u = ["B", "KB", "MB", "GB", "TB"];
  let i = 0, v = n;
  while (v >= 1024 && i < u.length - 1) { v /= 1024; i++; }
  return `${v.toFixed(v < 10 && i > 0 ? 1 : 0)} ${u[i]}`;
}
//: Risk is marked, not merely coloured - colour alone cannot carry a state distinction.
const WARN_MARK = "\u26a0 ";
function card(html) { return `<div class="card result">${html}</div>`; }
function debounce(fn, ms) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; }

// plain-language explanation of each derived folder category (for first-timers)
const CAT_INFO = {
  Camera: "Photos and videos from a phone or camera (has device info).",
  Screenshots: "Screen captures.",
  WhatsApp: "Images and videos from WhatsApp.",
  Telegram: "Images and videos from Telegram.",
  Saved: "Images saved from apps or the web - original source unknown.",
  Undated: "No reliable date could be found, so these are kept together, not guessed.",
};
const catTip = (name) => CAT_INFO[name] || "Folder derived from the file’s own details.";

// "24 photos · 6 videos" - split, honest about the mix, zeros omitted (photos shown if all zero)
function mediaCount(s) {
  const parts = [];
  if (s.photos) parts.push(plural(s.photos, "photo"));
  if (s.videos) parts.push(plural(s.videos, "video"));
  if (s.audio) parts.push(`${nfmt(s.audio)} audio`);
  return parts.length ? parts.join(" · ") : "0 photos";
}
// collapsible "By format ▾" - extension counts split by photos / videos / audio, monospace
function byFormat(bf) {
  if (!bf) return "";
  const line = (grp, label) => {
    const e = Object.entries(bf[grp] || {});
    return e.length ? `${label}: ${e.map(([x, n]) => `${esc(x)} ${n}`).join(" · ")}` : "";
  };
  const rows = [line("photos", "photos"), line("videos", "videos"), line("audio", "audio")].filter(Boolean);
  return rows.length
    ? `<details class="more"><summary>By format ▾</summary><div class="k mono" style="line-height:1.8;margin-top:var(--space-2)">${rows.join("<br>")}</div></details>`
    : "";
}

// Two date-quality signals, each on its own line and never folded into the plain "no date"
// count: a placeholder date we refused, and a date that may be a dead camera-clock default.
// Both render only when non-zero -- a clean library says nothing rather than "0".
function dateQualityNotes(s) {
  const notes = [];
  if (s.future_rejected) {
    notes.push(`<div>${plural(s.future_rejected, "file")} claimed a date in the future, so it was
      refused and they went to <span class="mono">Undated/</span>. That usually means a wrong
      camera clock or edited details; the original date cannot be recovered.</div>`);
  }
  if (s.sentinel_rejected) {
    notes.push(`<div>${plural(s.sentinel_rejected, "file")} carried only a placeholder date
      (an all-zero “epoch” timestamp). It was refused, so they went to “Undated” rather than
      being filed under 1904 or 1970.</div>`);
  }
  if (s.suspect_default) {
    notes.push(`<div>${plural(s.suspect_default, "file")} dated exactly midnight on a day
      cameras fall back to when their clock battery dies. They are filed by that date - it may
      well be right - but they are worth a look.</div>`);
  }
  return notes.length ? `<div class="banner warn">${notes.join("")}</div>` : "";
}

// Informational: videos whose UTC CreateDate was shifted to local. Names + offsets, not a
// count alone. not_proven_utc fallthrough is omitted (usually correct local digits).
function inferredLocalShiftNotes(s) {
  const shifts = s.inferred_local_shifts || [];
  if (!shifts.length) return "";
  const rows = shifts.map((x) => `<div class="mono">${esc(x.line || x.name)}</div>`).join("");
  return `<div class="banner"><div>${plural(shifts.length, "video")} shifted from UTC CreateDate:
    <div style="margin-top:var(--space-2)">${rows}</div></div></div>`;
}

// Folder chips + their first-timer legend. Shared by the preview and the completion card so
// the same folders are always described the same way.
function chipsFor(folders) {
  return Object.entries(folders || {}).map(([k, v]) =>
    `<span class="chip" title="${esc(catTip(k))}">${esc(k)} <span class="num">${nfmt(v)}</span></span>`).join("");
}
function legendFor(folders) {
  const names = Object.keys(folders || {}).filter((n) => CAT_INFO[n]);
  return names.length
    ? `<div class="k" style="font-size:var(--text-xs);margin-top:var(--space-2);line-height:1.6">${
        names.map((n) => `<b>${esc(n)}</b> - ${esc(CAT_INFO[n])}`).join("<br>")}</div>` : "";
}

// ---------- completion ----------
// The payoff moment, shared by every long operation. Each field renders only when the run
// actually produced it: an undated batch shows no year range, a run with no duplicates shows
// no savings line. Nothing here is computed for effect -- the same honesty rule the custody
// strip obeys applies hardest at the moment a user feels good about the result.
function completionCard({ headline, sub, stats = [], chips = "", notes = [], legend = "", done = "Done" }) {
  const statRows = stats
    .filter((s) => s && s.value)
    .map((s) => `<div class="n">${s.value}</div><div class="k">${s.label}</div>`)
    .join("");
  return card(
    `<div class="done-mark">${esc(done)}</div>
     <div class="headline">${headline}</div>
     ${sub ? `<div class="k">${sub}</div>` : ""}
     ${statRows ? `<div class="tally">${statRows}</div>` : ""}
     ${chips ? `<h3>Into these folders</h3><div class="chips">${chips}</div>${legend}` : ""}
     ${notes.filter(Boolean).join("")}`
  );
}

const yearOf = (iso) => (iso ? String(new Date(iso).getFullYear()) : null);
const dayOf = (iso) => (iso ? String(iso).slice(0, 10) : "never");

function statsBars(years) {
  if (!years.length) return `<div class="k">No dated files yet.</div>`;
  const max = Math.max(...years.map((row) => row.count), 1);
  return years.map((row) => {
    const width = Math.max(2, Math.round((row.count / max) * 100));
    return `<div class="stats-bar-row">
      <div class="mono">${esc(row.year)}</div>
      <div class="stats-bar"><i style="width:${width}%"></i></div>
      <div class="mono">${nfmt(row.count)}</div>
    </div>`;
  }).join("");
}

function statsFormatRows(byFormat) {
  const rows = Object.entries(byFormat || {});
  if (!rows.length) return `<div class="k">Formats are unknown until files are organized.</div>`;
  return rows.map(([ext, count]) => `<div class="mono">${esc(ext)} · ${nfmt(count)}</div>`).join("");
}

// (n) "How your dates were determined" - the honesty view. Percentages are of the RECORDED
// files only: a share of a population that includes "unknown" is not a share of anything, and on
// a library organized before this shipped every row is unknown.
function dateProvenanceRows(dates) {
  const recorded = dates.recorded || 0;
  return (dates.rows || [])
    .map((r) => {
      // A group with files in it must never render as "0%". Found on the real library: 2
      // undated files out of 600 round to zero, and a screen that exists to be honest about
      // dates cannot report "none" for something it is simultaneously listing.
      const exact = recorded && !r.not_recorded ? (r.files / recorded) * 100 : null;
      const share = exact === null ? null : exact < 1 ? "<1" : String(Math.round(exact));
      const pct = share === null ? "" : `<span class="k">${share}%</span>`;
      const flag = r.review ? ' <span class="k">worth a look</span>' : "";
      const why = r.evidence ? `<div class="k mono">${esc(r.evidence)}</div>` : "";
      // The row is openable: the mix says HOW dates were determined, the drill-down says which
      // files - and carries the sha256 the rescue action needs. Addressed by the raw tier value,
      // never by the label, because the label is wording and wording is allowed to change.
      const key = r.source === null || r.source === undefined ? "" : r.source;
      return `<tr><td>${esc(r.label)}${flag}</td><td class="num">${plural(r.files, "file")}</td>
              <td class="num">${pct}</td></tr>
              <tr><td colspan="3" class="k">${esc(r.detail)}${why}
                <div><button class="btn btn-ghost" data-date-tier="${esc(key)}">Show these files</button></div>
                <div data-date-tier-list="${esc(key)}"></div></td></tr>`;
    })
    .join("");
}

function renderStatsSummary(stats) {
  const safety = stats.safety || {};
  const completeness = stats.completeness || {};
  const shape = stats.shape || {};
  const dates = stats.dates || { rows: [], total: 0, recorded: 0, not_recorded: 0 };
  if (!safety.total_files) {
    return card(
      `<div class="headline">No library data yet</div>
       <div class="k">Organize or import photos first. This view will then show custody and completeness totals.</div>`
    );
  }
  const undatedList = (completeness.undated_samples || [])
    .slice(0, 8)
    .map((row) => `<div class="mono">${esc(row.relative || row.source_path)}</div>`)
    .join("");
  const zeroSamples = (safety.zero_drive_samples || [])
    .slice(0, 8)
    .map((name) => `<div class="mono">${esc(name)}</div>`)
    .join("");
  const drives = (safety.drives || []).length
    ? safety.drives.map((d) => `<tr><td>${esc(d.label)}</td><td class="num">${nfmt(d.files)}</td><td class="num">${fmtBytes(d.size)}</td><td class="mono">${esc(dayOf(d.last_verified))}</td></tr>`).join("")
    : `<tr><td colspan="4" class="k">No registered backup drives yet.</td></tr>`;
  return [
    card(
      `<div class="headline">Custody</div>
       <div class="k">Query cost: ${esc(stats.complexity || "aggregate SQL only")}.</div>
       <div class="tally">
         <div class="n">${nfmt(safety.photos || 0)}</div><div class="k">photos</div>
         <div class="n">${nfmt(safety.videos || 0)}</div><div class="k">videos</div>
         <div class="n">${fmtBytes(safety.total_size || 0)}</div><div class="k">total size</div>
         <div class="n">${nfmt(safety.files_on_two_plus_drives || 0)}</div><div class="k">files on 2+ drives</div>
         <div class="n">${nfmt(safety.files_on_one_drive || 0)}</div><div class="k">files on exactly 1 drive</div>
         <div class="n">${nfmt(safety.files_on_zero_drives || 0)}</div><div class="k">not on a registered drive</div>
         <div class="n">${nfmt(safety.never_verified_files || 0)}</div><div class="k">never verified</div>
       </div>
       <div class="actions">
         <button class="btn btn-secondary" data-stats-action="backups">Go to Backups</button>
         <span class="why">Make another copy or run verification for at-risk and never-verified files.</span>
       </div>
       ${safety.files_on_zero_drives ? `<div class="banner"><div>
         <div class="b-title">${plural(safety.files_on_zero_drives, "file")} not on a registered drive</div>
         <div class="k">Truestill has these in its records but no copy on any drive it knows, so
         it cannot check them. Two ordinary reasons: the destination is a cloud remote reached
         with <code>--rclone</code>, which is not a drive; or they were organized from the
         command line before it registered its destination. Re-importing from the originals
         puts them back in custody. Truestill does not guess which of the two applies.</div>
       </div></div>` : ""}
       <div class="actions">
       </div>
       ${zeroSamples ? `<details class="more"><summary>At-risk file sample ▾</summary>${zeroSamples}</details>` : ""}
       <h3>Per drive</h3>
       <table class="table"><thead><tr><th>Drive</th><th>Files</th><th>Size</th><th>Last verified</th></tr></thead><tbody>${drives}</tbody></table>`
    ),
    card(
      `<div class="headline">How your dates were determined</div>
       <div class="k">${
         dates.not_recorded
           ? `${plural(dates.not_recorded, "file")} of ${plural(dates.total, "file")} predate this record. That is normal and nothing is wrong with them; the shares below are of the ${nfmt(dates.recorded)} Truestill has a note for.`
           : `Where the capture date for each of your ${plural(dates.total, "file")} came from.`
       }</div>
       <table class="table"><thead><tr><th>Source</th><th>Files</th><th>Share</th></tr></thead>
       <tbody>${dateProvenanceRows(dates)}</tbody></table>`
    ),
    card(
      `<div class="headline">Completeness</div>
       <div class="tally">
         <div class="n">${nfmt(completeness.undated_files || 0)}</div><div class="k">undated files</div>
         <div class="n">${nfmt(completeness.timeline_files || 0)}</div><div class="k">in timeline folders</div>
         <div class="n">${nfmt(completeness.side_bin_files || 0)}</div><div class="k">in side bins</div>
         <div class="n">${nfmt(completeness.near_duplicates_flagged || 0)}</div><div class="k">near-duplicate flagged files</div>
       </div>
       <div class="actions">
         <button class="btn btn-secondary" data-stats-action="undated">Review undated files</button>
         <span class="why">Opens Find with “Undated” so you can locate and fix dating gaps.</span>
       </div>
       ${undatedList ? `<details class="more"><summary>Undated file sample ▾</summary>${undatedList}</details>` : ""}
       <div class="k" style="margin-top:var(--space-3)">
         Exact duplicates are not shown in this view. ${esc(completeness.exact_duplicates_omission_reason || "")}
       </div>`
    ),
    card(
      `<div class="headline">Shape</div>
       <div class="tally">
         <div class="n">${esc(dayOf(shape.oldest_capture))}</div><div class="k">oldest capture date</div>
         <div class="n">${esc(dayOf(shape.newest_capture))}</div><div class="k">newest capture date</div>
       </div>
       <h3>By year</h3>
       <div class="stats-bars">${statsBars(shape.by_year || [])}</div>
       <h3>By format</h3>
       <div class="stats-formats">${statsFormatRows(shape.by_format || {})}</div>`
    ),
  ].join("");
}

function spanStory(r) {
  const from = yearOf(r.oldest), to = yearOf(r.newest);
  if (!from) return null;                       // undated batch: no range exists to tell
  return from === to ? `all from ${from}` : `spanning ${from} – ${to}`;
}

function organizeCompletion(r) {
  const moved = (r.moved_in_place || 0) + (r.moved_by_copy || 0);
  const verb = moved && !r.organized ? "moved" : "organized";
  const kinds = [
    r.photos ? plural(r.photos, "photo") : "",
    r.videos ? plural(r.videos, "video") : "",
    r.audio ? `${nfmt(r.audio)} audio` : "",
  ].filter(Boolean).join(" · ");
  const span = spanStory(r);
  const notes = [];
  if (r.near_dup) {
    notes.push(`<div class="banner warn"><div>${plural(r.near_dup, "look-alike")} flagged for
      review - ${fmtBytes(r.bytes_near_dup)} if you decide to remove them. They were kept, not
      dropped.</div></div>`);
  }
  if (r.moved_in_place) {
    notes.push(`<div class="banner"><div>${nfmt(r.moved_in_place)} moved by rename on the drive
      (no bytes copied). Undo with <code>truestill undo-organize</code>.</div></div>`);
  }
  if (r.single_copy) {
    notes.push(`<div class="banner warn"><div>${plural(r.single_copy, "file")} now exist in only
      one place. <a href="#" onclick="showScreen('backups');return false;">Make it safe in 2
      places</a>.</div></div>`);
  }
  if (r.failed) {
    notes.push(`<div class="banner warn"><div>${plural(r.failed, "file")} could not be
      ${verb}.</div></div>`);
  }
  if (r.leftover_empty_folders && r.leftover_empty_folders.count) {
    notes.push(cleanupOfferNote(r.leftover_empty_folders));
  }
  return completionCard({
    done: r.cancelled ? "Stopped" : "Done",
    headline: `${plural(r.organized || 0, "file")} ${verb}`
      + (r.cancelled ? " before you stopped it" : ""),
    sub: [kinds, span].filter(Boolean).join(" · "),
    stats: [
      { value: fmtBytes(r.bytes_organized), label: "now organized" },
      r.duplicates
        ? { value: fmtBytes(r.bytes_saved), label: `saved by skipping ${plural(r.duplicates, "duplicate")}` }
        : null,
      r.elapsed_seconds ? { value: fmtDuration(r.elapsed_seconds), label: "taken" } : null,
      Object.keys(r.folders || {}).length
        ? {
            value: nfmt(Object.keys(r.folders).length),
            label: Object.keys(r.folders).length === 1 ? "folder" : "folders",
          }
        : null,
    ],
    chips: chipsFor(r.folders || {}),
    legend: legendFor(r.folders || {}),
    notes,
  });
}

const orgProgress = createProgress("org");
const verifyProgress = createProgress("verify");
const evProgress = createProgress("ev");
const bkProgress = createProgress("bk");
const migProgress = createProgress("mig");
const undoProgress = createProgress("undo");
const rcProgress = createProgress("rc");
const bakeProgress = createProgress("bake");

// ---------- typed confirm (reusable) ----------
// Destructive actions that currently demand a typed word on the CLI (undo, and soon oo/rr)
// need the same gate in the app. One helper so each surface does not invent its own.
function typedConfirm(host, { word, label, buttonLabel, onConfirm }) {
  host.innerHTML =
    `<div class="field"><label>${esc(label)}</label>
       <input class="input" data-typed-confirm autocomplete="off" spellcheck="false"
              placeholder="type ${esc(word)}"></div>
     <div class="actions">
       <button class="btn btn-primary" data-typed-go disabled>${esc(buttonLabel)}</button></div>`;
  const input = host.querySelector("[data-typed-confirm]");
  const go = host.querySelector("[data-typed-go]");
  const sync = () => { go.disabled = input.value.trim() !== word; };
  input.addEventListener("input", sync);
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !go.disabled) go.click();
  });
  go.onclick = guarded(async () => {
    if (input.value.trim() !== word) return;
    await onConfirm();
  });
  input.focus();
}

// ---------- busy state (reusable) ----------
// Every trigger that starts work disables itself for the duration and re-enables in finally -
// success, cancel, and throw alike. An error path that left a button dead would be worse than
// the silent freeze this exists to fix (backlog oo). Second click while busy is a no-op (UX);
// the server DriveBusy lock is the real authority across tabs.
async function withBusy(button, label, work) {
  if (!button || button.dataset.busy === "1") return;
  const previousText = button.textContent;
  const previousDisabled = button.disabled;
  button.dataset.busy = "1";
  button.disabled = true;
  button.setAttribute("aria-busy", "true");
  const setStatus = (text) => { button.textContent = text; };
  setStatus(typeof label === "function" ? label() : label);
  try {
    await work({ setStatus });
  } finally {
    button.textContent = previousText;
    button.disabled = previousDisabled;
    delete button.dataset.busy;
    button.removeAttribute("aria-busy");
  }
}

/** DriveBusy gets its own title; other soft-fails keep the drive-correction card. */
function startRefusedCard(r, fieldId) {
  if (r && r.code === "DriveBusy") {
    return card(
      `<div class="banner warn"><div><div class="b-title">Already running</div>${esc(r.error)}</div></div>`
    );
  }
  return driveError(r, fieldId);
}

function scaleStatus(verb, done, total, unit) {
  if (!total) return `${verb}…`;
  return `${verb} for ${nfmt(total)} ${unit}…`;
}

// ---------- migration undo affordance (backlog pp) ----------
// Durable, not a snackbar: the journal lives in the catalog, so the affordance must survive a
// tab reload and must be re-queried after any migration (the only supersession signal).
let undoJob = null;

function undoArmedHtml(state, path) {
  return card(
    `<div class="headline">Undo the last migration</div>
     <div class="k">${plural(state.file_count, "file")} from the most recent migration on this
       drive can be put back. <b>Only the most recent migration on a drive is reversible</b> -
       running another migration (a trip apply, an event apply, or Move the files) replaces
       this record.</div>
     <div class="actions">
       <button class="btn btn-secondary" data-undo-preview="${esc(path)}">Preview undo…</button>
     </div>
     <div data-undo-stage></div>`
  );
}

function undoRefusalList(refused) {
  if (!refused || !refused.length) return "";
  return `<div class="banner warn"><div><div class="b-title">${plural(refused.length, "file")} left untouched</div>
    ${refused.map((r) => `<div class="mono">${esc(r.relative)} - ${esc(r.reason)}</div>`).join("")}
    </div></div>`;
}

async function refreshUndoAffordance(path, panel) {
  if (!panel) return;
  // The shared progress node may be parked inside this panel; move it home before wiping.
  const progress = $("undo-card");
  if (progress && panel.contains(progress)) {
    document.body.appendChild(progress);
    progress.classList.add("hidden");
  }
  if (!path) { panel.innerHTML = ""; return; }
  const r = await get(`/api/migrate/undo?path=${encodeURIComponent(path)}`);
  if (!r.ok || !r.armed) { panel.innerHTML = ""; return; }
  panel.innerHTML = undoArmedHtml(r, path);
  panel.querySelector("[data-undo-preview]").onclick = guarded(() => startUndoPreview(path, panel));
}

async function startUndoPreview(path, panel) {
  const previewBtn = panel.querySelector("[data-undo-preview]");
  await runJob({
    button: previewBtn,
    busyLabel: "Checking undo…",
    start: () => api("/api/migrate/undo/preview", { path }),
    setJob: (id) => { undoJob = id; },
    progress: undoProgress,
    progressLabel: "restoring",
    parkUndoCardIn: () => {
      let stage = panel.querySelector("[data-undo-stage]");
      if (!stage) {
        panel.innerHTML = undoArmedHtml({ file_count: 0 }, path);
        stage = panel.querySelector("[data-undo-stage]");
      }
      return stage;
    },
    onRefuse: (started) => {
      panel.innerHTML = startRefusedCard(started, panel.id === "mig-undo-panel" ? "mig-path" : "ev-source");
    },
    statusVerb: "Checking undo",
    onError: (d) => {
      panel.querySelector("[data-undo-stage]").innerHTML = jobErrorCard(d);
    },
    onCancelled: (d) => {
      panel.querySelector("[data-undo-stage]").innerHTML = card(
        `<div class="headline">Preview cancelled</div><div class="k">Nothing was changed. Preview again when you are ready.</div>`);
    },
    onSuccess: (d) => {
      const stage = panel.querySelector("[data-undo-stage]");
      const s = d.summary;
      stage.innerHTML =
        `<div class="headline">${plural(s.reversed_files, "file")} can be put back</div>
         ${undoRefusalList(s.refused)}
         <div data-typed-host></div>`;
      typedConfirm(stage.querySelector("[data-typed-host]"), {
        word: "undo",
        label: `Type undo to put ${plural(s.reversed_files, "file")} back`,
        buttonLabel: "Put them back",
        onConfirm: () => startUndoApply(path, panel),
      });
    },
  });
}

async function startUndoApply(path, panel) {
  const go = panel.querySelector("[data-typed-go]");
  let summaryHtml;
  await runJob({
    button: go,
    busyLabel: "Putting files back…",
    start: () => api("/api/migrate/undo/apply", { path }),
    setJob: (id) => { undoJob = id; },
    progress: undoProgress,
    progressLabel: "restoring",
    parkUndoCardIn: () => {
      let stage = panel.querySelector("[data-undo-stage]");
      if (!stage) {
        panel.innerHTML = `<div data-undo-stage></div>`;
        stage = panel.querySelector("[data-undo-stage]");
      }
      return stage;
    },
    onRefuse: (started) => {
      panel.innerHTML = startRefusedCard(started, panel.id === "mig-undo-panel" ? "mig-path" : "ev-source");
    },
    statusVerb: "Putting files back",
    onCancelled: (d) => {
      summaryHtml = card(
        `<div class="headline">Stopped</div>
         <div class="k">Put ${plural(d.summary.reversed_files || 0, "file")} back before you stopped it.</div>
         ${undoRefusalList(d.summary.refused)}`);
    },
    onSuccess: (d) => {
      summaryHtml = card(
        `<div class="headline">Put ${plural(d.summary.reversed_files, "file")} back.</div>
         ${undoRefusalList(d.summary.refused)}`);
    },
    onError: (d) => { summaryHtml = jobErrorCard(d); },
    after: async () => {
      await refreshUndoAffordance(path, panel);
      // Prepend the outcome without re-parsing the armed card: assigning panel.innerHTML
      // would wipe the Preview onclick refreshUndoAffordance just attached, and a cancelled
      // apply that left rows would show a dead button (resume impossible from the UI).
      panel.insertAdjacentHTML("afterbegin", summaryHtml);
      loadCustody();
    },
  });
}

function backupCompletion(r) {
  const notes = [];
  if (r.verified) {
    notes.push(`<div class="banner"><div><b>Every copy verified.</b> Each file was re-read from
      ${esc(r.to || "the drive")} and checked against its original before being recorded — a copy
      that did not match would have stopped the run.</div></div>`);
  }
  notes.push(`<div class="k" style="margin-top:var(--space-3)">Check this drive again any time
    with <b>Check a connected backup drive</b> above — a backup is only as good as its last
    check.</div>`);
  return completionCard({
    done: r.cancelled ? "Stopped" : "Done",
    headline: `${mediaCount(r)} copied to ${esc(r.to || "the drive")}`
      + (r.cancelled ? " before you stopped it" : ""),
    sub: "Your library now lives in more than one place.",
    stats: [
      { value: fmtBytes(r.bytes_copied), label: "copied" },
      r.elapsed_seconds ? { value: fmtDuration(r.elapsed_seconds), label: "taken" } : null,
    ],
    notes,
  });
}

// Any completed operation that changes drive state refreshes everything that describes it.
// Without this the page contradicts itself: after a successful copy the Check section still
// showed "this folder isn't a Truestill backup yet" about the drive now listed above it.
async function refreshDriveState() {
  $("verify-result").innerHTML = "";  // a verdict about the old state is not about this one
  await Promise.all([loadDrives(), loadCustody()]);
}

// ---------- navigation ----------
function showScreen(name) {
  document.querySelectorAll(".screen").forEach((s) => s.classList.toggle("active", s.id === `screen-${name}`));
  // Land at the top. Switching screens is a class toggle, not a page load, so nothing resets
  // the scroller and the offset used to survive into the next screen - the second half of
  // papercut #9, "lands the next screen scrolled down into empty space".
  // BOTH are reset on purpose: `.main` is the scroller above the 720px breakpoint and the
  // document is the scroller below it, so resetting only one leaves the defect at one width.
  const main = document.querySelector(".main");
  if (main) main.scrollTop = 0;
  window.scrollTo(0, 0);
  document.querySelectorAll(".nav-item").forEach((n) =>
    n.setAttribute("aria-current", n.dataset.screen === name ? "page" : "false"));
  if (name === "backups") loadDrives();
  if (name === "settings") {
    loadLayout();
    refreshUndoAffordance($("mig-path").value.trim(), $("mig-undo-panel"));
  }
  if (name === "events") {
    refreshUndoAffordance($("ev-source").value.trim(), $("ev-undo-panel"));
  }
  if (name === "organize") {
    refreshOrganizeUndoAffordance();
  }
  if (name === "stats") {
    loadStats();
  }
}
document.querySelectorAll(".nav-item").forEach((item) => { item.onclick = () => showScreen(item.dataset.screen); });

// ---------- collapsible sidebar (catalog-persisted; no localStorage) ----------
let sidebarLoadGeneration = 0;

function sidebarIsCollapsed() {
  return $("sidebar").dataset.collapsed === "true";
}

function applySidebarCollapsed(collapsed) {
  const sidebar = $("sidebar");
  const toggle = $("sidebar-toggle");
  const app = document.querySelector(".app");
  const next = !!collapsed;
  sidebar.dataset.collapsed = next ? "true" : "false";
  app.classList.toggle("sidebar-collapsed", next);
  const label = next ? "Expand" : "Collapse";
  toggle.setAttribute("aria-expanded", next ? "false" : "true");
  toggle.setAttribute("aria-label", `${label} sidebar`);
  toggle.dataset.label = label;
  const text = toggle.querySelector(".nav-label");
  const tip = toggle.querySelector(".nav-tooltip");
  if (text) text.textContent = label;
  if (tip) tip.textContent = label;
  refreshCatalogPathFit();
}

async function loadSidebar() {
  const gen = ++sidebarLoadGeneration;
  const state = await get("/api/sidebar/settings");
  if (gen !== sidebarLoadGeneration) return;
  applySidebarCollapsed(!!state.collapsed);
}

async function saveSidebarCollapsed(collapsed) {
  await api("/api/sidebar/settings", { collapsed: !!collapsed });
}

$("sidebar-toggle").onclick = guarded(async () => {
  sidebarLoadGeneration += 1; // invalidate any in-flight settings load
  const next = !sidebarIsCollapsed();
  applySidebarCollapsed(next);
  // Keep focus on the toggle so collapsing never traps or drops the keyboard user.
  $("sidebar-toggle").focus();
  await saveSidebarCollapsed(next);
});

// Re-query when the connected-drive path changes - the catalog answer is per drive, not per
// session, and a Browse into a different drive must update the affordance without a reload.
[["ev-source", "ev-undo-panel"], ["mig-path", "mig-undo-panel"]].forEach(([inputId, panelId]) => {
  const input = $(inputId);
  if (!input) return;
  input.addEventListener("change", () => refreshUndoAffordance(input.value.trim(), $(panelId)));
});

// ---------- custody strip (always true, catalog-driven) ----------
// Fields the catalog can already answer are filled in, never asked for. Browse stays, for
// overriding -- but a user should never have to go and find what we already know.
function prefill(id, value) {
  const el = $(id);
  // Never write into a field the user (or a test driver) is editing. A late custody
  // response used to refill an emptied Check field mid-keystroke, so the typed backup
  // path was appended to the library path and then carried into "To".
  if (el && value && !el.value && document.activeElement !== el) el.value = value;
}

function pathBasename(path) {
  const i = Math.max(path.lastIndexOf("/"), path.lastIndexOf("\\"));
  return i >= 0 ? path.slice(i + 1) : path;
}

/** Paint a middle-ellipsis label that keeps the path start and the filename; full path stays
 *  in ``data-full`` / ``title`` and remains selectable. Never shortens the stored path. */
function fitCatalogPath(el) {
  if (!el) return;
  const full = el.dataset.full || "";
  if (!full) return;
  el.title = full;
  el.textContent = full;
  if (el.clientWidth <= 0 || el.scrollWidth <= el.clientWidth) return;
  const name = pathBasename(full);
  const head = full.slice(0, Math.max(0, full.length - name.length));
  let lo = 0;
  let hi = head.length;
  while (lo < hi) {
    const mid = Math.ceil((lo + hi) / 2);
    el.textContent = `${head.slice(0, mid)}…${name}`;
    if (el.scrollWidth <= el.clientWidth) lo = mid;
    else hi = mid - 1;
  }
  el.textContent = lo > 0 ? `${head.slice(0, lo)}…${name}` : `…${name}`;
  // If even "…filename" will not fit, the honest answer is to show nothing rather than a
  // fragment: `…e` identifies no file and reads as damage. The full path stays in `title` and
  // `data-full`, so it is still reachable and still selectable.
  el.classList.remove("too-narrow");
  if (el.scrollWidth > el.clientWidth) {
    el.textContent = full;
    el.classList.add("too-narrow");
  }
}

/** Re-fit whenever the box actually changes size, not only when the text is written.
 *
 *  THE `…e` DEFECT. `fitCatalogPath`'s last resort shortens the FILENAME one character at a
 *  time while the box is narrower than `…filename`, so a measurement taken while the rail is
 *  mid-animation - the shell transitions its columns over 160ms - ate `catalog.sqlite` down to
 *  a single letter and left it there. The label is only re-painted when `loadCustody` runs, so
 *  the fragment then survived until the next custody refresh, which is why it was visible in a
 *  screenshot rather than being a flicker.
 *
 *  A ResizeObserver answers the real question: fit the label to the box it actually has, every
 *  time that box settles. Cheaper than a timer and correct for the window resize case too,
 *  which nothing handled before.
 */
let catalogFitObserver = null;

function refreshCatalogPathFit() {
  const el = $("custody-catalog");
  if (!el) return;
  fitCatalogPath(el);
  if (catalogFitObserver) catalogFitObserver.disconnect();
  if (typeof ResizeObserver === "undefined") return;
  catalogFitObserver = new ResizeObserver(() => fitCatalogPath(el));
  catalogFitObserver.observe(el);
}

async function loadCustody() {
  const s = await get("/api/library/status");
  // Organize and Trips work on the library; Backups copies *from* it to somewhere else.
  prefill("org-dest", s.library_path);
  prefill("ev-source", s.library_path);
  prefill("bk-source", s.library_path);
  prefill("verify-path", s.backup_path || s.library_path);
  prefill("bk-target", s.backup_path);
  const pips = $("custody-pips"), line = $("custody-line");
  // PER-FILE, NOT PER-DRIVE. This used to read `safe in N places` with N = the number of drives
  // holding any copy, which is a per-drive count under a per-file sentence. Organize into drive
  // A, then into drive B with no overlap, and every file is in exactly one place while the strip
  // said "safe in 2 places". `redundancy_floor` is the weakest file's copy count, so one
  // unprotected file holds it down and the strip can never over-promise.
  const noCopy = s.files_no_copy || 0;
  const oneCopy = s.files_one_copy || 0;
  const onADrive = s.files_on_a_drive || 0;
  const heldFloor = s.held_floor || 0;
  // `places` picks the STATE and never becomes the number in a sentence. Writing a per-file
  // claim against a per-drive count is the defect this whole strip was rebuilt to remove.
  const anyDrive = (s.places || 0) > 0;
  // RISK is exposure among files that HAVE a home: one copy and no more. A file with no copy at
  // all is a Stats finding, not a rail sentence - it cannot be acted on from here.
  const atRisk = oneCopy > 0;
  const filled = s.files && onADrive ? Math.min(heldFloor, 3) : 0;
  pips.textContent = [0, 1, 2].map((i) => (i < filled ? "▪" : "▫")).join(" ");
  pips.classList.toggle("none", filled === 0);
  pips.classList.toggle("at-risk", atRisk);
  // RISK FIRST: an exposed file is a reason to act, so it is what the strip says. The
  // reassurance is only offered when it is true of every file, never as an average.
  // `files_no_copy` is named separately because `single_copy_count` cannot see it - that query
  // reads FROM file_copies, so a file with no copy row at all is in neither bucket.
  // Four states. NEUTRAL is not a lesser amber - it is a different fact.
  //  - nothing organized yet          : empty catalog, never reassured about
  //  - not on a backup drive yet      : NEUTRAL. No drive holds anything, which is where an
  //    rclone user permanently lives ("always-online cloud, not drives-in-a-drawer") and where
  //    anyone is before their first registered destination. Progress, not risk.
  //  - N files in only one place      : AMBER. Exposure with a remedy the user can act on.
  //  - every file / N files in M places: reassured. The universal is used ONLY when no file
  //    is missing a copy entirely; otherwise the count, because "every" would exclude rows in
  //    silence and that is the defect this strip was rebuilt to remove.
  const safe = !s.files ? "nothing organized yet"
    : !anyDrive ? "not on a backup drive yet"
    : oneCopy ? `${WARN_MARK}${plural(oneCopy, "file")} in only one place`
    : noCopy ? `${plural(onADrive, "file")} in ${filled} places`
    : `every file in ${filled} places`;
  // One custody sentence, not an inventory. The photos/videos line that used to sit above this
  // never changed and asked nothing of anyone; custody is what this strip is for.
  const catalogPath = s.catalog_path
    ? `<div class="catalog-path mono" id="custody-catalog" data-full="${esc(s.catalog_path)}" title="${esc(s.catalog_path)}">${esc(s.catalog_path)}</div>`
    : "";
  // First-run (will_create) is calm info; empty_with_drives is the only alert-looking case.
  let catalogNote = "";
  if (s.catalog_detail) {
    const cls = s.catalog_tone === "alert" ? "banner warn" : "k";
    catalogNote = s.catalog_tone === "alert"
      ? `<div class="${cls}"><div>${esc(s.catalog_detail)}</div></div>`
      : `<div class="${cls}">${esc(s.catalog_detail)}</div>`;
  }
  const tone = atRisk ? "at-risk" : anyDrive && s.files ? "safe" : "neutral";
  line.innerHTML = `<span class="${tone}">${esc(safe)}</span>${catalogPath}${catalogNote}`;
  refreshCatalogPathFit();
}
window.addEventListener("resize", debounce(refreshCatalogPathFit, 50));

// ---------- folder picker ----------
const pk = { input: null, kind: "source", path: "" };
document.querySelectorAll("[data-browse]").forEach((btn) => {
  btn.onclick = () => openPicker($(btn.dataset.browse), btn.dataset.kind);
});
function openPicker(input, kind) {
  pk.input = input; pk.kind = kind;
  $("picker").classList.remove("hidden");
  pkNavigate(input.value.trim());
}
async function pkNavigate(path) {
  const data = await get(`/api/fs/dirs?path=${encodeURIComponent(path || "")}`);
  pk.path = data.path || "";
  $("pk-roots").innerHTML =
    `<div class="grp">Places</div>` +
    (data.roots || []).map((r) => `<button class="diritem" data-p="${esc(r.path)}">${esc(r.label)}</button>`).join("");
  const segs = pk.path ? pk.path.split("/").filter(Boolean) : [];
  let acc = "";
  const crumbs = [`<a data-p="/">/</a>`].concat(segs.map((s) => { acc += "/" + s; return `<a data-p="${esc(acc)}">${esc(s)}</a>`; }));
  $("pk-crumbs").innerHTML = crumbs.join(" <span>›</span> ");
  const entries = data.entries || [];
  const emptyMsg = data.error ? esc(data.error) : pk.path ? "No sub-folders here." : "Pick a place on the left to start.";
  $("pk-dirs").innerHTML = entries.length
    ? entries.map((e) => `<button class="diritem" data-p="${esc(e.path)}">${esc(e.name)}</button>`).join("")
    : `<div class="empty">${emptyMsg}</div>`;
  $("picker").querySelectorAll(".diritem, .crumbs a").forEach((n) => { n.onclick = () => pkNavigate(n.dataset.p); });
  updateUse();
}
async function updateUse() {
  const use = $("pk-use"), sel = $("pk-sel");
  if (!pk.path) { use.disabled = true; use.textContent = "Use this folder"; sel.textContent = "Pick a place on the left to start"; return; }
  sel.textContent = pk.path;
  use.disabled = false;
  use.textContent = "Use this folder";
  const v = await get(`/api/fs/validate?path=${encodeURIComponent(pk.path)}`);
  if (v.unreadable) {
    // Offering a folder Truestill cannot read would hand the failure to the next screen.
    use.disabled = true;
    use.textContent = "Can't read this folder";
    return;
  }
  const n = v.media_capped ? `${v.media}+` : v.media;
  if (pk.kind === "source") use.textContent = v.media > 0 ? `Use this folder · ${n} photos or videos` : "Use this folder · no photos or videos";
  else use.textContent = v.is_drive ? "Use this backup drive" : "Use this folder";
}
$("pk-use").onclick = () => {
  pk.input.value = pk.path;
  $("picker").classList.add("hidden");
  pk.input.dispatchEvent(new Event("change"));
};
$("pk-cancel").onclick = () => $("picker").classList.add("hidden");
$("picker").onclick = (e) => { if (e.target === $("picker")) $("picker").classList.add("hidden"); };

// ---------- inline path validation (guardrail a) - live, both fields ----------
async function validatePath(input, hint, kind) {
  const path = input.value.trim();
  if (!path) { hint.innerHTML = ""; hint.className = "hint"; return null; }
  const v = await get(`/api/fs/validate?path=${encodeURIComponent(path)}`);
  // Checked before the source/destination split: the folder is there and the OS will not
  // describe it, which is the same answer either way -- and specifically NOT "doesn't exist",
  // because that branch offers "Create it" and the create fails with the same refusal.
  if (v.unreadable) {
    hint.textContent = "Truestill can't read this folder. Check its permissions, or pick another one.";
    hint.className = "hint warn";
    return v;
  }
  if (kind === "source") {
    if (!v.exists || !v.is_dir) { hint.textContent = "That folder cannot be used. Check the path, then pick an existing folder."; hint.className = "hint warn"; return v; }
    const n = v.media_capped ? `${v.media}+` : v.media;
    if (v.media > 0) { hint.textContent = `${n} photos and videos here`; hint.className = "hint ok"; }
    else { hint.textContent = "No photos or videos are in this folder yet."; hint.className = "hint warn"; }
    return v;
  }
  // destination: new backup folders are the normal case, so offer to create, don't just warn.
  if (!v.exists) {
    hint.className = "hint warn";
    hint.innerHTML = `This folder doesn’t exist yet. <button class="btn btn-ghost pk-create" style="padding:0;color:var(--accent);text-decoration:underline">Create it</button>`;
    hint.querySelector(".pk-create").onclick = guarded(async () => {
      hint.textContent = "Creating…";
      const r = await api("/api/fs/create", { path });
      if (r.created) validatePath(input, hint, kind);
      else { hint.textContent = `Could not create this folder. ${r.error || "Unknown reason."} Choose another folder or create it with your file manager.`; hint.className = "hint warn"; }
    });
  } else if (!v.is_dir) { hint.textContent = "That path is a file, not a folder. Pick a folder."; hint.className = "hint warn"; }
  else if (!v.writable) { hint.textContent = "This folder is read-only. Pick a folder you can write to."; hint.className = "hint warn"; }
  else { hint.textContent = v.is_drive ? "Ready · backup drive ✓" : "Ready"; hint.className = "hint ok"; }
  return v;
}
// Both of these name the same thing -- the backup drive -- on one page: "Drive folder" in
// Check, "To" in Copy. Typing it once should be enough. (`bk-source` is deliberately absent:
// that is the *library*, a different concept that happens to also be a folder.)
const BACKUP_DRIVE_FIELDS = ["verify-path", "bk-target"];

function offerBackupPath(fromId) {
  const value = $(fromId).value.trim();
  if (!value) return;
  for (const id of BACKUP_DRIVE_FIELDS) {
    if (id === fromId) continue;
    const el = $(id);
    if (!el || el.value.trim()) continue;  // never overwrite something the user typed
    el.value = value;
    // Validate it exactly as if typed, so the hint ("Ready", "doesn't exist yet - Create it")
    // is about the value now in the box rather than the empty one it replaced.
    el.dispatchEvent(new Event("change"));
    $(`${id}-carried`)?.classList.remove("hidden");
  }
}

// Only user input carries a value across. `prefill()` assigns without dispatching, so the
// catalog's own suggestions never trigger this -- which matters, because the Check field is
// prefilled with the *library* path when no backup exists yet, and silently proposing that as
// the copy target would be offering to copy the library onto itself.
BACKUP_DRIVE_FIELDS.forEach((id) => {
  const el = $(id);
  if (!el) return;
  el.addEventListener("change", () => offerBackupPath(id));
  el.addEventListener("blur", () => offerBackupPath(id));
  // Once the user edits a carried-over value it is theirs, so stop calling it a suggestion.
  el.addEventListener("input", () => $(`${id}-carried`)?.classList.add("hidden"));
});

// wire every path field (source + destination) to validate live as you type and on pick
document.querySelectorAll("[data-browse]").forEach((btn) => {
  const input = $(btn.dataset.browse);
  const hint = $(`${btn.dataset.browse}-hint`);
  if (!input || !hint) return;
  const run = () => validatePath(input, hint, btn.dataset.kind);
  input.addEventListener("input", debounce(run, 400));
  input.addEventListener("change", run);
});

// ---------- Organize ----------
function setWhy(text) { $("org-why").textContent = text; }
let orgMode = "copy";
let organizeModeLoadGeneration = 0;
let orgMechanism = null;
let orgUndoJob = null;
let cleanupOffer = null;

function currentOrganizeMode() {
  const picked = document.querySelector('input[name="org-mode"]:checked');
  return picked ? picked.value : "copy";
}

function organizeNeedsDestination(mode) {
  return mode !== "inplace";
}

function modeLine(mode) {
  if (mode === "copy") return "Originals stay where they are.";
  if (mode === "move") return "Originals are removed only after copy verification.";
  return "This mode reorganizes in this same folder by rename only, and never falls back to copy. In the CLI, this is --in-place.";
}

function modeMechanismLine(mode, mechanism) {
  if (mode === "copy") return "This run copies files into the organized folder.";
  if (!mechanism || !mechanism.same_filesystem) {
    if (mode === "move") {
      return "Source and destination are on different filesystems: this run will copy, verify, then delete each source.";
    }
    return "In-place requires rename on one filesystem. This run will refuse instead of copying.";
  }
  if (mode === "move") return "Source and destination share one filesystem: this run will move by rename.";
  return "This run reorganizes in place by rename on this filesystem.";
}

function reversibilityLine(mechanism) {
  return mechanism && mechanism.reversible
    ? "This run is reversible with undo-organize."
    : "This run is not reversible with undo-organize.";
}

async function loadOrganizeMode() {
  const gen = ++organizeModeLoadGeneration;
  const state = await get("/api/organize/settings");
  // A user change while this request was in flight must win; do not clobber it.
  if (gen !== organizeModeLoadGeneration) return;
  orgMode = state.mode || "copy";
  const input = document.querySelector(`input[name="org-mode"][value="${orgMode}"]`);
  if (input) input.checked = true;
  renderOrganizeMode();
}

function renderOrganizeMode() {
  orgMode = currentOrganizeMode();
  const needsDest = organizeNeedsDestination(orgMode);
  $("org-dest-field").classList.toggle("hidden", !needsDest);
  $("org-mode-hint").textContent = modeLine(orgMode);
  $("org-confirm").innerHTML = "";
  if (!needsDest) {
    $("org-dest-hint").textContent = "Reorganize in this same folder uses the source folder as the destination. In the CLI, this is --in-place.";
    $("org-dest-hint").className = "hint";
  }
}

async function saveOrganizeMode(mode) {
  await api("/api/organize/settings", { mode });
}

function renderOrganizeRunConfirm({ kept, mode, mechanism }) {
  const host = $("org-confirm");
  const lines = [
    modeMechanismLine(mode, mechanism),
    reversibilityLine(mechanism),
  ];
  host.innerHTML =
    `<div class="banner">
      <div>
        <div class="b-title">Before you organize</div>
        <div>${esc(lines[0])}</div>
        <div>${esc(lines[1])}</div>
        ${mode === "inplace" ? `<div>Originals do not stay in their current folders.</div>` : ""}
        <div class="k" style="margin-top:var(--space-2)">Type <code>move</code> to continue.</div>
      </div>
    </div>
    <div data-org-typed></div>`;
  typedConfirm(host.querySelector("[data-org-typed]"), {
    word: "move",
    label: `Type move to organize ${plural(kept, "file")}`,
    buttonLabel: `Organize ${nfmt(kept)} files`,
    onConfirm: () => startOrganizeRun(),
  });
}

function organizeUndoCard(state) {
  return card(
    `<div class="headline">Undo the last reversible organize run</div>
     <div class="k">${plural(state.restorable, "file")} can be put back where they were before this rename-based organize run.
      This uses <code>truestill undo-organize</code> semantics.</div>
     <div class="actions">
       <button class="btn btn-secondary" id="org-undo-preview">Preview undo…</button>
     </div>
     <div id="org-undo-stage"></div>`
  );
}

async function refreshOrganizeUndoAffordance() {
  const panel = $("org-undo-panel");
  const state = await get("/api/organize/undo");
  if (!state.ok || !state.armed) {
    panel.innerHTML = "";
    return;
  }
  panel.innerHTML = organizeUndoCard(state);
  panel.querySelector("#org-undo-preview").onclick = guarded(startOrganizeUndoPreview);
}

function organizeUndoSkipped(skipped) {
  if (!skipped || !skipped.length) return "";
  return `<div class="banner warn"><div><div class="b-title">${plural(skipped.length, "file")} could not be restored</div>
    ${skipped.map((r) => `<div class="mono">${esc(r.relative)} - ${esc(r.detail || r.reason)}</div>`).join("")}
  </div></div>`;
}

// What actually happened to the folders, named per disposition rather than summed.
//
// `removed` is a DERIVED property - trashed + deleted - so rendering it added core's two
// answers together and threw away the only distinction that matters afterwards: whether a
// folder is recoverable from the trash or gone. The CLI has always split them.
//
// Built from whichever counts are non-zero, which is `dupOrigins`' shape and, since 2026-08-04,
// the only one that stays honest: an absent trash backend is a refusal, so `deleted` is now
// non-zero only under `clean-empty --permanent`, which the app does not offer. A hand-written
// "N moved to the trash" would therefore be right today and wrong the day an app permanent mode
// exists. A zero bucket prints nothing - never-silent is about what happened, not what did not.
//
// Complexity: O(1). Two integers already in the payload; nothing is re-counted or re-read.
function cleanupDisposition(applied) {
  const parts = [];
  if (applied.trashed) parts.push(`${plural(applied.trashed, "folder")} moved to the trash`);
  if (applied.deleted) parts.push(`${plural(applied.deleted, "folder")} deleted permanently`);
  // Never "Removed 0 folders": a run that removed nothing is not a removal, and the failures
  // banner below it carries the reason for each one.
  return parts.length ? `${esc(parts.join(", "))}.` : "No folders were removed.";
}

function cleanupOfferNote(cleanup) {
  if (!cleanup || !cleanup.count) return "";
  const listed = cleanup.folders.slice(0, 8).map((name) => `<div class="mono">${esc(name)}</div>`).join("");
  const more = cleanup.folders.length > 8
    ? `<div class="k">…and ${nfmt(cleanup.folders.length - 8)} more</div>`
    : "";
  return `<div class="banner warn"><div>
    <div class="b-title">${plural(cleanup.count, "empty folder")} left behind</div>
    <div>Files were restored/moved, but folders are never auto-deleted.</div>
    ${listed}${more}
    <div class="actions">
      <button class="btn btn-secondary" data-clean-preview>Review empty-folder cleanup…</button>
    </div>
    <div data-clean-stage></div>
  </div></div>`;
}

async function startCleanupPreview(button) {
  if (!cleanupOffer) return;
  const host = button.closest(".banner");
  const stage = host ? host.querySelector("[data-clean-stage]") : null;
  if (!stage) return;
  await withBusy(button, "Checking empty folders…", async () => {
    const preview = await api("/api/clean-empty/preview", {
      path: cleanupOffer.source_root,
      emptied: cleanupOffer.emptied,
    });
    if (!preview.removable.length) {
      stage.innerHTML = card("<div class='k'>Nothing to remove now.</div>");
      return;
    }
    // No trash on this machine is a REFUSAL now, not a permanent delete (core `run_cleanup`,
    // 2026-08-04). This branch used to read "permanently (no trash backend available)" and then
    // offer the typed confirm anyway - a sentence describing something the run can no longer do,
    // followed by a button that could only ever report failures. The app has no `--permanent`,
    // by the same App-surface-deferral reasoning that keeps `reclaim` on the CLI: an
    // irreversible removal is not a thing to reach for by accident.
    if (!preview.backend) {
      // A refusal that names no route is a dead end, and this one has a route: the CLI's
      // --permanent, which exists for exactly this case and asks for `delete forever` rather
      // than `clean`. Naming it is not a suggestion to use it - it is the difference between
      // "you cannot do this" and "you cannot do this here".
      stage.innerHTML = card(
        `<div class="banner warn" data-testid="clean-no-trash"><div>
         <div class="b-title">These folders cannot be removed here</div>
         <div>This computer has no trash Truestill can use, and Truestill will not delete a
         folder outright. ${plural(preview.removable.length, "folder")} left exactly where
         ${preview.removable.length === 1 ? "it is" : "they are"} - nothing was changed.</div>
         <div class="k">To remove them anyway, from a terminal:</div>
         <div class="mono">truestill clean-empty ${esc(cleanupOffer.source_root)} --apply --permanent</div>
         <div class="k">That deletes them outright and cannot be undone, so it asks you to type
         <code>delete forever</code> rather than <code>clean</code>.</div></div></div>`
      );
      return;
    }
    const where = `to the trash (${preview.backend})`;
    stage.innerHTML = `<div class="k">${plural(preview.removable.length, "folder")} can be removed ${esc(where)}.</div>
      <details class="more"><summary>Show folders ▾</summary><div class="mono">${preview.removable.map((p) => esc(p)).join("<br>")}</div></details>
      <div data-org-clean-typed></div>`;
    typedConfirm(stage.querySelector("[data-org-clean-typed]"), {
      word: "clean",
      label: `Type clean to remove ${plural(preview.removable.length, "folder")}`,
      buttonLabel: "Remove empty folders",
      onConfirm: async () => {
        const applied = await api("/api/clean-empty/apply", {
          path: cleanupOffer.source_root,
          emptied: cleanupOffer.emptied,
        });
        stage.innerHTML = card(
          `<div class="headline">${cleanupDisposition(applied)}</div>
           ${applied.failures && applied.failures.length
            ? `<div class="banner warn"><div>${applied.failures.map((f) => esc(f)).join("<br>")}</div></div>`
            : ""}`
        );
      },
    });
  });
}

async function startOrganizeUndoPreview() {
  const previewBtn = $("org-undo-preview");
  await runJob({
    button: previewBtn,
    busyLabel: "Checking undo…",
    start: () => api("/api/organize/undo/preview", {}),
    setJob: (id) => { orgUndoJob = id; },
    progress: undoProgress,
    progressLabel: "checking",
    parkUndoCardIn: () => $("org-undo-stage"),
    onRefuse: (started) => {
      // Mirror migrate-undo: a DriveBusy / soft-fail must not enter awaitJob with no job id.
      $("org-undo-panel").innerHTML = startRefusedCard(started, "org-source");
    },
    abortStart: async (started) => {
      if (started.ok === true && started.armed === false) {
        await refreshOrganizeUndoAffordance();
        return true;
      }
      return false;
    },
    statusVerb: "Checking undo",
    onError: (d) => { $("org-undo-stage").innerHTML = jobErrorCard(d); },
    onCancelled: () => {
      $("org-undo-stage").innerHTML = card(
        `<div class="headline">Preview cancelled</div><div class="k">Nothing was changed. Preview again when you are ready.</div>`);
    },
    onSuccess: (d) => {
      const stage = $("org-undo-stage");
      const s = d.summary;
      stage.innerHTML = `<div class="headline">${plural(s.restorable, "file")} can be restored</div>
        ${organizeUndoSkipped(s.skipped)}
        <div data-org-undo-typed></div>`;
      typedConfirm(stage.querySelector("[data-org-undo-typed]"), {
        word: "undo",
        label: `Type undo to restore ${plural(s.restorable, "file")}`,
        buttonLabel: "Put them back",
        onConfirm: () => startOrganizeUndoApply(),
      });
    },
  });
}

async function startOrganizeUndoApply() {
  const go = document.querySelector("#org-undo-stage [data-typed-go]");
  let summaryHtml;
  await runJob({
    button: go,
    busyLabel: "Putting files back…",
    start: () => api("/api/organize/undo/apply", {}),
    setJob: (id) => { orgUndoJob = id; },
    progress: undoProgress,
    progressLabel: "restoring",
    parkUndoCardIn: () => $("org-undo-stage"),
    onRefuse: (started) => {
      $("org-undo-panel").innerHTML = startRefusedCard(started, "org-source");
    },
    abortStart: async (started) => {
      if (started.ok === true && started.armed === false) {
        await refreshOrganizeUndoAffordance();
        return true;
      }
      return false;
    },
    statusVerb: "Restoring",
    onCancelled: (d) => {
      summaryHtml = card(
        `<div class="headline">Stopped</div>
         <div class="k">Restored ${plural(d.summary.restored || 0, "file")} before you stopped it.</div>
         ${organizeUndoSkipped(d.summary.skipped)}`);
    },
    onSuccess: (d) => {
      summaryHtml = card(
        `<div class="headline">Restored ${plural(d.summary.restored, "file")}.</div>
         ${organizeUndoSkipped(d.summary.skipped)}`);
    },
    onError: (d) => { summaryHtml = jobErrorCard(d); },
    after: async (d) => {
      if (d.ok) loadCustody();
      await refreshOrganizeUndoAffordance();
      // Prepend the outcome without re-parsing the armed card: assigning panel.innerHTML
      // would wipe the outcome refreshOrganizeUndoAffordance just cleared (spent journal) or
      // rewrote (still armed after a failed apply) - the migrate-undo twin fixed this first.
      $("org-undo-panel").insertAdjacentHTML("afterbegin", summaryHtml);
    },
  });
}

// Renders WHATEVER groups the payload carries, rather than the three it used to name by hand.
// That hand-kept list is the third copy of one vocabulary this repo has been bitten by: adding
// `hidden` in core would have left the app silently short, which is precisely the "skipped but
// never counted" defect the group exists to fix. The engine decides what the groups are; this
// decides how they look. Keys are snake_case there and read as words here.
function renderSkippedDetails(sk) {
  const groups = Object.entries(sk || {})
    .map(([name, counts]) => [name, Object.entries(counts || {})])
    .filter(([, entries]) => entries.length);
  const skTotal = groups.reduce((a, [, entries]) => a + entries.reduce((b, [, n]) => b + n, 0), 0);
  if (!skTotal) return "";
  const rows = groups
    .map(([name, entries]) =>
      `<tr><td>${esc(name.replace(/_/g, " "))}</td><td class="num">${entries
        .map(([e, n]) => `${esc(e)} ×${n}`)
        .join(", ")}</td></tr>`)
    .join("");
  return `<details class="more"><summary>${plural(skTotal, "file")} skipped (not photos or videos) ▾</summary>
    <table class="table"><tbody>${rows}</tbody></table></details>`;
}

// What Truestill could not read, on the preview that is supposed to predict the run.
//
// Both halves render here because they are one question to a user - "did you see everything of
// mine?" - even though they are two different facts underneath. `unreadable_folders` shipped in
// the payload and was never rendered at all, so a folder Truestill could not open produced a
// clean-looking preview; adding its file sibling while leaving that unrendered would have
// rebuilt the same silence one layer down.
//
// FILES CARRY A COUNT AND FOLDERS DO NOT, deliberately. For a folder the number of files inside
// is exactly what could not be read, so stating one would invent the missing figure. For a file
// the number is known exactly. Do not "make these consistent".
function renderUnreadable(s) {
  const files = s.unreadable_files || { total: 0, shown: [] };
  const folders = s.unreadable_folders || [];
  if (!files.total && !folders.length) return "";
  const fileRows = files.shown
    .map((f) => `<div class="mono">${esc(f.name)} - ${esc(f.reason)}</div>`)
    .join("");
  // Truncation is never silent: if the payload capped the list, say how many are not shown.
  const more = files.total > files.shown.length
    ? `<div class="k">… and ${nfmt(files.total - files.shown.length)} more.</div>` : "";
  const filesBlock = files.total
    ? `<div class="b-title">${plural(files.total, "file")} could not be read</div>
       ${fileRows}${more}
       <div class="k">Not organized. Fix the permission or check the disk, then preview again.</div>`
    : "";
  const folderRows = folders
    .map((f) => `<div class="mono">${esc(f)} - contents unknown</div>`)
    .join("");
  const foldersBlock = folders.length
    ? `<div class="b-title">${plural(folders.length, "folder")} could not be opened</div>
       ${folderRows}
       <div class="k">Whatever is inside was not counted. Check the folder's permissions, then preview again.</div>`
    : "";
  return `<div class="banner warn" data-testid="org-unreadable"><div>${filesBlock}${foldersBlock}</div></div>`;
}

function renderInventoryResult(s) {
  if (!s.files) {
    $("org-result").innerHTML = card(
      `<div class="banner warn"><div><div class="b-title">Nothing to organize here</div>
       <div>No photos or videos in this folder - is it the right one?</div></div></div>`
    );
    return;
  }
  $("org-result").innerHTML = card(
    `<div class="headline">${mediaCount(s)} found</div>
     <div class="k">${fmtBytes(s.total_bytes || 0)} of media - no dates or duplicates checked yet</div>
     ${byFormat(s.by_format)}${renderSkippedDetails(s.skipped)}
     <div class="banner"><div>Next: check for duplicates (reads each file for dates and look-alikes).
       That is the slow step on a network drive.</div></div>`
  );
}

function renderOrganizeResult(s) {
  if (!s.files) {
    // The unreadable block goes FIRST here: when a folder could not be opened, "nothing to
    // organize" is very likely the wrong answer, and the reason must be read before it.
    $("org-result").innerHTML = card(
      `${renderUnreadable(s)}
       <div class="banner warn"><div><div class="b-title">Nothing to organize here</div>
       <div>No photos or videos in this folder - is it the right one?</div></div></div>`
    );
    return;
  }
  const kept = (s.new_unique || 0) + (s.near_dup || 0);
  const folders = chipsFor(s.folders);
  const legend = legendFor(s.folders);
  const details = renderSkippedDetails(s.skipped);
  const heic = s.heic_perceptual_skipped ? `<div class="banner warn"><div>${plural(s.heic_perceptual_skipped, "HEIC file")} will be backed up, but near-duplicate detection is unavailable for them.</div></div>` : "";
  const dateQuality = dateQualityNotes(s);
  const inferredShifts = inferredLocalShiftNotes(s);
  // Shown above the tallies, not below them: it decides whether the run can happen at all, so
  // it must be read before the confirm control the preview puts on screen next.
  const limit = s.destination_limit
    ? `<div class="banner warn" data-testid="org-destination-limit"><div>
       <div class="b-title">This drive cannot hold this run</div>
       <div>${esc(s.destination_limit.detail)}</div></div></div>`
    : "";
  // Above the tallies too, and for the same reason: a count of what "will be organized" is
  // only as true as the set of files Truestill managed to read.
  const unreadable = renderUnreadable(s);
  $("org-result").innerHTML = card(
    `<div class="headline">${mediaCount(s)} found</div>
     ${s.elapsed_seconds ? `<div class="k">checked in ${fmtDuration(s.elapsed_seconds)}</div>` : ""}
     ${limit}${unreadable}
     <div class="tally">
       <div class="n">${nfmt(s.new_unique)}</div><div class="k">new - will be organized</div>
       <div class="n">${nfmt(s.near_dup)}</div><div class="k">look-alikes - kept and flagged</div>
       <div class="n">${nfmt(s.exact_dup)}</div><div class="k">duplicates - not copied again${dupOrigins(s.exact_dup_matches)}</div>
       <div class="n">${nfmt(s.undated)}</div><div class="k">no date - will go to “Undated”</div>
     </div>
     ${matchListHtml(s.exact_dup_matches, "Show what each duplicate matched")}
     ${matchListHtml(s.near_dup_matches, "Show what each look-alike resembles")}
     ${folders ? `<h3>Into these folders <span style="font-weight:400;color:var(--text-muted)">- hover a chip for what it means</span></h3><div class="chips">${folders}</div>${legend}` : ""}
     ${byFormat(s.by_format)}${dateQuality}${inferredShifts}${heic}${details}`
  );
  return kept;
}

// Shared by preview and run: both are cancellable jobs, and Cancel needs the current one.
let orgJob = null;

$("org-preview").onclick = guarded(async () => {
  const source = $("org-source").value.trim();
  const mode = currentOrganizeMode();
  const destination = mode === "inplace" ? source : $("org-dest").value.trim();
  if (!source) { setWhy("Pick a folder to organize first."); return; }
  if (organizeNeedsDestination(mode) && !destination) {
    setWhy("Pick the organized destination folder first.");
    return;
  }
  // Cheap inventory only (walk + size). Full dedup is an explicit second step.
  await withBusy($("org-preview"), "Looking inside…", async () => {
    $("org-result").innerHTML = "";
    $("org-dedup").disabled = true;
    const s = await api("/api/organize/inventory", { source });
    renderInventoryResult(s);
    if (!s.files) {
      setWhy("Nothing to organize in this folder.");
      return;
    }
    $("org-dedup").disabled = false;
    setWhy("Check for duplicates before organizing.");
  });
});

$("org-dedup").onclick = guarded(async () => {
  const source = $("org-source").value.trim();
  const mode = currentOrganizeMode();
  const destination = mode === "inplace" ? source : $("org-dest").value.trim();
  const refresh_metadata = $("org-refresh-metadata").checked;
  if (!source) { setWhy("Pick a folder to organize first."); return; }
  if (organizeNeedsDestination(mode) && !destination) {
    setWhy("Pick the organized destination folder first.");
    return;
  }
  $("org-confirm").innerHTML = "";
  await runJob({
    button: $("org-dedup"),
    busyLabel: "Checking for duplicates…",
    start: () => api("/api/organize/preview", { source, destination, refresh_metadata, mode }),
    setJob: (id) => { orgJob = id; },
    progress: orgProgress,
    progressLabel: "starting",
    progressBeforeStart: true,
    onRefuse: (started) => {
      $("org-result").innerHTML = startRefusedCard(started, "org-dest");
    },
    statusForProgress: (p, setStatus) => {
      if (p.phase === "scanning") setStatus(scaleStatus("Reading photos", p.done, p.total, "files"));
      else if (p.phase === "hashing") setStatus(scaleStatus("Checking for duplicates", p.done, p.total, "files"));
      else if (p.total) setStatus(scaleStatus("Checking folder", p.done, p.total, "files"));
    },
    onError: (d) => { $("org-result").innerHTML = jobErrorCard(d); },
    onCancelled: () => {
      $("org-result").innerHTML = card(
        `<div class="headline">Check cancelled</div><div class="k">Nothing was changed. Check again when you are ready.</div>`);
      setWhy("Check for duplicates again to see what would happen.");
    },
    onSuccess: (d) => {
      const s = d.summary;
      const kept = renderOrganizeResult(s);
      orgMechanism = s.mechanism || null;
      if (!s.files) { setWhy("Nothing to organize in this folder."); }
      else {
        renderOrganizeRunConfirm({ kept, mode, mechanism: orgMechanism });
        setWhy("");
      }
    },
  });
});

async function startOrganizeRun() {
  const source = $("org-source").value.trim();
  const mode = currentOrganizeMode();
  const destination = mode === "inplace" ? source : $("org-dest").value.trim();
  const skip_undated = $("org-skip-undated").checked;
  const refresh_metadata = $("org-refresh-metadata").checked;
  const trigger = $("org-confirm").querySelector("[data-typed-go]");
  await runJob({
    button: trigger,
    busyLabel: "Organizing…",
    start: () => api("/api/organize/run", { source, destination, skip_undated, refresh_metadata, mode }),
    setJob: (id) => { orgJob = id; },
    progress: orgProgress,
    progressLabel: "preparing",
    onRefuse: (started) => {
      $("org-result").innerHTML = startRefusedCard(started, "org-dest");
      $("org-confirm").innerHTML = "";
    },
    statusVerb: "Organizing",
    onCancelled: (d) => {
      // A cancelled run still organized everything it reached, and those files are real.
      // Show the same card, labelled honestly, rather than implying nothing happened.
      const r = d.summary;
      $("org-result").innerHTML = organizeCompletion({ ...r, cancelled: true });
      cleanupOffer = r.leftover_empty_folders || null;
    },
    onError: (d) => {
      $("org-result").innerHTML = jobErrorCard(d);
      cleanupOffer = null;
    },
    onSuccess: (d) => {
      const r = d.summary;
      $("org-result").innerHTML = r.organized || r.outcomes
        ? organizeCompletion(r)
        : card(`<div class="headline">Nothing to organize</div><div class="k">No new photos or videos were found here.</div>`);
      cleanupOffer = r.leftover_empty_folders || null;
    },
    after: () => {
      $("org-confirm").innerHTML = "";
      loadCustody();
      refreshOrganizeUndoAffordance();
    },
  });
}

$("org-cancel").onclick = guarded(() => { if (orgJob) return api(`/api/jobs/${orgJob}/cancel`, {}); });
$("undo-cancel").onclick = guarded(() => {
  if (undoJob) return api(`/api/jobs/${undoJob}/cancel`, {});
  if (orgUndoJob) return api(`/api/jobs/${orgUndoJob}/cancel`, {});
});

document.querySelectorAll('input[name="org-mode"]').forEach((item) => {
  item.addEventListener("change", guarded(async () => {
    organizeModeLoadGeneration += 1; // invalidate any in-flight settings load
    renderOrganizeMode();
    await saveOrganizeMode(currentOrganizeMode());
    setWhy("Look inside first to see what is in the folder.");
  }));
});

// ---------- Backups ----------
// Offline is an expected state, not a failure, and the wording carries that: a drive you
// unplugged is "not plugged in", never "missing". Conflating the two is what makes a backup tool
// feel broken - the whole reason `reach` is three-valued rather than a boolean.
//
// A CONNECTED drive gets no badge on purpose. Marking the normal case trains people to ignore
// the marks, and every drive on this screen used to be implicitly "fine"; only a departure from
// that is worth a word.
function driveReachBadge(reach) {
  if (reach === "offline") {
    return `<span class="k" data-testid="drive-offline" title="Truestill knows where this drive was, and it is not there now">- not plugged in</span>`;
  }
  if (reach === "unknown") {
    return `<span class="k" data-testid="drive-unknown" title="Truestill has not seen this drive on this computer yet">- location not known yet</span>`;
  }
  return "";
}

async function loadDrives() {
  const [{ drives, at_risk }, lib] = await Promise.all([api("/api/drives"), get("/api/library/status")]);
  const list = $("drives-list");
  if (!drives.length) {
    // Guide, do not merely report. The old text ("connect one and click Check now") pointed at
    // the wrong section for the commonest state -- a library with no backup yet -- where
    // checking has nothing to check and copying is the actual next step.
    const hasLibrary = (lib.photos || 0) + (lib.videos || 0) + (lib.audio || 0) > 0;
    list.innerHTML = `<div class="card"><div class="empty">${hasLibrary
      ? `<b>Your library isn’t backed up yet.</b><br>
         You have ${mediaCount(lib)} organized and no second copy of them.<br>
         Connect a drive, then use <b>Copy your library to another drive</b> below.`
      : `<b>No backups yet - and nothing to back up.</b><br>
         Organize some photos first, then come back here to copy them to a second drive.`}
      </div></div>`;
    return;
  }
  // Library summary (counts + formats only, catalog-driven - deliberately not a dashboard).
  const summary = `<div class="card"><div class="headline" style="font-size:var(--text-lg)">Your library</div>
    <div class="k mono">${mediaCount(lib)} · ${fmtBytes(lib.bytes)}</div>${byFormat(lib.by_format)}</div>`;
  const risk = at_risk.length ? `<div class="banner warn"><div>${plural(at_risk.length, "file")} exist in only one place.</div></div>` : "";
  const cards = drives.map((d) => {
    const pips = Math.min(drives.length, 3);  // ambient: how many places this library lives in
    const strip = [0, 1, 2].map((i) => (i < pips ? "▪" : "▫")).join(" ");
    return `<div class="card"><div class="tally" style="grid-template-columns:1fr auto">
      <div><b>${esc(d.label)}</b> ${driveReachBadge(d.reach)}<div class="k mono">${mediaCount(d)} · ${fmtBytes(d.size)}</div>
        ${d.path ? `<div class="k mono"><a href="#" data-open="${esc(d.path)}" title="Open in file manager">${esc(d.path)}</a></div>` : ""}</div>
      <div class="mono" style="color:var(--success)">${strip}</div></div>
      <div class="drive-foot">
        <span class="k mono">last checked: ${(d.last_verified || "never").slice(0, 10)}</span>
        ${d.path
          ? `<button class="btn btn-ghost drive-check" data-path="${esc(d.path)}">Check now</button>`
          : ""}
      </div></div>`;
  }).join("");
  list.innerHTML = summary + cards + risk;
  // A stated fact should carry its remedy: "last checked: never" is only useful next to the
  // thing that changes it. Rendered only when we know where the drive is -- offering an action
  // we cannot honour would be worse than stating the fact plainly.
  list.querySelectorAll(".drive-check").forEach((btn) => {
    btn.onclick = () => {
      const field = $("verify-path");
      field.value = btn.dataset.path;
      field.dispatchEvent(new Event("change"));
      field.scrollIntoView({ behavior: "smooth", block: "center" });
      $("verify-run").click();
    };
  });
}
let verifyJob = null;
$("verify-run").onclick = guarded(async () => {
  const path = $("verify-path").value.trim();
  $("verify-result").innerHTML = "";
  await runJob({
    button: $("verify-run"),
    busyLabel: "Checking…",
    start: () => api("/api/verify/run", { path }),
    setJob: (id) => { verifyJob = id; },
    progress: verifyProgress,
    progressLabel: "checking",
    onRefuse: (started) => {
      $("verify-result").innerHTML = startRefusedCard(started, "verify-path");
    },
    statusVerb: "Checking",
    onError: (d) => { $("verify-result").innerHTML = jobErrorCard(d); },
    onCancelled: () => {
      // Read-only: cancel changes nothing on disk, but ok:true must not paint "Checked".
      $("verify-result").innerHTML = card(
        `<div class="headline">Check cancelled</div><div class="k">Nothing was changed. Check again when you are ready.</div>`);
    },
    onSuccess: (d) => {
      const s = d.summary;
      const problems = (s.problems || []).map((p) => {
        const why = p.detail ? ` - ${esc(p.detail)}` : "";
        return `<div class="mono">${esc(p.status)} · ${esc(p.relative)}${why}</div>`;
      }).join("");
      const problemNote = problems
        ? `<div class="banner warn"><div><div class="b-title">${plural(s.problems.length, "file")} could not be confirmed</div>${problems}</div></div>`
        : "";
      $("verify-result").innerHTML =
        card(`<div class="headline">Checked ${esc(s.label || "")}</div>
           <div class="tally"><div class="n">${nfmt(s.verified)}</div><div class="k">verified</div>
           <div class="n">${nfmt(s.missing)}</div><div class="k">missing</div>
           <div class="n">${nfmt(s.mismatch)}</div><div class="k">changed</div>
           <div class="n">${nfmt(s.unreadable || 0)}</div><div class="k">unreadable</div>
           <div class="n">${nfmt(s.unverifiable || 0)}</div><div class="k">no recorded hash</div></div>
           ${problemNote}`);
      loadCustody();
      loadDrives();  // "last checked" on the card comes from the verify just recorded
    },
  });
});
$("verify-cancel").onclick = guarded(() => { if (verifyJob) return api(`/api/jobs/${verifyJob}/cancel`, {}); });

// A drive error that carries a correction offers it as a button: the common cause is naming a
// folder INSIDE a connected drive, and re-typing the root by hand is work the app can do.
function driveError(r, fieldId) {
  if (!r.suggested_root) return card(`<div class="banner warn"><div>${esc(r.error)}</div></div>`);
  return card(`<div class="banner warn"><div>${esc(r.error)}</div>
    <div class="actions"><button class="btn btn-secondary" data-use-root="${esc(r.suggested_root)}"
      data-field="${esc(fieldId)}">Use ${esc(r.drive_label || "the drive root")}</button></div></div>`);
}

document.addEventListener("click", (e) => {
  const btn = e.target.closest("[data-use-root]");
  if (!btn) return;
  $(btn.dataset.field).value = btn.dataset.useRoot;
  $(btn.dataset.field).dispatchEvent(new Event("change"));
});

document.addEventListener("click", guarded(async (e) => {
  const btn = e.target.closest("[data-clean-preview]");
  if (!btn) return;
  e.preventDefault();
  await startCleanupPreview(btn);
}));

// A displayed path is a dead end unless you can get to it. Anything carrying data-open reveals
// that folder in the desktop's own file manager; a failure says why, because a control that
// silently does nothing is worse than no control.
document.addEventListener("click", guarded(async (e) => {
  const el = e.target.closest("[data-open]");
  if (!el || !el.dataset.open) return;
  e.preventDefault();
  const r = await api("/api/reveal", { path: el.dataset.open });
  if (!r.ok) { el.title = r.error; el.classList.add("warn"); }
}));

// ---------- Find ----------
let wherePage = 1;

async function runWhere(term, page) {
  const r = await api(`/api/where?term=${encodeURIComponent(term)}&page=${page}`);
  wherePage = r.page;
  if (!r.total) {
    $("where-result").innerHTML = card(`<div class="empty">No files match “${esc(term)}”.</div>`);
    return;
  }
  const first = (r.page - 1) * r.page_size + 1;
  const last = first + r.copies.length - 1;
  // The count is stated, not implied: "showing 1-50 of 2,269" is the difference between a
  // page of results and a page that might be hiding the file you are looking for.
  const pager = r.pages > 1
    ? `<div class="row" style="justify-content:space-between;align-items:center">
         <span class="k">Showing ${nfmt(first)}-${nfmt(last)} of ${nfmt(r.total)}</span>
         <span class="row">
           <button class="btn btn-secondary" id="where-prev"${r.page <= 1 ? " disabled" : ""}>Previous</button>
           <span class="k">Page ${r.page} of ${r.pages}</span>
           <button class="btn btn-secondary" id="where-next"${r.page >= r.pages ? " disabled" : ""}>Next</button>
         </span>
       </div>`
    : `<div class="k">${plural(r.total, "match", "es")}</div>`;
  $("where-result").innerHTML = card(
    `<table class="table"><thead><tr><th>File</th><th>Drive</th><th>Location</th></tr></thead><tbody>${
      r.copies.map((c) => `<tr><td>${esc(c.name)}</td><td>${esc(c.drive || "-")}</td><td class="path">${esc(c.relative)}</td></tr>`).join("")
    }</tbody></table>${pager}`);
  const prev = $("where-prev"), next = $("where-next");
  if (prev) prev.onclick = guarded(() => runWhere(term, wherePage - 1));
  if (next) next.onclick = guarded(() => runWhere(term, wherePage + 1));
}

$("where-go").onclick = guarded(() => runWhere($("where-term").value.trim(), 1));

async function loadStats() {
  $("stats-result").innerHTML = card("<div class='k'>Loading library stats…</div>");
  const stats = await get("/api/library/stats");
  $("stats-result").innerHTML = renderStatsSummary(stats);
}

document.addEventListener("click", guarded(async (e) => {
  const btn = e.target.closest("[data-stats-action]");
  if (!btn) return;
  e.preventDefault();
  if (btn.dataset.statsAction === "backups") {
    showScreen("backups");
    await loadDrives();
    return;
  }
  if (btn.dataset.statsAction === "undated") {
    showScreen("find");
    $("where-term").value = "Undated";
    await runWhere("Undated", 1);
  }
}));

// ---------- Import (a folder of photos, or archives from any service) ----------
// One summary renderer for both entry paths (an extracted folder, and an unpacked archive set),
// extracted rather than copied so the two cannot drift in what they report.
function rcRenderSummary(d) {
  const r = d.summary;
  if (!r) { $("rc-result").innerHTML = archiveRefusalCard(d); return; }
  $("rc-result").innerHTML = card(
    `<div class="headline" data-testid="rc-summary">${nfmt(r.files)} files found</div>
     <div class="tally">
       <div class="n">${nfmt(r.kept)}</div><div class="k">to import</div>
       <div class="n">${nfmt(r.dup_collapsed)}</div><div class="k">duplicates removed (~${r.reclaimed_mb} MB)</div>
       <div class="n">${nfmt(r.dates_photo_taken)}</div><div class="k">dates recovered</div>
       <div class="n">${nfmt(r.undated)}</div><div class="k">still undated</div>
     </div>
     ${dateQualityNotes(r)}${inferredLocalShiftNotes(r)}
     ${matchListHtml(r.duplicate_matches, "Show what each duplicate matched")}
     ${matchListHtml(r.near_dup_matches, "Show what each look-alike resembles")}`
  );
}

let rcJob = null;

// Every refusal carries its CODE in data-refusal, and the tests key on that rather than on the
// sentence. Five refusals render similar-looking prose, so matching words lets a test pass
// because a DIFFERENT refusal fired - guard rule 8, applied to a user-facing surface.
function archiveRefusalCard(d) {
  const codes = (d.refusals || []).map((r) => `data-refusal="${esc(r)}"`).join(" ");
  return card(
    `<div class="headline" ${codes} data-testid="rc-refusal">Cannot unpack these archives</div>
     <div class="k" data-testid="rc-refusal-detail">${esc(d.detail)}</div>`);
}

// The claim is labelled in the copy, not just in the number: a header field is what the archive
// SAYS it will unpack to, and a user must not read it as something Truestill measured.
function archiveReadyCard(d) {
  return card(
    `<div class="headline" data-testid="rc-ready">${nfmt(d.media_entries)} photos and videos in ${nfmt(d.parts)} file(s)</div>
     <div class="k" data-testid="rc-claim">${esc(d.detail)}</div>
     <button class="btn" id="rc-confirm" data-testid="rc-confirm">Unpack and scan</button>`);
}

async function rcRunArchives(source, destination) {
  await runJob({
    button: $("rc-confirm"),
    busyLabel: "Unpacking…",
    start: () => api("/api/ingest/archives/run", { takeout: source, destination }),
    setJob: (id) => { rcJob = id; },
    progress: rcProgress,
    progressLabel: "unpacking",
    progressBeforeStart: true,
    statusForProgress: (p, setStatus) => {
      if (p.phase === "unpacking") setStatus(scaleStatus("Unpacking", p.done, p.total, "files"));
      else if (p.phase === "hashing") setStatus(scaleStatus("Checking for duplicates", p.done, p.total, "files"));
      else setStatus(scaleStatus("Scanning", p.done, p.total, "files"));
    },
    onError: (d) => { $("rc-result").innerHTML = jobErrorCard(d); },
    onCancelled: () => {
      $("rc-result").innerHTML = card(
        `<div class="headline" data-testid="rc-cancelled">Unpacking cancelled</div>
         <div class="k">Nothing was imported. What was unpacked so far is kept where it is, and
         starting again picks up from there or clears it.</div>`);
    },
    onSuccess: (d) => { rcRenderSummary(d); },
  });
}

$("rc-preview").onclick = guarded(async () => {
  const takeout = $("rc-takeout").value.trim(), destination = $("rc-dest").value.trim();
  $("rc-result").innerHTML = "";

  // Archives get preview-then-confirm: a cheap header read, then an explicit decision. An
  // already-extracted folder keeps the old single-step path, so nothing regresses for it.
  const pre = await api("/api/ingest/archives/precheck", { takeout, destination });
  if (pre && pre.parts > 0) {
    if (!pre.ok) { $("rc-result").innerHTML = archiveRefusalCard(pre); return; }
    $("rc-result").innerHTML = archiveReadyCard(pre);
    $("rc-confirm").onclick = guarded(() => rcRunArchives(takeout, destination));
    return;
  }

  await runJob({
    button: $("rc-preview"),
    busyLabel: "Scanning…",
    start: () => api("/api/ingest/preview", { takeout, destination }),
    setJob: (id) => { rcJob = id; },
    progress: rcProgress,
    progressLabel: "scanning",
    progressBeforeStart: true,
    onRefuse: (started) => {
      $("rc-result").innerHTML = startRefusedCard(started, "rc-dest");
    },
    statusForProgress: (p, setStatus) => {
      if (!p.total) setStatus("Scanning…");
      else if (p.phase === "scanning") setStatus(scaleStatus("Reading photos", p.done, p.total, "files"));
      else if (p.phase === "hashing") setStatus(scaleStatus("Checking for duplicates", p.done, p.total, "files"));
      else setStatus(scaleStatus("Scanning", p.done, p.total, "files"));
    },
    onError: (d) => { $("rc-result").innerHTML = jobErrorCard(d); },
    onCancelled: () => {
      $("rc-result").innerHTML = card(
        `<div class="headline">Preview cancelled</div><div class="k">Nothing was imported. Preview again when you are ready.</div>`);
    },
    onSuccess: (d) => { rcRenderSummary(d); },
  });
});
$("rc-cancel").onclick = guarded(() => { if (rcJob) return api(`/api/jobs/${rcJob}/cancel`, {}); });

// ---------- Trips & events ----------
// 13.3b's inversion: detect_trips runs first, so a genuine multi-day run already arrives as ONE
// card (kind "trip"); a standalone active day arrives as its own card (kind "event") exactly as
// before. Split is the primary adjustment (break a wrongly-joined run); merge is secondary (join
// a gap detection didn't bridge) and must obey §3e/§3f, which the server enforces and reports
// back as {error: "..."} - refused, never silently dropped.
let evSession = null;
let evCards = [];
function evCardKey(c) {
  // Stable across re-sorts (largest-first) so a Split/Merge can restore names on cards that
  // still exist. Index is not an identity - order_review_cards reshuffles after every edit.
  if (c.kind === "trip" && Array.isArray(c.days) && c.days.length) {
    return `t:${c.days.map((d) => d.date).join(",")}`;
  }
  return `e:${c.start}|${c.end}|${c.count}`;
}
function syncEvNamesFromDom() {
  for (const inp of $("ev-clusters").querySelectorAll(".ev-name")) {
    const i = +inp.dataset.i;
    if (evCards[i]) evCards[i].name = inp.value;
  }
}
function takeEvNamesByKey(cards) {
  const prior = new Map();
  for (const c of cards) {
    const name = (c.name || "").trim();
    if (name) prior.set(evCardKey(c), name);
  }
  return prior;
}
function restoreEvNames(cards, priorByKey) {
  const used = new Set();
  for (const c of cards) {
    const key = evCardKey(c);
    if (priorByKey.has(key) && !used.has(key)) {
      c.name = priorByKey.get(key);
      used.add(key);
    }
  }
  return [...priorByKey.entries()].filter(([key]) => !used.has(key)).map(([, name]) => name);
}
function showInvalidatedEvNames(names) {
  if (!names.length) return;
  $("ev-clusters").insertAdjacentHTML(
    "afterbegin",
    `<div class="banner warn"><div><div class="b-title">Names not kept</div>
     Split or merge changed these cards, so these typed names were cleared: ${names.map(esc).join(", ")}.
     Type them again where they still apply.</div></div>`
  );
}
async function applyEvCardEdit(endpoint, body) {
  // Capture names before the round-trip: renderCards replaces innerHTML and would otherwise
  // discard every typed value with nothing for the user to read (F39).
  syncEvNamesFromDom();
  const prior = takeEvNamesByKey(evCards);
  const r = await api(`/api/events/${evSession}/${endpoint}`, body);
  if (r.error) return r;
  const invalidated = restoreEvNames(r.cards, prior);
  renderCards(r.cards, r.collapsed);
  showInvalidatedEvNames(invalidated);
  return r;
}
function evCardHtml(c, i) {
  const isTrip = c.kind === "trip";
  const span = isTrip ? `${c.start} → ${c.end}` : `${c.start.slice(0, 10)} → ${c.end.slice(0, 10)}`;
  const days = isTrip
    ? `<details class="more"><summary>${plural(c.active_days, "active day")}</summary>
         <div class="mono k">${c.days.map((d) => `${d.date}: ${plural(d.count, "photo")}`).join("<br>")}</div></details>`
    : "";
  const splitAttrs = isTrip
    ? `data-kind="trip" data-days="${esc(c.days.map((d) => d.date).join(","))}"`
    : `data-kind="event" data-count="${c.count}"`;
  const nameValue = c.name ? ` value="${esc(c.name)}"` : "";
  return `<div class="card"><div class="tally" style="grid-template-columns:1fr auto">
        <div><b>${isTrip ? "TRIP" : "EVENT"} · ${nfmt(c.count)} photos</b><div class="k mono">${span}</div></div>
        <label class="k"><input type="checkbox" class="ev-check" data-i="${i}"> merge</label></div>
        ${days}
        <div class="row" style="margin-top:var(--space-2)"><input class="input ev-name" data-i="${i}"${nameValue} placeholder="name this ${isTrip ? "trip" : "event"} (leave blank to skip)">
        <button class="btn btn-secondary ev-split" data-i="${i}" ${splitAttrs}>Split</button></div></div>`;
}
function renderCards(cards, collapsed) {
  evCards = cards;
  const visible = cards.map((c, i) => [c, i]).filter(([c]) => !c.collapsed);
  const small = cards.map((c, i) => [c, i]).filter(([c]) => c.collapsed);
  const smallGroups = collapsed
    ? `<details class="card"><summary>${plural(collapsed.count, "smaller group")},
         ${nfmt(collapsed.min_photos)}-${nfmt(collapsed.max_photos)} photos ·
         ${esc(collapsed.start)} → ${esc(collapsed.end)} - show</summary>
         <div style="margin-top:var(--space-3)">${small.map(([c, i]) => evCardHtml(c, i)).join("")}</div></details>`
    : "";
  $("ev-actions-card").classList.toggle("hidden", cards.length === 0);
  $("ev-merge").classList.toggle("hidden", cards.length < 2);
  $("ev-clusters").innerHTML = cards.length
    ? visible.map(([c, i]) => evCardHtml(c, i)).join("") + smallGroups
    : `<div class="card"><div class="empty">No trips or events found - needs enough camera photos taken close together.</div></div>`;
  $("ev-clusters").querySelectorAll(".ev-name").forEach((inp) => {
    inp.addEventListener("input", () => {
      const i = +inp.dataset.i;
      if (evCards[i]) evCards[i].name = inp.value;
    });
  });
  $("ev-clusters").querySelectorAll(".ev-split").forEach((b) => {
    b.onclick = guarded(async () => {
      let body;
      if (b.dataset.kind === "trip") {
        const splittable = b.dataset.days.split(",").slice(0, -1);
        const after = prompt(`Split after which day? (${splittable.join(", ")})`);
        if (!after) return;
        body = { index: +b.dataset.i, after_day: after.trim() };
      } else {
        const at = parseInt(prompt(`Split after how many photos? (1..${b.dataset.count - 1})`), 10);
        if (!at) return;
        body = { index: +b.dataset.i, at };
      }
      await withBusy(b, "Splitting…", async () => {
        await applyEvCardEdit("split", body);
      });
    });
  });
}
function renderDeclines(declines) {
  $("ev-declines").innerHTML = (declines || [])
    .map(
      (msg) =>
        `<div class="banner warn"><div><div class="b-title">A run was not proposed as a trip</div>${esc(msg)}</div></div>`
    )
    .join("");
}
$("ev-propose").onclick = guarded(async () => {
  await withBusy($("ev-propose"), "Finding trips & events…", async () => {
    $("ev-result").innerHTML = "";
    $("ev-declines").innerHTML = "";
    $("ev-apply-card").classList.add("hidden");
    const r = await api("/api/events/propose", { path: $("ev-source").value.trim() });
    if (r.ok === false) {
      $("ev-clusters").innerHTML = driveError(r, "ev-source");
      $("ev-actions-card").classList.add("hidden");
      return;
    }
    evSession = r.session;
    renderDeclines(r.declines);
    renderCards(r.cards, r.collapsed);
  });
});
$("ev-merge").onclick = guarded(async () => {
  const indices = [...document.querySelectorAll(".ev-check:checked")].map((c) => +c.dataset.i);
  if (indices.length < 2) return;
  await withBusy($("ev-merge"), "Merging…", async () => {
    const r = await applyEvCardEdit("merge", { indices });
    if (r.error) {
      $("ev-clusters").insertAdjacentHTML(
        "afterbegin",
        `<div class="banner warn"><div><div class="b-title">Can't merge these</div>${esc(r.error)}</div></div>`
      );
    }
  });
});
// How many moves the preview lists before it starts summarising. A plan that rearranges someone's
// library must never look complete when it is not, so the hidden count is named in both places a
// reader can stop: the summary they decide whether to open, and the end of the list they scrolled.
const MOVE_PREVIEW_LIMIT = 200;

// A skipped duplicate must say WHAT it matched, not only that it matched something
// (IMPLEMENTATION_STANDARDS 9: counted AND named). The CLI has always printed this; the app
// used to render a bare count. Truncation follows the F46 shape - the count the list was taken
// from is named in the summary you decide whether to open, and again at the end you scrolled.
// "2,057 duplicates" answers nothing a person is asking. Whether their twin is ALREADY IN THE
// LIBRARY or merely earlier in the same batch leads to opposite next actions: the first says the
// source copies are redundant, the second says nothing about the library at all. The old clause
// here - "identical to a kept file" - was worse than silent, because for a library match there is
// no kept file in this batch to be identical to. Counts come from the payload, split over every
// match rather than over the capped sample; the wording is the engine's, not a second copy.
function dupOrigins(report) {
  if (!report) return "";
  const parts = [];
  if (report.already_in_library) parts.push(`${nfmt(report.already_in_library)} already in your library`);
  if (report.within_this_batch) parts.push(`${nfmt(report.within_this_batch)} earlier in this batch`);
  if (report.unclassified) parts.push(`${nfmt(report.unclassified)} matched elsewhere`);
  return parts.length ? `<br>${esc(parts.join(", "))}` : "";
}

function matchListHtml(report, label) {
  if (!report || !report.total) return "";
  const shown = report.shown || [];
  const hidden = report.total - shown.length;
  const heading = hidden
    ? `${label} (first ${nfmt(shown.length)} of ${nfmt(report.total)})`
    : `${label} (${nfmt(report.total)})`;
  const rows = shown
    .map((m) => `<div><span class="mono">${esc(m.name)}</span> - ${esc(m.detail)}</div>`)
    .join("");
  return `<details class="more"><summary>${heading}</summary>
            <div class="k">${rows}</div>
            ${hidden ? `<div class="k">…and ${nfmt(hidden)} more</div>` : ""}</details>`;
}

function moveListHtml(moves) {
  const shown = moves.slice(0, MOVE_PREVIEW_LIMIT);
  const hidden = moves.length - shown.length;
  const label = hidden
    ? `Show the moves (first ${nfmt(shown.length)} of ${nfmt(moves.length)})`
    : "Show the moves";
  const rows = shown.map((m) => `${esc(m.old)} → ${esc(m.new)}`).join("<br>");
  return `<details class="more"><summary>${label}</summary>
            <div class="mono k">${rows}</div>
            ${hidden ? `<div class="k">…and ${nfmt(hidden)} more</div>` : ""}</details>`;
}

$("ev-apply").onclick = guarded(async () => {
  await withBusy($("ev-apply"), "Saving names…", async ({ setStatus }) => {
    syncEvNamesFromDom();
    const names = evCards.map((card) => {
      const name = (card.name || "").trim();
      return name || null;
    });
    const r = await api(`/api/events/${evSession}/apply`, { names });
    if (!r.events && !r.trips) {
      $("ev-result").innerHTML = card(`<div class="k">Nothing named yet - type a name above, then Save names.</div>`);
      return;
    }
    const named = [r.trips ? plural(r.trips, "trip") : null, r.events ? plural(r.events, "event") : null]
      .filter(Boolean)
      .join(" and ");
    $("ev-result").innerHTML = card(
      `<div class="headline">${named} named.</div>
       <div class="k">Next: preview where these photos will move on the drive.</div>`);
    // Preview the on-disk placement (reuses the migrate engine). A named trip reaches this the
    // same way a named event always has (Stage 13.4) - both are previewed here, and nothing
    // moves until the button below is actually clicked. Preview is a real job: on a large trip
    // over a network mount it is minutes of rederive+plan (backlog oo), not a quick GET.
    $("ev-apply-card").classList.remove("hidden");
    $("ev-disk-result").innerHTML = "";
    $("ev-moves").innerHTML = "";
    $("ev-apply-disk").classList.add("hidden");
    setStatus("Planning moves…");
    await runJob({
      setStatus,
      start: () => api(`/api/events/${evSession}/preview`, {}),
      setJob: (id) => { evJob = id; },
      progress: evProgress,
      progressLabel: "planning",
      onRefuse: (started) => {
        $("ev-moves").innerHTML = startRefusedCard(started, "ev-source");
      },
      statusVerb: "Planning moves",
      unit: "photos",
      onError: (d) => { $("ev-moves").innerHTML = jobErrorCard(d); },
      onCancelled: () => {
        $("ev-moves").innerHTML = card(
          `<div class="headline">Preview cancelled</div><div class="k">Nothing was moved. Save names again when you are ready.</div>`);
      },
      onSuccess: (d) => {
        const p = d.summary;
        if (!p.ok) { $("ev-moves").innerHTML = `<div class="banner warn"><div>${esc(p.error)}</div></div>`; return; }
        $("ev-moves").innerHTML = p.moves.length
          ? `<div class="headline">${plural(p.moves.length, "photo")} will move into trip and event folders</div>
             ${moveListHtml(p.moves)}`
          : `<div class="k">Nothing to move - these photos are already in their trip and event folders.</div>`;
        $("ev-apply-disk").classList.toggle("hidden", p.moves.length === 0);
      },
    });
  });
});
// One row per trip or event actually named and moved this run, each with a working reveal link -
// folder exists by construction (the migration that just finished wrote it), so unlike Backups'
// drive-path links there is no disabled/absent state to consider here. Falls back to the plain
// count only when nothing in this session had a folder to show (e.g. everything was skipped).
function reviewResultCards(summary) {
  const groups = summary.groups || [];
  const cleanup = summary.leftover_empty_folders ? cleanupOfferNote(summary.leftover_empty_folders) : "";
  if (!groups.length) {
    return card(`<div class="headline">Moved ${plural(summary.migrated || 0, "photo")} into trip and event folders.</div>`) + cleanup;
  }
  return groups.map((g) => card(
    `<div class="headline">${esc(g.kind.toUpperCase())} · ${esc(g.name)}</div>
     <div class="k mono">${g.start.slice(0, 10)} → ${g.end.slice(0, 10)}</div>
     <div class="k mono"><a href="#" data-open="${esc(g.path)}" title="Open in file manager">${esc(g.path)}</a></div>`
  )).join("") + cleanup;
}
let evJob = null;
$("ev-apply-disk").onclick = guarded(async () => {
  await runJob({
    button: $("ev-apply-disk"),
    busyLabel: "Moving photos…",
    start: () => api(`/api/events/${evSession}/apply-to-disk`, {}),
    setJob: (id) => { evJob = id; },
    progress: evProgress,
    progressLabel: "moving",
    onRefuse: (started) => {
      $("ev-disk-result").innerHTML = startRefusedCard(started, "ev-source");
    },
    statusVerb: "Moving photos",
    unit: "photos",
    beforeOutcome: () => { $("ev-apply-disk").classList.add("hidden"); },
    onCancelled: (d) => {
      // Cancel leaves completed moves in place (resumable journal) - never claim a finished apply.
      const s = d.summary || {};
      cleanupOffer = s.leftover_empty_folders || null;
      $("ev-disk-result").innerHTML = card(
        `<div class="headline">Stopped</div>
         <div class="k">Moved ${plural(s.migrated || 0, "photo")} before you stopped it.</div>`)
        + (s.leftover_empty_folders ? cleanupOfferNote(s.leftover_empty_folders) : "");
      loadCustody();
      refreshUndoAffordance($("ev-source").value.trim(), $("ev-undo-panel"));
    },
    onError: (d) => {
      cleanupOffer = null;
      $("ev-disk-result").innerHTML = jobErrorCard(d);
      loadCustody();
      refreshUndoAffordance($("ev-source").value.trim(), $("ev-undo-panel"));
    },
    onSuccess: (d) => {
      cleanupOffer = d.summary.leftover_empty_folders || null;
      $("ev-disk-result").innerHTML = reviewResultCards(d.summary);
      loadCustody();
      // The apply just armed (or superseded) the reversible journal - re-query, never assume.
      refreshUndoAffordance($("ev-source").value.trim(), $("ev-undo-panel"));
    },
  });
});
$("ev-cancel").onclick = guarded(() => { if (evJob) return api(`/api/jobs/${evJob}/cancel`, {}); });

// ---------- Backups: copy the library to another drive ----------
$("bk-preview").onclick = guarded(async () => {
  const source = $("bk-source").value.trim(), target = $("bk-target").value.trim();
  await withBusy($("bk-preview"), "Checking what to copy…", async () => {
    const r = await api("/api/backup/preview", { source, target });
    if (!r.ok) { $("bk-result").innerHTML = driveError(r, "bk-target"); $("bk-run").classList.add("hidden"); return; }
    // Attaching a library that was organized before its folder was registered reads every one
    // of those files end to end, to record what that drive itself holds. On a big library that
    // is the longest part of the run, so it is said here rather than appearing as a progress
    // bar nobody was warned about. Usually zero: an already-attached drive reads nothing.
    const willRead = r.will_read
      ? `<div class="hint">First it will check ${plural(r.will_read, "file")} already on these drives, reading each one to record exactly what is there. That part can take a while; you can stop it at any time and it picks up where it left off.</div>`
      : "";
    if (r.count === 0) {
      $("bk-result").innerHTML = card(`<div class="headline">Already backed up.</div><div class="k">Every photo on ${esc(r.from)} is already on ${esc(r.to)}.</div>${willRead}`);
      $("bk-run").classList.toggle("hidden", !r.will_read); return;
    }
    if (!r.enough) {
      // A disk-full mid-copy is the failure this feature exists to prevent: warn and block.
      $("bk-result").innerHTML = card(`<div class="banner warn"><div><div class="b-title">Not enough space on ${esc(r.to)}</div>
        Needs ${fmtBytes(r.bytes)}, but the drive only has ${fmtBytes(r.free)} free.</div></div>`);
      $("bk-run").classList.add("hidden"); return;
    }
    $("bk-result").innerHTML = card(`<div class="headline">${mediaCount(r)} · ${fmtBytes(r.bytes)} to copy</div>
      <div class="k">From ${esc(r.from)} to ${esc(r.to)} · ${fmtBytes(r.free)} free on ${esc(r.to)}.</div>${willRead}`);
    $("bk-run").classList.remove("hidden");
  });
});
let bkJob = null;
$("bk-run").onclick = guarded(async () => {
  const source = $("bk-source").value.trim(), target = $("bk-target").value.trim();
  await runJob({
    button: $("bk-run"),
    busyLabel: "Copying…",
    start: () => api("/api/backup/run", { source, target }),
    setJob: (id) => { bkJob = id; },
    progress: bkProgress,
    progressLabel: "copying",
    onRefuse: (started) => {
      $("bk-result").innerHTML = startRefusedCard(started, "bk-target");
    },
    statusVerb: "Copying",
    beforeOutcome: () => { $("bk-run").classList.add("hidden"); },
    onCancelled: (d) => {
      // Cancel leaves completed copies on the target - same honesty as organizeCompletion.
      $("bk-result").innerHTML = backupCompletion({ ...d.summary, cancelled: true });
    },
    onError: (d) => { $("bk-result").innerHTML = jobErrorCard(d); },
    onSuccess: (d) => { $("bk-result").innerHTML = backupCompletion(d.summary); },
    after: () => { refreshDriveState(); },
  });
});
$("bk-cancel").onclick = guarded(() => { if (bkJob) return api(`/api/jobs/${bkJob}/cancel`, {}); });

// ---------- Settings ----------
function renderLayoutPreview(rows) {
  $("layout-preview").querySelector("tbody").innerHTML = rows.map((r) => `<tr>
    <td>${esc(r.description)}</td><td class="k">${esc(r.when)}</td>
    <td><code>${esc(r.path)}</code>${r.warnings.length ? `<div class="hint warn">${esc(r.warnings.join("; "))}</div>` : ""}</td>
  </tr>`).join("");
}
async function loadLayout() {
  const [s, eventConfig, dayConfig] = await Promise.all([
    get("/api/layout"),
    get("/api/events/settings"),
    get("/api/layout/everyday-day-threshold"),
  ]);
  $("layout-current").textContent = s.template;
  // Derived, never a hardcoded label.
  $("layout-default").textContent = s.is_default ? "(default)" : "";
  $("layout-template").value = s.template;
  const preset = $("layout-preset");
  preset.length = 1;
  for (const [name, tmpl] of Object.entries(s.presets)) {
    const o = document.createElement("option");
    const title = (s.preset_titles || {})[name] || name;
    o.value = tmpl;
    o.textContent = `${title}  -  ${tmpl}` + (name === s.default_preset ? "  (recommended)" : "");
    preset.appendChild(o);
  }
  renderLayoutPreview(s.preview);
  if (eventConfig.valid === false) {
    $("events-min-files").value = "";
    $("events-settings-status").textContent = eventConfig.error;
  } else {
    $("events-min-files").value = eventConfig.min_files;
    $("events-settings-status").textContent = eventConfig.is_default
      ? `Using the default (${eventConfig.default_min_files}).`
      : "Using your saved value.";
  }
  renderEverydayDayThreshold(dayConfig);
}
function renderEverydayDayThreshold(dayConfig) {
  const warn = $("everyday-day-threshold-warn");
  warn.innerHTML = "";
  if (dayConfig.valid === false) {
    $("everyday-day-threshold").value = "";
    $("everyday-day-threshold-status").textContent = dayConfig.error;
    return;
  }
  $("everyday-day-threshold").value = dayConfig.threshold;
  $("everyday-day-threshold-status").textContent = dayConfig.is_default
    ? `Using the default (${dayConfig.default_threshold}).`
    : "Using your saved value.";
  if (dayConfig.migrate_warning) {
    warn.innerHTML = `<div class="banner warn"><div>
      <div class="b-title">Existing files need a migrate</div>
      <div>${esc(dayConfig.migrate_warning)}</div>
      <div class="actions">
        <button class="btn btn-secondary" type="button" data-goto-migrate>Go to Move existing files</button>
      </div>
    </div></div>`;
    warn.querySelector("[data-goto-migrate]").onclick = guarded(() => {
      const target = $(dayConfig.migrate_anchor || "settings-migrate");
      if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
      $("mig-path")?.focus();
    });
  }
}
async function previewLayout() {
  const r = await api("/api/layout/preview", { template: $("layout-template").value.trim() });
  $("layout-error").textContent = r.valid ? "" : `That folder pattern is not valid. ${r.error} Update the pattern, then preview again.`;
  $("layout-save").disabled = !r.valid;
  if (r.valid) renderLayoutPreview(r.preview);
}
$("layout-template").oninput = guarded(previewLayout);
$("layout-preset").onchange = guarded(() => { if ($("layout-preset").value) { $("layout-template").value = $("layout-preset").value; return previewLayout(); } });
$("layout-save").onclick = guarded(async () => {
  const r = await api("/api/layout", { template: $("layout-template").value.trim() });
  if (r.valid === false) { $("layout-error").textContent = `That folder pattern is not valid. ${r.error} Update the pattern, then save again.`; return; }
  $("layout-current").textContent = r.template;
  $("layout-default").textContent = "";
  $("layout-error").textContent = "Saved.";
});
$("events-settings-save").onclick = guarded(async () => {
  const minFiles = Number($("events-min-files").value);
  const r = await api("/api/events/settings", { min_files: minFiles });
  if (r.valid === false) {
    $("events-settings-status").textContent = r.error;
    return;
  }
  $("events-min-files").value = r.min_files;
  $("events-settings-status").textContent = "Saved. New searches use this value.";
});
$("everyday-day-threshold-save").onclick = guarded(async () => {
  const threshold = Number($("everyday-day-threshold").value);
  const r = await api("/api/layout/everyday-day-threshold", { threshold });
  renderEverydayDayThreshold(r);
  if (r.valid === false) return;
  if (!r.migrate_warning) {
    $("everyday-day-threshold-status").textContent = "Saved.";
  }
});
let migJob = null;
function clearMigrateConfirm() {
  $("mig-confirm").innerHTML = "";
}
async function startMigrateRun() {
  const go = $("mig-confirm").querySelector("[data-typed-go]");
  await runJob({
    button: go,
    busyLabel: "Moving files…",
    start: () => api("/api/migrate/run", { path: $("mig-path").value.trim() }),
    setJob: (id) => { migJob = id; },
    progress: migProgress,
    progressLabel: "moving",
    onRefuse: (started) => {
      clearMigrateConfirm();
      $("mig-result").innerHTML = startRefusedCard(started, "mig-path");
    },
    statusVerb: "Moving files",
    beforeOutcome: () => { clearMigrateConfirm(); },
    onCancelled: (d) => {
      // Cancel leaves completed moves in place - do not paint a finished "Moved N files." card.
      const s = d.summary || {};
      cleanupOffer = s.leftover_empty_folders || null;
      $("mig-result").innerHTML = card(
        `<div class="headline">Stopped</div>
         <div class="k">Moved ${plural(s.migrated || 0, "file")} before you stopped it.</div>`)
        + (s.leftover_empty_folders ? cleanupOfferNote(s.leftover_empty_folders) : "");
    },
    onError: (d) => {
      cleanupOffer = null;
      $("mig-result").innerHTML = jobErrorCard(d);
    },
    onSuccess: (d) => {
      cleanupOffer = d.summary.leftover_empty_folders || null;
      $("mig-result").innerHTML = card(`<div class="headline">Moved ${plural(d.summary.migrated || 0, "file")}.</div>`)
        + (d.summary.leftover_empty_folders ? cleanupOfferNote(d.summary.leftover_empty_folders) : "");
    },
    after: () => {
      loadDrives();
      refreshUndoAffordance($("mig-path").value.trim(), $("mig-undo-panel"));
    },
  });
}
function renderMigrateTypedConfirm(moveCount) {
  const host = $("mig-confirm");
  host.innerHTML =
    `<div class="banner">
      <div>
        <div class="b-title">Before you move files</div>
        <div class="k">Type <code>move</code> to relocate ${plural(moveCount, "file")}.</div>
      </div>
    </div>
    <div data-mig-typed></div>`;
  typedConfirm(host.querySelector("[data-mig-typed]"), {
    word: "move",
    label: `Type move to relocate ${plural(moveCount, "file")}`,
    buttonLabel: `Move ${nfmt(moveCount)} files`,
    onConfirm: () => startMigrateRun(),
  });
}
$("mig-preview").onclick = guarded(async () => {
  $("mig-result").innerHTML = "";
  clearMigrateConfirm();
  await runJob({
    button: $("mig-preview"),
    busyLabel: "Planning moves…",
    start: () => api("/api/migrate/preview", { path: $("mig-path").value.trim() }),
    setJob: (id) => { migJob = id; },
    progress: migProgress,
    progressLabel: "planning",
    progressBeforeStart: true,
    onRefuse: (started) => {
      $("mig-result").innerHTML = startRefusedCard(started, "mig-path");
    },
    statusVerb: "Planning moves",
    onError: (d) => { $("mig-result").innerHTML = jobErrorCard(d); },
    onCancelled: () => {
      $("mig-result").innerHTML = card(
        `<div class="headline">Preview cancelled</div><div class="k">Nothing was moved. Preview again when you are ready.</div>`);
    },
    onSuccess: (d) => {
      const r = d.summary;
      if (!r.ok) { $("mig-result").innerHTML = driveError(r, "mig-path"); return; }
      const dayReasons = (r.day_folder_reasons || []).map((line) => `<div>${esc(line)}</div>`).join("");
      const dayBlock = dayReasons
        ? `<div class="banner" style="margin-top:var(--space-3)"><div>
             <div class="b-title">Everyday day-folder changes</div>${dayReasons}
           </div></div>`
        : "";
      // Reasons sit with the count so month↔day moves are explained before confirm (never bare).
      $("mig-result").innerHTML = card(`<div class="headline">${plural(r.moves.length, "file")} to move</div>
        <div class="k">${r.unchanged} already in place${r.warnings.length ? " · ⚠ " + esc(r.warnings.join("; ")) : ""}</div>
        ${dayBlock}`);
      if (r.moves.length) renderMigrateTypedConfirm(r.moves.length);
    },
  });
});
$("mig-cancel").onclick = guarded(() => { if (migJob) return api(`/api/jobs/${migJob}/cancel`, {}); });

// theme toggle
document.querySelectorAll('input[name="theme"]').forEach((r) => {
  r.onchange = () => {
    const v = r.value;
    if (v === "system") document.documentElement.removeAttribute("data-theme");
    else document.documentElement.setAttribute("data-theme", v);
  };
});

loadOrganizeMode();
loadSidebar();
loadCustody();
refreshOrganizeUndoAffordance();

// ---------- Dates you have corrected: preview -> typed confirm -> job (step 4) ----------
// Preview is catalog-only so it is a plain request; the run is a job because it writes to user
// files and must take the per-drive lock, stream progress and be cancellable.
function bakeDriveLines(elsewhere) {
  if (!elsewhere.length) return "";
  const rows = elsewhere
    .map((d) => `<div>${esc(d.label)} - ${plural(d.files, "file")}${d.connected ? " (connected now)" : " (not connected)"}</div>`)
    .join("");
  return `<div class="banner"><div><div class="b-title">These drives keep the old date inside their files</div>
            ${rows}
            <div class="k">Connect each one and set the dates again - Truestill does not do it on its own.</div></div></div>`;
}

let bakeJob = null;
$("bake-preview").onclick = guarded(async () => {
  const path = $("bake-path").value.trim();
  await withBusy($("bake-preview"), "Checking…", async () => {
    const r = await api("/api/dates/bake/preview", { path });
    $("bake-result").innerHTML = "";
    if (!r.ok) { $("bake-confirm").innerHTML = driveError(r, "bake-path"); return; }
    if (!r.will_write) {
      $("bake-confirm").innerHTML = card(
        `<div class="headline">Nothing to write on ${esc(r.drive_label)}</div>
         <div class="k">Every corrected date is already inside the files on this drive.</div>
         ${r.videos_skipped ? `<div class="k">${esc(r.videos_reason)}</div>` : ""}
         ${bakeDriveLines(r.elsewhere)}`);
      return;
    }
    $("bake-confirm").innerHTML = card(
      `<div class="headline">${plural(r.will_write, "file")} on ${esc(r.drive_label)} would be updated</div>
       ${r.videos_skipped ? `<div class="k">${plural(r.videos_skipped, "video")} left alone. ${esc(r.videos_reason)}</div>` : ""}
       ${r.absent ? `<div class="k">${plural(r.absent, "file")} the catalog expects here could not be found on this drive.</div>` : ""}
       ${bakeDriveLines(r.elsewhere)}
       <div class="banner warn"><div><div class="b-title">This cannot be undone</div>${esc(r.irreversible)}</div></div>
       <div data-typed-host></div>`);
    // The warning sits ABOVE the typed field on purpose: it is the thing to read before
    // typing, not an explanation offered after the decision has been made.
    typedConfirm($("bake-confirm").querySelector("[data-typed-host]"), {
      word: r.confirm_word,
      label: `Type ${r.confirm_word} to update ${plural(r.will_write, "file")}`,
      buttonLabel: "Set the dates",
      onConfirm: () => startBake(path),
    });
  });
});

async function startBake(path) {
  await runJob({
    button: $("bake-confirm").querySelector("[data-typed-go]"),
    busyLabel: "Setting dates…",
    start: () => api("/api/dates/bake/run", { path }),
    setJob: (id) => { bakeJob = id; },
    progress: bakeProgress,
    progressLabel: "updating",
    statusVerb: "Setting dates",
    beforeOutcome: () => { $("bake-confirm").innerHTML = ""; },
    onRefuse: (started) => { $("bake-confirm").innerHTML = startRefusedCard(started, "bake-path"); },
    onError: (d) => { $("bake-result").innerHTML = jobErrorCard(d); },
    onCancelled: (d) => { $("bake-result").innerHTML = bakeCompletion(d.summary, true); },
    onSuccess: (d) => { $("bake-result").innerHTML = bakeCompletion(d.summary, false); },
    after: () => { refreshDriveState(); },
  });
}
$("bake-cancel").onclick = guarded(() => { if (bakeJob) return api(`/api/jobs/${bakeJob}/cancel`, {}); });

function bakeCompletion(s, cancelled) {
  return card(
    `<div class="headline">${cancelled ? "Stopped" : "Dates updated"}</div>
     <div class="k">${esc(s.completeness || "")}</div>
     ${cancelled ? `<div class="k">The ${plural(s.baked || 0, "file")} already updated are finished and correct. The rest still have their old date and will be offered again.</div>` : ""}
     ${s.videos_skipped ? `<div class="k">${plural(s.videos_skipped, "video")} left alone. ${esc(s.videos_reason || "")}</div>` : ""}
     ${s.failed ? `<div class="banner warn"><div>${plural(s.failed, "file")} could not be updated and were left as they were.</div></div>` : ""}
     ${s.refused ? `<div class="banner warn"><div>${esc(s.refused)}</div></div>` : ""}
     ${bakeDriveLines(s.awaiting || [])}`);
}

// ---------- honesty view drill-down (step 5, part 1) ----------
// Read-only. Turns a tier's percentage into the files behind it, each carrying the sha256 the
// rescue action is keyed on. Truncation is disclosed the same way every other list does it.
document.addEventListener("click", guarded(async (event) => {
  const button = event.target.closest("[data-date-tier]");
  if (!button) return;
  const key = button.getAttribute("data-date-tier");
  const host = document.querySelector(`[data-date-tier-list="${CSS.escape(key)}"]`);
  if (!host) return;
  if (host.innerHTML) { host.innerHTML = ""; return; }
  await withBusy(button, "Loading…", async () => {
    const page = await get(`/api/dates/files${key ? `?source=${encodeURIComponent(key)}` : ""}`);
    const hidden = page.total - page.files.length;
    const rows = page.files
      .map((f) => `<div class="row" data-rescue-row="${esc(f.sha256)}">
                     <span class="mono">${esc(f.name)}</span>
                     <span class="k">${f.captured_at ? esc(f.captured_at.slice(0, 10)) : "no date"}</span>
                     ${f.evidence ? `<span class="k mono">${esc(f.evidence)}</span>` : ""}
                     ${candidateHtml(f)}
                     <input class="input" data-rescue-date placeholder="2011-03-04" size="11">
                     <input class="input" data-rescue-time placeholder="time (optional)" size="12">
                     <button class="btn btn-ghost" data-rescue-go>Set date</button>
                   </div>
                   <div class="k" data-rescue-said></div>`)
      .join("");
    host.innerHTML =
      `<div class="k">${rows}</div>` +
      (hidden > 0 ? `<div class="k">…and ${nfmt(hidden)} more</div>` : "");
  });
}));

// What a confirmation says back. Part 2 states the recorded fact; part 3 extends THIS function
// with the other two states (still filed under the old year on disk, file itself unchanged) so
// the wording keeps one home rather than gaining a second copy.
function confirmedCard(r) {
  // The three states come from the server so the wording has one home (same reason as
  // status_label and date_explain). Rendered as separate lines because they are separate
  // facts: what changed, what did not move, and what the file itself still says.
  const states = (r.states || []).map((s) => `<div>${esc(s)}</div>`).join("");
  const assumed = r.time_assumed
    ? `<div class="k">Time not given, so midday is assumed.</div>`
    : "";
  // Offers, not actions. Each of these writes to user files behind its own typed confirm, so
  // the card sends the user there rather than doing it for them.
  const steps = (r.next_steps || [])
    .map((s) => `<div><button class="btn btn-ghost" data-rescue-next="${esc(s.action)}">${esc(s.label)}</button>
                   <span class="k">${esc(s.detail)}</span></div>`)
    .join("");
  return `${states}${assumed}<div class="k">Neither of these has happened yet:</div>${steps}`;
}

// Both next steps just take the user to the surface that already gates them. Nothing is
// started here - a card that ran a write would defeat the point of saying it had not.
document.addEventListener("click", guarded((event) => {
  const button = event.target.closest("[data-rescue-next]");
  if (!button) return;
  showScreen("settings");
  const target = button.getAttribute("data-rescue-next") === "bake" ? "bake-path" : "mig-path";
  $(target).scrollIntoView({ block: "center" });
  $(target).focus();
}));

// An exiftool _original sidecar beside the user's source may hold a different date. Truestill
// never creates these files - its own writes use -overwrite_original - so one that exists came
// from the user's own exiftool use, which is why this suggests and never decides.
//
// Three states, rendered DISTINCTLY rather than in three wordings of one thing: an offer is a
// button, "nothing to suggest" is muted text, and "could not look" is a warning. A user
// scanning fifty rows must tell "no sidecar" from "Truestill could not reach the source"
// without reading either one.
function candidateHtml(f) {
  if (f.candidate === "offer") {
    const when = esc(f.candidate_date.slice(0, 10));
    return `<button class="btn btn-secondary" data-rescue-candidate="${when}"
              title="A backup file beside your original still has this date">Use ${when}</button>`;
  }
  if (f.candidate === "unreachable") {
    return `<span class="warn" title="The folder this was imported from is not reachable, so no backup file could be checked">could not check</span>`;
  }
  return `<span class="k">no backup date</span>`;
}

// ---------- the rescue action (step 5, part 2) ----------
// The date field takes a full date only. A partial date is refused by the server with an
// explanation rather than being completed here - completing it in the browser would put the
// guess back, one layer further from the person who has to trust it.
document.addEventListener("click", guarded(async (event) => {
  const go = event.target.closest("[data-rescue-go]");
  if (!go) return;
  const row = go.closest("[data-rescue-row]");
  const said = row.nextElementSibling;
  await withBusy(go, "Saving…", async () => {
    const r = await api("/api/dates/confirm", {
      sha256: row.getAttribute("data-rescue-row"),
      date: row.querySelector("[data-rescue-date]").value.trim(),
      time: row.querySelector("[data-rescue-time]").value.trim(),
    });
    said.innerHTML = r.ok ? confirmedCard(r) : `<span class="warn">${esc(r.error)}</span>`;
  });
}));

// Accepting a candidate only fills the field. The commit is the same typed action as any other
// rescue - one home for what a confirmation means, so a sidecar date is not a second way in.
document.addEventListener("click", guarded((event) => {
  const button = event.target.closest("[data-rescue-candidate]");
  if (!button) return;
  const row = button.closest("[data-rescue-row]");
  row.querySelector("[data-rescue-date]").value = button.getAttribute("data-rescue-candidate");
  row.querySelector("[data-rescue-date]").focus();
}));
