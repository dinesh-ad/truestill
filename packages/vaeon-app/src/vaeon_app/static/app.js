"use strict";
const TOKEN = window.VAEON_TOKEN;
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const nfmt = (n) => Number(n).toLocaleString();

async function api(path, body) {
  const opts = { headers: { "X-Vaeon-Token": TOKEN } };
  if (body !== undefined) {
    opts.method = "POST";
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  return (await fetch(path, opts)).json();
}
const get = (path) => api(path);

function streamJob(jobId, onProgress, onDone) {
  const es = new EventSource(`/api/jobs/${jobId}/events?token=${encodeURIComponent(TOKEN)}`);
  es.onmessage = (e) => {
    const d = JSON.parse(e.data);
    if (d.type === "progress") { onProgress(d); return; }
    es.close();
    onDone(d);
  };
  es.onerror = () => es.close();
  return es;
}
function setBar(barId, countId, done, total) {
  const pct = total ? Math.round((done / total) * 100) : 0;
  $(barId).style.width = pct + "%";
  $(countId).textContent = `${nfmt(done)} / ${nfmt(total)}`;
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

// "24 photos · 6 videos" — split, honest about the mix, zeros omitted (photos shown if all zero)
function mediaCount(s) {
  const parts = [];
  if (s.photos) parts.push(`${nfmt(s.photos)} photo${s.photos === 1 ? "" : "s"}`);
  if (s.videos) parts.push(`${nfmt(s.videos)} video${s.videos === 1 ? "" : "s"}`);
  if (s.audio) parts.push(`${nfmt(s.audio)} audio`);
  return parts.length ? parts.join(" · ") : "0 photos";
}
// collapsible "By format ▾" — extension counts split by photos / videos / audio, monospace
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
async function loadCustody() {
  const s = await get("/api/library/status");
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
  if (pk.kind === "source") use.textContent = v.media > 0 ? `Use this folder · ${n} photos` : "Use this folder · no photos";
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
  const folderNames = Object.keys(s.folders || {});
  const folders = Object.entries(s.folders || {}).map(([k, v]) =>
    `<span class="chip" title="${esc(catTip(k))}">${esc(k)} <span class="num">${nfmt(v)}</span></span>`).join("");
  const legendNames = folderNames.filter((n) => CAT_INFO[n]);
  const legend = legendNames.length
    ? `<div class="k" style="font-size:var(--text-xs);margin-top:var(--space-2);line-height:1.6">${
        legendNames.map((n) => `<b>${esc(n)}</b> - ${esc(CAT_INFO[n])}`).join("<br>")}</div>` : "";
  const sk = s.skipped || {};
  const skDocs = Object.entries(sk.documents || {});
  const skUn = Object.entries(sk.unrecognized || {});
  const skTotal = skDocs.concat(skUn).reduce((a, [, n]) => a + n, 0);
  let details = "";
  if (skTotal) {
    const rows = (label, list) => list.length
      ? `<tr><td>${label}</td><td class="num">${list.map(([e, n]) => `${esc(e)} ×${n}`).join(", ")}</td></tr>` : "";
    details = `<details class="more"><summary>${skTotal} file(s) skipped (not photos or videos) ▾</summary>
      <table class="table"><tbody>${rows("documents", skDocs)}${rows("unrecognized", skUn)}</tbody></table></details>`;
  }
  const heic = s.heic_perceptual_skipped ? `<div class="banner warn"><div>${s.heic_perceptual_skipped} HEIC file(s) will be backed up, but near-duplicate detection is unavailable for them.</div></div>` : "";
  $("org-result").innerHTML = card(
    `<div class="headline">${mediaCount(s)} found</div>
     <div class="tally">
       <div class="n">${nfmt(s.new_unique)}</div><div class="k">new - will be organized</div>
       <div class="n">${nfmt(s.near_dup)}</div><div class="k">look-alikes - kept and flagged</div>
       <div class="n">${nfmt(s.exact_dup)}</div><div class="k">duplicates - already backed up, will skip</div>
       <div class="n">${nfmt(s.undated)}</div><div class="k">no date - will go to “Undated”</div>
     </div>
     ${folders ? `<h3>Into these folders <span style="font-weight:400;color:var(--text-muted)">- hover a chip for what it means</span></h3><div class="chips">${folders}</div>${legend}` : ""}
     ${byFormat(s.by_format)}${heic}${details}`
  );
  return kept;
}

$("org-preview").onclick = async () => {
  const source = $("org-source").value.trim();
  const destination = $("org-dest").value.trim();
  if (!source) { setWhy("Pick a folder to organize first."); return; }
  $("org-result").innerHTML = card("Checking…");
  const s = await api("/api/organize/preview", { source, destination });
  const kept = renderOrganizeResult(s);
  if (!s.files) { $("org-run").disabled = true; setWhy("Nothing to organize in this folder."); }
  else if (!destination) { $("org-run").disabled = true; setWhy("Pick the organized folder for the sorted copies."); }
  else { $("org-run").disabled = false; $("org-run").textContent = `Organize ${nfmt(kept)} files`; setWhy(""); }
};

let orgJob = null;
$("org-run").onclick = async () => {
  const source = $("org-source").value.trim();
  const destination = $("org-dest").value.trim();
  const skip_undated = $("org-skip-undated").checked;
  const { job_id } = await api("/api/organize/run", { source, destination, skip_undated });
  orgJob = job_id;
  $("org-progress-card").classList.remove("hidden");
  streamJob(job_id,
    (d) => setBar("org-bar", "org-count", d.done, d.total),
    (d) => {
      $("org-progress-card").classList.add("hidden");
      const o = (d.summary || d).outcomes || {};
      const line = Object.entries(o).map(([k, v]) => `${nfmt(v)} ${k.replace(/_/g, " ")}`).join(" · ");
      $("org-result").innerHTML = card(`<div class="headline">Done</div><div class="k">${esc(line) || "nothing to do"}</div>`);
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
    list.innerHTML = `<div class="card"><div class="empty">No backup drives yet. Connect one and click “Check now”.</div></div>`;
    return;
  }
  // Library summary (counts + formats only, catalog-driven — deliberately not a dashboard).
  const summary = `<div class="card"><div class="headline" style="font-size:var(--text-lg)">Your library</div>
    <div class="k mono">${mediaCount(lib)} · ${fmtBytes(lib.bytes)}</div>${byFormat(lib.by_format)}</div>`;
  const risk = at_risk.length ? `<div class="banner warn"><div>${at_risk.length} photo(s) exist in only one place.</div></div>` : "";
  const cards = drives.map((d) => {
    const pips = Math.min(drives.length, 3);  // ambient: how many places this library lives in
    const strip = [0, 1, 2].map((i) => (i < pips ? "▪" : "▫")).join(" ");
    return `<div class="card"><div class="tally" style="grid-template-columns:1fr auto">
      <div><b>${esc(d.label)}</b><div class="k mono">${mediaCount(d)} · ${fmtBytes(d.size)}</div></div>
      <div class="mono" style="color:var(--success)">${strip}</div></div>
      <div class="k mono" style="font-size:var(--text-xs)">last checked: ${(d.last_verified || "never").slice(0, 10)}</div></div>`;
  }).join("");
  list.innerHTML = summary + cards + risk;
}
$("verify-run").onclick = async () => {
  const path = $("verify-path").value.trim();
  $("verify-result").innerHTML = card("Checking…");
  const { job_id } = await api("/api/verify/run", { path });
  $("verify-progress").classList.remove("hidden");
  streamJob(job_id,
    (d) => setBar("verify-bar", "verify-count", d.done, d.total),
    (d) => {
      $("verify-progress").classList.add("hidden");
      const s = d.summary || d;
      $("verify-result").innerHTML = s.error
        ? card(`<div class="banner warn"><div>${esc(s.error)}</div></div>`)
        : card(`<div class="headline">Checked ${esc(s.label || "")}</div>
           <div class="tally"><div class="n">${nfmt(s.verified)}</div><div class="k">verified</div>
           <div class="n">${nfmt(s.missing)}</div><div class="k">missing</div>
           <div class="n">${nfmt(s.mismatch)}</div><div class="k">changed</div></div>`);
      loadCustody();
    });
};
$("verify-cancel").onclick = () => {};

// ---------- Find ----------
$("where-go").onclick = async () => {
  const term = $("where-term").value.trim();
  const { copies } = await api(`/api/where?term=${encodeURIComponent(term)}`);
  $("where-result").innerHTML = copies.length
    ? card(`<table class="table"><thead><tr><th>File</th><th>Drive</th><th>Location</th></tr></thead><tbody>${
        copies.map((c) => `<tr><td>${esc(c.name)}</td><td>${esc(c.drive || "-")}</td><td class="path">${esc(c.relative)}</td></tr>`).join("")}</tbody></table>`)
    : card(`<div class="empty">No files match “${esc(term)}”.</div>`);
};

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
     </div>`
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
    $("ev-result").innerHTML = card(`<div class="k">No trips named yet — type a name above, then Save names.</div>`);
    return;
  }
  $("ev-result").innerHTML = card(
    `<div class="headline">${nfmt(r.events)} trip(s) named.</div>
     <div class="k">Next: preview where these photos will move on the drive.</div>`);
  // Preview the on-disk placement (reuses the migrate engine).
  const p = await api(`/api/events/${evSession}/preview`, {});
  $("ev-apply-card").classList.remove("hidden");
  $("ev-disk-result").innerHTML = "";
  if (!p.ok) { $("ev-moves").innerHTML = `<div class="banner warn"><div>${esc(p.error)}</div></div>`; return; }
  $("ev-moves").innerHTML = p.moves.length
    ? `<div class="headline">${nfmt(p.moves.length)} photo(s) will move into trip folders</div>
       <details class="more"><summary>Show the moves</summary>
         <div class="mono k">${p.moves.slice(0, 200).map((m) => `${esc(m.old)} → ${esc(m.new)}`).join("<br>")}</div></details>`
    : `<div class="k">Nothing to move — these photos are already in their trip folders.</div>`;
  $("ev-apply-disk").classList.toggle("hidden", p.moves.length === 0);
};
let evJob = null;
$("ev-apply-disk").onclick = async () => {
  const { job_id } = await api(`/api/events/${evSession}/apply-to-disk`, {});
  evJob = job_id;
  $("ev-progress").classList.remove("hidden");
  streamJob(job_id, (d) => setBar("ev-bar", "ev-count", d.done, d.total),
    (d) => {
      $("ev-progress").classList.add("hidden");
      $("ev-apply-disk").classList.add("hidden");
      $("ev-disk-result").innerHTML = card(`<div class="headline">Moved ${nfmt((d.summary || d).migrated || 0)} photo(s) into trip folders.</div>`);
      evJob = null;
      loadCustody();
    });
};
$("ev-cancel").onclick = () => { if (evJob) api(`/api/jobs/${evJob}/cancel`, {}); };

// ---------- Settings: layout + migrate ----------
function renderLayoutPreview(rows) {
  $("layout-preview").querySelector("tbody").innerHTML = rows.map((r) => {
    const w = r.warnings && r.warnings.length ? ` <span style="color:var(--warning)">⚠ ${esc(r.warnings.join("; "))}</span>` : "";
    return `<tr><td>${esc(r.category)}</td><td class="mono">${esc(r.when)}</td><td class="path">${esc(r.path)}${w}</td></tr>`;
  }).join("");
}
async function loadLayout() {
  const s = await get("/api/layout");
  $("layout-current").textContent = s.template;
  $("layout-default").textContent = s.is_default ? "(default)" : "";
  $("layout-template").value = s.template;
  const preset = $("layout-preset");
  preset.length = 1;
  for (const [name, tmpl] of Object.entries(s.presets)) {
    const o = document.createElement("option");
    o.value = tmpl; o.textContent = `${name}  (${tmpl})`;
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
  $("mig-result").innerHTML = card(`<div class="headline">${r.moves.length} file(s) to move</div>
    <div class="k">${r.unchanged} already in place${r.warnings.length ? " · ⚠ " + esc(r.warnings.join("; ")) : ""}</div>`);
  $("mig-run").classList.toggle("hidden", r.moves.length === 0);
};
let migJob = null;
$("mig-run").onclick = async () => {
  const { job_id } = await api("/api/migrate/run", { path: $("mig-path").value.trim() });
  migJob = job_id;
  $("mig-progress").classList.remove("hidden");
  streamJob(job_id, (d) => setBar("mig-bar", "mig-count", d.done, d.total),
    (d) => { $("mig-progress").classList.add("hidden"); $("mig-result").innerHTML = card(`<div class="headline">Moved ${nfmt((d.summary || d).migrated || 0)} file(s).</div>`); migJob = null; loadDrives(); });
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
