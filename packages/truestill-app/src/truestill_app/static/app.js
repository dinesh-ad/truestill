"use strict";
const TOKEN = window.TRUESTILL_TOKEN;
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const nfmt = (n) => Number(n).toLocaleString();
// "2 files", "1 file" -- never "file(s)". Counts are read aloud in a user's head, and the
// parenthesised plural is the sound of a form letter.
const plural = (n, word, suffix = "s") => `${nfmt(n)} ${word}${Number(n) === 1 ? "" : suffix}`;

async function api(path, body) {
  const opts = { headers: { "X-Truestill-Token": TOKEN } };
  if (body !== undefined) {
    opts.method = "POST";
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  return (await fetch(path, opts)).json();
}
const get = (path) => api(path);

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
  if (name === "settings") loadLayout();
}
document.querySelectorAll(".nav-item").forEach((item) => { item.onclick = () => showScreen(item.dataset.screen); });

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
    hint.querySelector(".pk-create").onclick = async () => {
      hint.textContent = "Creating…";
      const r = await api("/api/fs/create", { path });
      if (r.created) validatePath(input, hint, kind);
      else { hint.textContent = `Couldn’t create it: ${r.error || "unknown error"}`; hint.className = "hint warn"; }
    };
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

$("org-preview").onclick = async () => {
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
};

$("org-run").onclick = async () => {
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
};
$("org-cancel").onclick = () => { if (orgJob) api(`/api/jobs/${orgJob}/cancel`, {}); };

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
      <div><b>${esc(d.label)}</b><div class="k mono">${mediaCount(d)} · ${fmtBytes(d.size)}</div></div>
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
$("verify-run").onclick = async () => {
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
};
$("verify-cancel").onclick = () => { if (verifyJob) api(`/api/jobs/${verifyJob}/cancel`, {}); };

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
  if (prev) prev.onclick = () => runWhere(term, wherePage - 1);
  if (next) next.onclick = () => runWhere(term, wherePage + 1);
}

$("where-go").onclick = () => runWhere($("where-term").value.trim(), 1);

// ---------- Import (Takeout) ----------
$("rc-preview").onclick = async () => {
  const takeout = $("rc-takeout").value.trim(), destination = $("rc-dest").value.trim();
  $("rc-result").innerHTML = card("Scanning…");
  const r = await api("/api/ingest/preview", { takeout, destination });
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
};

// ---------- Trips & events ----------
let evSession = null;
function renderClusters(clusters) {
  $("ev-actions-card").classList.toggle("hidden", clusters.length === 0);
  $("ev-merge").classList.toggle("hidden", clusters.length < 2);
  $("ev-clusters").innerHTML = clusters.length
    ? clusters.map((c, i) => `<div class="card"><div class="tally" style="grid-template-columns:1fr auto">
        <div><b>${nfmt(c.count)} photos</b><div class="k mono">${c.start.slice(0, 10)} → ${c.end.slice(0, 10)}</div></div>
        <label class="k"><input type="checkbox" class="ev-check" data-i="${i}"> merge</label></div>
        <div class="row" style="margin-top:var(--space-2)"><input class="input ev-name" data-i="${i}" placeholder="name this trip (leave blank to skip)">
        <button class="btn btn-secondary ev-split" data-i="${i}" data-count="${c.count}">Split</button></div></div>`).join("")
    : `<div class="card"><div class="empty">No trips found - needs enough camera photos taken close together.</div></div>`;
  $("ev-clusters").querySelectorAll(".ev-split").forEach((b) => {
    b.onclick = async () => {
      const at = parseInt(prompt(`Split after how many photos? (1..${b.dataset.count - 1})`), 10);
      if (!at) return;
      renderClusters((await api(`/api/events/${evSession}/split`, { index: +b.dataset.i, at })).clusters);
    };
  });
}
$("ev-propose").onclick = async () => {
  $("ev-result").innerHTML = "";
  $("ev-apply-card").classList.add("hidden");
  const r = await api("/api/events/propose", { path: $("ev-source").value.trim() });
  if (r.ok === false) {
    $("ev-clusters").innerHTML = card(`<div class="banner warn"><div>${esc(r.error)}</div></div>`);
    $("ev-actions-card").classList.add("hidden");
    return;
  }
  evSession = r.session;
  renderClusters(r.clusters);
};
$("ev-merge").onclick = async () => {
  const indices = [...document.querySelectorAll(".ev-check:checked")].map((c) => +c.dataset.i);
  if (indices.length < 2) return;
  renderClusters((await api(`/api/events/${evSession}/merge`, { indices })).clusters);
};
$("ev-apply").onclick = async () => {
  const names = [...document.querySelectorAll("#ev-clusters .card")].map((row) => {
    const inp = row.querySelector(".ev-name");
    return inp && inp.value.trim() ? inp.value.trim() : null;
  });
  const r = await api(`/api/events/${evSession}/apply`, { names });
  if (!r.events) {
    $("ev-result").innerHTML = card(`<div class="k">No trips named yet - type a name above, then Save names.</div>`);
    return;
  }
  $("ev-result").innerHTML = card(
    `<div class="headline">${plural(r.events, "trip")} named.</div>
     <div class="k">Next: preview where these photos will move on the drive.</div>`);
  // Preview the on-disk placement (reuses the migrate engine).
  const p = await api(`/api/events/${evSession}/preview`, {});
  $("ev-apply-card").classList.remove("hidden");
  $("ev-disk-result").innerHTML = "";
  if (!p.ok) { $("ev-moves").innerHTML = `<div class="banner warn"><div>${esc(p.error)}</div></div>`; return; }
  $("ev-moves").innerHTML = p.moves.length
    ? `<div class="headline">${plural(p.moves.length, "photo")} will move into trip folders</div>
       <details class="more"><summary>Show the moves</summary>
         <div class="mono k">${p.moves.slice(0, 200).map((m) => `${esc(m.old)} → ${esc(m.new)}`).join("<br>")}</div></details>`
    : `<div class="k">Nothing to move - these photos are already in their trip folders.</div>`;
  $("ev-apply-disk").classList.toggle("hidden", p.moves.length === 0);
};
let evJob = null;
$("ev-apply-disk").onclick = async () => {
  const { job_id } = await api(`/api/events/${evSession}/apply-to-disk`, {});
  evJob = job_id;
  evProgress.start("moving");
  streamJob(job_id, (d) => evProgress.update(d),
    (d) => {
      evProgress.stop();
      $("ev-apply-disk").classList.add("hidden");
      $("ev-disk-result").innerHTML = d.ok
        ? card(`<div class="headline">Moved ${plural(d.summary.migrated || 0, "photo")} into trip folders.</div>`)
        : jobErrorCard(d);
      evJob = null;
      loadCustody();
    });
};
$("ev-cancel").onclick = () => { if (evJob) api(`/api/jobs/${evJob}/cancel`, {}); };

