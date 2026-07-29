"use strict";
const TOKEN = window.TRUESTILL_TOKEN;
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
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

// Known failures worth answering with a next step rather than an apology. Matched on an
// exception name from the server, never on message text, which would break the moment
// anyone reworded it.
const FRIENDLY_ERRORS = {
  NotABackupDriveError:
    "This folder isn’t a truestill backup yet - use <b>Copy your library to another drive</b> " +
    "below to create one.",
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
  if (s.photos) parts.push(`${nfmt(s.photos)} photo${s.photos === 1 ? "" : "s"}`);
  if (s.videos) parts.push(`${nfmt(s.videos)} video${s.videos === 1 ? "" : "s"}`);
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

function spanStory(r) {
  const from = yearOf(r.oldest), to = yearOf(r.newest);
  if (!from) return null;                       // undated batch: no range exists to tell
  return from === to ? `all from ${from}` : `spanning ${from} – ${to}`;
}

function organizeCompletion(r) {
  const moved = (r.moved_in_place || 0) + (r.moved_by_copy || 0);
  const verb = moved && !r.organized ? "moved" : "organized";
  const kinds = [
    r.photos ? `${nfmt(r.photos)} photo${r.photos === 1 ? "" : "s"}` : "",
    r.videos ? `${nfmt(r.videos)} video${r.videos === 1 ? "" : "s"}` : "",
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
  return completionCard({
    done: r.cancelled ? "Stopped" : "Done",
    headline: `${nfmt(r.organized || 0)} file${r.organized === 1 ? "" : "s"} ${verb}`
      + (r.cancelled ? " before you stopped it" : ""),
    sub: [kinds, span].filter(Boolean).join(" · "),
    stats: [
      { value: fmtBytes(r.bytes_organized), label: "now organized" },
      r.duplicates
        ? { value: fmtBytes(r.bytes_saved), label: `saved by skipping ${nfmt(r.duplicates)} duplicate${r.duplicates === 1 ? "" : "s"}` }
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
  const started = await api("/api/migrate/undo/preview", { path });
  if (started.ok === false) {
    panel.innerHTML = driveError(started, panel.id === "mig-undo-panel" ? "mig-path" : "ev-source");
    return;
  }
  undoJob = started.job_id;
  // Park the shared progress block inside this panel so it is visible on the active screen.
  let stage = panel.querySelector("[data-undo-stage]");
  if (!stage) {
    panel.innerHTML = undoArmedHtml(
      { file_count: 0 }, path
    ); // keep a stage host if the armed card was cleared mid-flight
    stage = panel.querySelector("[data-undo-stage]");
  }
  stage.innerHTML = "";
  stage.appendChild($("undo-card"));
  undoProgress.start("restoring");
  streamJob(started.job_id, (d) => undoProgress.update(d), (d) => {
    undoProgress.stop();
    undoJob = null;
    document.body.appendChild($("undo-card"));
    $("undo-card").classList.add("hidden");
    if (!d.ok) { stage.innerHTML = jobErrorCard(d); return; }
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
  });
}

async function startUndoApply(path, panel) {
  const started = await api("/api/migrate/undo/apply", { path });
  if (started.ok === false) {
    panel.innerHTML = driveError(started, panel.id === "mig-undo-panel" ? "mig-path" : "ev-source");
    return;
  }
  undoJob = started.job_id;
  let stage = panel.querySelector("[data-undo-stage]");
  if (!stage) {
    panel.innerHTML = `<div data-undo-stage></div>`;
    stage = panel.querySelector("[data-undo-stage]");
  }
  stage.innerHTML = "";
  stage.appendChild($("undo-card"));
  undoProgress.start("restoring");
  streamJob(started.job_id, (d) => undoProgress.update(d), async (d) => {
    undoProgress.stop();
    undoJob = null;
    document.body.appendChild($("undo-card"));
    $("undo-card").classList.add("hidden");
    const summaryHtml = d.ok
      ? card(
          `<div class="headline">Put ${plural(d.summary.reversed_files, "file")} back.</div>
           ${undoRefusalList(d.summary.refused)}`
        )
      : jobErrorCard(d);
    await refreshUndoAffordance(path, panel);
    // Prepend the outcome without re-parsing the armed card: assigning panel.innerHTML
    // would wipe the Preview onclick refreshUndoAffordance just attached, and a cancelled
    // apply that left rows would show a dead button (resume impossible from the UI).
    panel.insertAdjacentHTML("afterbegin", summaryHtml);
    loadCustody();
  });
}
$("undo-cancel").onclick = guarded(() => { if (undoJob) return api(`/api/jobs/${undoJob}/cancel`, {}); });

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
    headline: `${mediaCount(r)} copied to ${esc(r.to || "the drive")}`,
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
// showed "this folder isn't a truestill backup yet" about the drive now listed above it.
async function refreshDriveState() {
  $("verify-result").innerHTML = "";  // a verdict about the old state is not about this one
  await Promise.all([loadDrives(), loadCustody()]);
}

// ---------- navigation ----------
function showScreen(name) {
  document.querySelectorAll(".screen").forEach((s) => s.classList.toggle("active", s.id === `screen-${name}`));
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
}
document.querySelectorAll(".nav-item").forEach((item) => { item.onclick = () => showScreen(item.dataset.screen); });

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
  if (el && value && !el.value) el.value = value;
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
  const places = s.places || 0;
  const filled = Math.min(places, 3);
  pips.textContent = [0, 1, 2].map((i) => (i < filled ? "▪" : "▫")).join(" ");
  pips.classList.toggle("none", places === 0);
  const safe = !s.files ? "not backed up yet"
    : places === 0 ? "not on a backup drive yet"
    : `safe in ${places} place${places > 1 ? "s" : ""}`;
  // deliberate two lines (counts, then safety) so nothing orphans at the 232px sidebar width
  line.innerHTML = `<b>${s.files ? mediaCount(s) : "0 photos"}</b><br><span class="safe">${safe}</span>`;
}

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
  if (kind === "source") {
    if (!v.exists || !v.is_dir) { hint.textContent = "That folder doesn’t exist."; hint.className = "hint warn"; return v; }
    const n = v.media_capped ? `${v.media}+` : v.media;
    if (v.media > 0) { hint.textContent = `${n} photos and videos here`; hint.className = "hint ok"; }
    else { hint.textContent = "No photos or videos here ⚠"; hint.className = "hint warn"; }
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
      else { hint.textContent = `Couldn’t create it: ${r.error || "unknown error"}`; hint.className = "hint warn"; }
    });
  } else if (!v.is_dir) { hint.textContent = "That’s a file, not a folder."; hint.className = "hint warn"; }
  else if (!v.writable) { hint.textContent = "This folder isn’t writable ⚠"; hint.className = "hint warn"; }
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

function renderOrganizeResult(s) {
  if (!s.files) {
    $("org-result").innerHTML = card(
      `<div class="banner warn"><div><div class="b-title">Nothing to organize here</div>
       <div>No photos or videos in this folder - is it the right one?</div></div></div>`
    );
    return;
  }
  const kept = (s.new_unique || 0) + (s.near_dup || 0);
  const folders = chipsFor(s.folders);
  const legend = legendFor(s.folders);
  const sk = s.skipped || {};
  const skDocs = Object.entries(sk.documents || {});
  const skUn = Object.entries(sk.unrecognized || {});
  const skTotal = skDocs.concat(skUn).reduce((a, [, n]) => a + n, 0);
  let details = "";
  if (skTotal) {
    const rows = (label, list) => list.length
      ? `<tr><td>${label}</td><td class="num">${list.map(([e, n]) => `${esc(e)} ×${n}`).join(", ")}</td></tr>` : "";
    details = `<details class="more"><summary>${plural(skTotal, "file")} skipped (not photos or videos) ▾</summary>
      <table class="table"><tbody>${rows("documents", skDocs)}${rows("unrecognized", skUn)}</tbody></table></details>`;
  }
  const heic = s.heic_perceptual_skipped ? `<div class="banner warn"><div>${plural(s.heic_perceptual_skipped, "HEIC file")} will be backed up, but near-duplicate detection is unavailable for them.</div></div>` : "";
  const dateQuality = dateQualityNotes(s);
  $("org-result").innerHTML = card(
    `<div class="headline">${mediaCount(s)} found</div>
     ${s.elapsed_seconds ? `<div class="k">checked in ${fmtDuration(s.elapsed_seconds)}</div>` : ""}
     <div class="tally">
       <div class="n">${nfmt(s.new_unique)}</div><div class="k">new - will be organized</div>
       <div class="n">${nfmt(s.near_dup)}</div><div class="k">look-alikes - kept and flagged</div>
       <div class="n">${nfmt(s.exact_dup)}</div><div class="k">duplicates - identical to a kept file, will skip</div>
       <div class="n">${nfmt(s.undated)}</div><div class="k">no date - will go to “Undated”</div>
     </div>
     ${folders ? `<h3>Into these folders <span style="font-weight:400;color:var(--text-muted)">- hover a chip for what it means</span></h3><div class="chips">${folders}</div>${legend}` : ""}
     ${byFormat(s.by_format)}${dateQuality}${heic}${details}`
  );
  return kept;
}

// Shared by preview and run: both are cancellable jobs, and Cancel needs the current one.
let orgJob = null;

$("org-preview").onclick = guarded(async () => {
  const source = $("org-source").value.trim();
  const destination = $("org-dest").value.trim();
  if (!source) { setWhy("Pick a folder to organize first."); return; }
  // Previewing a large source is minutes of real work (metadata, then hashing), so it gets
  // the same progress display as a run rather than a card that says "Checking…" and freezes.
  $("org-result").innerHTML = "";
  orgProgress.start("starting");
  const { job_id } = await api("/api/organize/preview", { source, destination });
  orgJob = job_id;
  streamJob(job_id,
    (d) => orgProgress.update(d),
    (d) => {
      orgProgress.stop();
      orgJob = null;
      const s = d.summary;
      if (!d.ok) { $("org-result").innerHTML = jobErrorCard(d); return; }
      if (d.status === "cancelled") {
        // Never report a cancelled check as an empty folder: the run stopped, it did not
        // find nothing. Same failure the "Done / nothing to do" blocker was.
        $("org-result").innerHTML = card(
          `<div class="headline">Check cancelled</div><div class="k">Nothing was changed. Preview again when you are ready.</div>`);
        $("org-run").disabled = true;
        setWhy("Preview again to see what would happen.");
        return;
      }
      const kept = renderOrganizeResult(s);
      if (!s.files) { $("org-run").disabled = true; setWhy("Nothing to organize in this folder."); }
      else if (!destination) { $("org-run").disabled = true; setWhy("Pick the organized folder for the sorted copies."); }
      else { $("org-run").disabled = false; $("org-run").textContent = `Organize ${nfmt(kept)} files`; setWhy(""); }
    });
});

$("org-run").onclick = guarded(async () => {
  const source = $("org-source").value.trim();
  const destination = $("org-dest").value.trim();
  const skip_undated = $("org-skip-undated").checked;
  const { job_id } = await api("/api/organize/run", { source, destination, skip_undated });
  orgJob = job_id;
  orgProgress.start("preparing");
  streamJob(job_id,
    (d) => orgProgress.update(d),
    (d) => {
      orgProgress.stop();
      const r = d.summary;
      if (d.status === "cancelled") {
        // A cancelled run still organized everything it reached, and those files are real.
        // Show the same card, labelled honestly, rather than implying nothing happened.
        $("org-result").innerHTML = organizeCompletion({ ...r, cancelled: true });
      } else {
        $("org-result").innerHTML = r.organized || r.outcomes
          ? organizeCompletion(r)
          : card(`<div class="headline">Nothing to organize</div><div class="k">No new photos or videos were found here.</div>`);
      }
      orgJob = null;
      loadCustody();
    });
});
$("org-cancel").onclick = guarded(() => { if (orgJob) return api(`/api/jobs/${orgJob}/cancel`, {}); });

// ---------- Backups ----------
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
      <div><b>${esc(d.label)}</b><div class="k mono">${mediaCount(d)} · ${fmtBytes(d.size)}</div>
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
  $("verify-result").innerHTML = card("Checking…");
  const { job_id } = await api("/api/verify/run", { path });
  verifyJob = job_id;
  verifyProgress.start("checking");
  streamJob(job_id,
    (d) => verifyProgress.update(d),
    (d) => {
      verifyProgress.stop();
      verifyJob = null;
      if (!d.ok) { $("verify-result").innerHTML = jobErrorCard(d); return; }
      const s = d.summary;
      $("verify-result").innerHTML =
        card(`<div class="headline">Checked ${esc(s.label || "")}</div>
           <div class="tally"><div class="n">${nfmt(s.verified)}</div><div class="k">verified</div>
           <div class="n">${nfmt(s.missing)}</div><div class="k">missing</div>
           <div class="n">${nfmt(s.mismatch)}</div><div class="k">changed</div></div>`);
      loadCustody();
      loadDrives();  // "last checked" on the card comes from the verify just recorded
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

// ---------- Import (Takeout) ----------
let rcJob = null;
$("rc-preview").onclick = guarded(async () => {
  const takeout = $("rc-takeout").value.trim(), destination = $("rc-dest").value.trim();
  $("rc-result").innerHTML = "";
  rcProgress.start("scanning");
  const { job_id } = await api("/api/ingest/preview", { takeout, destination });
  rcJob = job_id;
  streamJob(job_id, (d) => rcProgress.update(d), (d) => {
    rcProgress.stop();
    rcJob = null;
    if (!d.ok) { $("rc-result").innerHTML = jobErrorCard(d); return; }
    if (d.status === "cancelled") {
      $("rc-result").innerHTML = card(
        `<div class="headline">Preview cancelled</div><div class="k">Nothing was imported. Preview again when you are ready.</div>`);
      return;
    }
    const r = d.summary;
    $("rc-result").innerHTML = card(
      `<div class="headline">${nfmt(r.files)} files found</div>
       <div class="tally">
         <div class="n">${nfmt(r.kept)}</div><div class="k">to import</div>
         <div class="n">${nfmt(r.dup_collapsed)}</div><div class="k">duplicates removed (~${r.reclaimed_mb} MB)</div>
         <div class="n">${nfmt(r.dates_photo_taken)}</div><div class="k">dates recovered</div>
         <div class="n">${nfmt(r.undated)}</div><div class="k">still undated</div>
       </div>
       ${dateQualityNotes(r)}`
    );
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
  return `<div class="card"><div class="tally" style="grid-template-columns:1fr auto">
        <div><b>${isTrip ? "TRIP" : "EVENT"} · ${nfmt(c.count)} photos</b><div class="k mono">${span}</div></div>
        <label class="k"><input type="checkbox" class="ev-check" data-i="${i}"> merge</label></div>
        ${days}
        <div class="row" style="margin-top:var(--space-2)"><input class="input ev-name" data-i="${i}" placeholder="name this ${isTrip ? "trip" : "event"} (leave blank to skip)">
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
      const r = await api(`/api/events/${evSession}/split`, body);
      renderCards(r.cards, r.collapsed);
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
$("ev-merge").onclick = guarded(async () => {
  const indices = [...document.querySelectorAll(".ev-check:checked")].map((c) => +c.dataset.i);
  if (indices.length < 2) return;
  const r = await api(`/api/events/${evSession}/merge`, { indices });
  if (r.error) {
    $("ev-clusters").insertAdjacentHTML(
      "afterbegin",
      `<div class="banner warn"><div><div class="b-title">Can't merge these</div>${esc(r.error)}</div></div>`
    );
    return;
  }
  renderCards(r.cards, r.collapsed);
});
$("ev-apply").onclick = guarded(async () => {
  const names = evCards.map((_card, i) => {
    const inp = document.querySelector(`.ev-name[data-i="${i}"]`);
    return inp && inp.value.trim() ? inp.value.trim() : null;
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
  const started = await api(`/api/events/${evSession}/preview`, {});
  if (started.ok === false) {
    $("ev-moves").innerHTML = driveError(started, "ev-source");
    return;
  }
  evJob = started.job_id;
  evProgress.start("planning");
  streamJob(started.job_id, (d) => evProgress.update(d), (d) => {
    evProgress.stop();
    evJob = null;
    if (!d.ok) { $("ev-moves").innerHTML = jobErrorCard(d); return; }
    if (d.status === "cancelled") {
      $("ev-moves").innerHTML = card(
        `<div class="headline">Preview cancelled</div><div class="k">Nothing was moved. Save names again when you are ready.</div>`);
      return;
    }
    const p = d.summary;
    if (!p.ok) { $("ev-moves").innerHTML = `<div class="banner warn"><div>${esc(p.error)}</div></div>`; return; }
    $("ev-moves").innerHTML = p.moves.length
      ? `<div class="headline">${plural(p.moves.length, "photo")} will move into trip and event folders</div>
         <details class="more"><summary>Show the moves</summary>
           <div class="mono k">${p.moves.slice(0, 200).map((m) => `${esc(m.old)} → ${esc(m.new)}`).join("<br>")}</div></details>`
      : `<div class="k">Nothing to move - these photos are already in their trip and event folders.</div>`;
    $("ev-apply-disk").classList.toggle("hidden", p.moves.length === 0);
  });
});
// One row per trip or event actually named and moved this run, each with a working reveal link -
// folder exists by construction (the migration that just finished wrote it), so unlike Backups'
// drive-path links there is no disabled/absent state to consider here. Falls back to the plain
// count only when nothing in this session had a folder to show (e.g. everything was skipped).
function reviewResultCards(summary) {
  const groups = summary.groups || [];
  if (!groups.length) {
    return card(`<div class="headline">Moved ${plural(summary.migrated || 0, "photo")} into trip and event folders.</div>`);
  }
  return groups.map((g) => card(
    `<div class="headline">${esc(g.kind.toUpperCase())} · ${esc(g.name)}</div>
     <div class="k mono">${g.start.slice(0, 10)} → ${g.end.slice(0, 10)}</div>
     <div class="k mono"><a href="#" data-open="${esc(g.path)}" title="Open in file manager">${esc(g.path)}</a></div>`
  )).join("");
}
let evJob = null;
$("ev-apply-disk").onclick = guarded(async () => {
  const { job_id } = await api(`/api/events/${evSession}/apply-to-disk`, {});
  evJob = job_id;
  evProgress.start("moving");
  streamJob(job_id, (d) => evProgress.update(d),
    (d) => {
      evProgress.stop();
      $("ev-apply-disk").classList.add("hidden");
      $("ev-disk-result").innerHTML = d.ok ? reviewResultCards(d.summary) : jobErrorCard(d);
      evJob = null;
      loadCustody();
      // The apply just armed (or superseded) the reversible journal - re-query, never assume.
      refreshUndoAffordance($("ev-source").value.trim(), $("ev-undo-panel"));
    });
});
$("ev-cancel").onclick = guarded(() => { if (evJob) return api(`/api/jobs/${evJob}/cancel`, {}); });

// ---------- Backups: copy the library to another drive ----------
$("bk-preview").onclick = guarded(async () => {
  const source = $("bk-source").value.trim(), target = $("bk-target").value.trim();
  const r = await api("/api/backup/preview", { source, target });
  if (!r.ok) { $("bk-result").innerHTML = driveError(r, "bk-target"); $("bk-run").classList.add("hidden"); return; }
  if (r.count === 0) {
    $("bk-result").innerHTML = card(`<div class="headline">Already backed up.</div><div class="k">Every photo on ${esc(r.from)} is already on ${esc(r.to)}.</div>`);
    $("bk-run").classList.add("hidden"); return;
  }
  if (!r.enough) {
    // A disk-full mid-copy is the failure this feature exists to prevent: warn and block.
    $("bk-result").innerHTML = card(`<div class="banner warn"><div><div class="b-title">Not enough space on ${esc(r.to)}</div>
      Needs ${fmtBytes(r.bytes)}, but the drive only has ${fmtBytes(r.free)} free.</div></div>`);
    $("bk-run").classList.add("hidden"); return;
  }
  $("bk-result").innerHTML = card(`<div class="headline">${mediaCount(r)} · ${fmtBytes(r.bytes)} to copy</div>
    <div class="k">From ${esc(r.from)} to ${esc(r.to)} · ${fmtBytes(r.free)} free on ${esc(r.to)}.</div>`);
  $("bk-run").classList.remove("hidden");
});
let bkJob = null;
$("bk-run").onclick = guarded(async () => {
  const source = $("bk-source").value.trim(), target = $("bk-target").value.trim();
  const { job_id } = await api("/api/backup/run", { source, target });
  bkJob = job_id;
  bkProgress.start("copying");
  streamJob(job_id, (d) => bkProgress.update(d),
    (d) => {
      bkProgress.stop();
      $("bk-run").classList.add("hidden");
      const s = d.summary;
      $("bk-result").innerHTML = d.ok ? backupCompletion(s) : jobErrorCard(d);
      bkJob = null;
      refreshDriveState();
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
  const [s, eventConfig] = await Promise.all([get("/api/layout"), get("/api/events/settings")]);
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
}
async function previewLayout() {
  const r = await api("/api/layout/preview", { template: $("layout-template").value.trim() });
  $("layout-error").textContent = r.valid ? "" : `Invalid: ${r.error}`;
  $("layout-save").disabled = !r.valid;
  if (r.valid) renderLayoutPreview(r.preview);
}
$("layout-template").oninput = guarded(previewLayout);
$("layout-preset").onchange = guarded(() => { if ($("layout-preset").value) { $("layout-template").value = $("layout-preset").value; return previewLayout(); } });
$("layout-save").onclick = guarded(async () => {
  const r = await api("/api/layout", { template: $("layout-template").value.trim() });
  if (r.valid === false) { $("layout-error").textContent = `Invalid: ${r.error}`; return; }
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
let migJob = null;
$("mig-preview").onclick = guarded(async () => {
  $("mig-result").innerHTML = "";
  $("mig-run").classList.add("hidden");
  migProgress.start("planning");
  const started = await api("/api/migrate/preview", { path: $("mig-path").value.trim() });
  if (started.ok === false) {
    migProgress.stop();
    $("mig-result").innerHTML = driveError(started, "mig-path");
    return;
  }
  migJob = started.job_id;
  streamJob(started.job_id, (d) => migProgress.update(d), (d) => {
    migProgress.stop();
    migJob = null;
    if (!d.ok) { $("mig-result").innerHTML = jobErrorCard(d); return; }
    if (d.status === "cancelled") {
      $("mig-result").innerHTML = card(
        `<div class="headline">Preview cancelled</div><div class="k">Nothing was moved. Preview again when you are ready.</div>`);
      return;
    }
    const r = d.summary;
    if (!r.ok) { $("mig-result").innerHTML = driveError(r, "mig-path"); return; }
    $("mig-result").innerHTML = card(`<div class="headline">${plural(r.moves.length, "file")} to move</div>
      <div class="k">${r.unchanged} already in place${r.warnings.length ? " · ⚠ " + esc(r.warnings.join("; ")) : ""}</div>`);
    $("mig-run").classList.toggle("hidden", r.moves.length === 0);
  });
});
$("mig-run").onclick = guarded(async () => {
  const { job_id } = await api("/api/migrate/run", { path: $("mig-path").value.trim() });
  migJob = job_id;
  migProgress.start("moving");
  streamJob(job_id, (d) => migProgress.update(d),
    (d) => {
      migProgress.stop();
      $("mig-result").innerHTML = d.ok
        ? card(`<div class="headline">Moved ${plural(d.summary.migrated || 0, "file")}.</div>`)
        : jobErrorCard(d);
      migJob = null;
      loadDrives();
      refreshUndoAffordance($("mig-path").value.trim(), $("mig-undo-panel"));
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

loadCustody();