// ---------- Backups: copy the library to another drive ----------
$("bk-preview").onclick = async () => {
  const source = $("bk-source").value.trim(), target = $("bk-target").value.trim();
  const r = await api("/api/backup/preview", { source, target });
  if (!r.ok) { $("bk-result").innerHTML = card(`<div class="banner warn"><div>${esc(r.error)}</div></div>`); $("bk-run").classList.add("hidden"); return; }
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
};
let bkJob = null;
$("bk-run").onclick = async () => {
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
};
$("bk-cancel").onclick = () => { if (bkJob) api(`/api/jobs/${bkJob}/cancel`, {}); };

// ---------- Settings: layout + migrate ----------
function renderLayoutPreview(rows) {
  $("layout-preview").querySelector("tbody").innerHTML = rows.map((r) => `<tr>
    <td>${esc(r.description)}</td><td class="k">${esc(r.when)}</td>
    <td><code>${esc(r.path)}</code>${r.warnings.length ? `<div class="hint warn">${esc(r.warnings.join("; "))}</div>` : ""}</td>
  </tr>`).join("");
}
async function loadLayout() {
  const s = await get("/api/layout");
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
}
async function previewLayout() {
  const r = await api("/api/layout/preview", { template: $("layout-template").value.trim() });
  $("layout-error").textContent = r.valid ? "" : `Invalid: ${r.error}`;
  $("layout-save").disabled = !r.valid;
  if (r.valid) renderLayoutPreview(r.preview);
}
$("layout-template").oninput = previewLayout;
$("layout-preset").onchange = () => { if ($("layout-preset").value) { $("layout-template").value = $("layout-preset").value; previewLayout(); } };
$("layout-save").onclick = async () => {
  const r = await api("/api/layout", { template: $("layout-template").value.trim() });
  if (r.valid === false) { $("layout-error").textContent = `Invalid: ${r.error}`; return; }
  $("layout-current").textContent = r.template;
  $("layout-default").textContent = "";
  $("layout-error").textContent = "Saved.";
};
$("mig-preview").onclick = async () => {
  const r = await api("/api/migrate/preview", { path: $("mig-path").value.trim() });
  if (!r.ok) { $("mig-result").innerHTML = card(`<div class="banner warn"><div>${esc(r.error)}</div></div>`); $("mig-run").classList.add("hidden"); return; }
  $("mig-result").innerHTML = card(`<div class="headline">${plural(r.moves.length, "file")} to move</div>
    <div class="k">${r.unchanged} already in place${r.warnings.length ? " · ⚠ " + esc(r.warnings.join("; ")) : ""}</div>`);
  $("mig-run").classList.toggle("hidden", r.moves.length === 0);
};
let migJob = null;
$("mig-run").onclick = async () => {
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
    });
};
$("mig-cancel").onclick = () => { if (migJob) api(`/api/jobs/${migJob}/cancel`, {}); };

// theme toggle
document.querySelectorAll('input[name="theme"]').forEach((r) => {
  r.onchange = () => {
    const v = r.value;
    if (v === "system") document.documentElement.removeAttribute("data-theme");
    else document.documentElement.setAttribute("data-theme", v);
  };
});

loadCustody();
