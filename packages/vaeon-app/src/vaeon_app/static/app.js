"use strict";
const TOKEN = window.VAEON_TOKEN;
const $ = (id) => document.getElementById(id);

async function api(path, body) {
  const opts = { headers: { "X-Vaeon-Token": TOKEN } };
  if (body !== undefined) {
    opts.method = "POST";
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(path, opts);
  return res.json();
}

// Stream a job's SSE progress; onProgress({done,total}), onDone(terminalEvent).
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
  $(countId).textContent = `${done} / ${total}`;
}

// --- Organize ---
$("org-preview").onclick = async () => {
  const source = $("org-source").value.trim();
  const destination = $("org-dest").value.trim();
  $("org-summary").textContent = "previewing…";
  const s = await api("/api/organize/preview", { source, destination });
  $("org-summary").textContent = JSON.stringify(s, null, 2);
  $("org-run").disabled = false;
};

let orgJob = null;
$("org-run").onclick = async () => {
  const source = $("org-source").value.trim();
  const destination = $("org-dest").value.trim();
  const { job_id } = await api("/api/organize/run", { source, destination });
  orgJob = job_id;
  $("org-progress").classList.remove("hidden");
  streamJob(job_id,
    (d) => setBar("org-bar", "org-count", d.done, d.total),
    (d) => { $("org-summary").textContent = JSON.stringify(d, null, 2); orgJob = null; });
};
$("org-cancel").onclick = () => { if (orgJob) api(`/api/jobs/${orgJob}/cancel`, {}); };

// --- Drives ---
async function loadDrives() {
  const { drives, at_risk } = await api("/api/drives");
  $("at-risk").textContent = at_risk.length
    ? `At risk: ${at_risk.length} file(s) exist on only one drive.` : "";
  const tbody = $("drives-table").querySelector("tbody");
  tbody.innerHTML = "";
  for (const d of drives) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${d.label}</td><td>${d.files}</td>` +
      `<td>${(d.size / 1e6).toFixed(1)} MB</td><td>${(d.last_seen || "-").slice(0, 19)}</td>` +
      `<td>${(d.last_verified || "never").slice(0, 19)}</td>` +
      `<td><button data-label="${d.label}">Where?</button></td>`;
    tbody.appendChild(tr);
  }
}
$("drives-refresh").onclick = loadDrives;

let verifyJob = null;
$("verify-run").onclick = async () => {
  const path = $("verify-path").value.trim();
  $("verify-out").textContent = "verifying…";
  const { job_id } = await api("/api/verify/run", { path });
  verifyJob = job_id;
  $("verify-progress").classList.remove("hidden");
  streamJob(job_id,
    (d) => setBar("verify-bar", "verify-count", d.done, d.total),
    (d) => { $("verify-out").textContent = JSON.stringify(d.summary || d, null, 2); verifyJob = null; loadDrives(); });
};
$("verify-cancel").onclick = () => { if (verifyJob) api(`/api/jobs/${verifyJob}/cancel`, {}); };

// --- Where ---
$("where-go").onclick = async () => {
  const term = $("where-term").value.trim();
  const { copies } = await api(`/api/where?term=${encodeURIComponent(term)}`);
  $("where-out").textContent = copies.length
    ? copies.map((c) => `${c.name}\n  drive '${c.drive}' -> ${c.relative}`).join("\n")
    : `no copies match '${term}'`;
};

// --- Event review (name / skip / merge / split) ---
let evSession = null;

function renderClusters(clusters) {
  const box = $("ev-clusters");
  box.innerHTML = "";
  clusters.forEach((c, i) => {
    const loc = c.location ? ` ~(${c.location[0].toFixed(2)}, ${c.location[1].toFixed(2)})` : "";
    const row = document.createElement("div");
    row.className = "cluster";
    row.innerHTML =
      `<input type="checkbox" class="ev-check" data-i="${i}"> ` +
      `<b>#${i}</b> ${c.count} files · ${c.start.slice(0, 16)} → ${c.end.slice(0, 16)}${loc} ` +
      `<input class="ev-name" data-i="${i}" placeholder="name (blank = skip)"> ` +
      `<button class="ev-split" data-i="${i}" data-count="${c.count}">split</button>`;
    box.appendChild(row);
  });
  $("ev-merge").classList.toggle("hidden", clusters.length < 2);
  $("ev-apply").classList.remove("hidden");
  document.querySelectorAll(".ev-split").forEach((b) => {
    b.onclick = async () => {
      const at = parseInt(prompt(`Split #${b.dataset.i} after how many photos? (1..${b.dataset.count - 1})`), 10);
      if (!at) return;
      renderClusters((await api(`/api/events/${evSession}/split`, { index: +b.dataset.i, at })).clusters);
    };
  });
}

$("ev-propose").onclick = async () => {
  const r = await api("/api/events/propose", { source: $("ev-source").value.trim() });
  evSession = r.session;
  renderClusters(r.clusters);
  $("ev-out").textContent = r.clusters.length ? "" : "no event clusters proposed";
};

$("ev-merge").onclick = async () => {
  const indices = [...document.querySelectorAll(".ev-check:checked")].map((c) => +c.dataset.i);
  if (indices.length < 2) { $("ev-out").textContent = "check at least two clusters to merge"; return; }
  renderClusters((await api(`/api/events/${evSession}/merge`, { indices })).clusters);
};

$("ev-apply").onclick = async () => {
  const names = [...document.querySelectorAll("#ev-clusters .cluster")].map((row) => {
    const v = row.querySelector(".ev-name").value.trim();
    return v || null;
  });
  const r = await api(`/api/events/${evSession}/apply`, { names });
  $("ev-out").textContent =
    `Named ${r.events} file(s) into events.\n` +
    r.placements.map((p) => `  ${p.name} -> ${p.relative}`).join("\n");
};

// --- Rescue report ---
$("rc-preview").onclick = async () => {
  $("rc-report").textContent = "scanning…";
  const r = await api("/api/ingest/preview", {
    takeout: $("rc-takeout").value.trim(), destination: $("rc-dest").value.trim(),
  });
  $("rc-report").innerHTML =
    `<b>Takeout rescue (preview)</b><br>` +
    `media files: ${r.files} &nbsp; kept: ${r.kept}<br>` +
    `album duplicate copies collapsed: ${r.dup_collapsed} (~${r.reclaimed_mb} MB)<br>` +
    `dates recovered (photoTakenTime): ${r.dates_photo_taken}<br>` +
    `dates approximate (upload time): ${r.dates_upload_approx}<br>` +
    `dates from EXIF: ${r.dates_exif} &nbsp; still undated: ${r.undated}<br>` +
    `media without a JSON sidecar: ${r.missing_sidecar}`;
};

// --- Settings: folder layout + migration ---
function renderLayoutPreview(rows) {
  const tbody = $("layout-preview").querySelector("tbody");
  tbody.innerHTML = "";
  for (const r of rows) {
    const tr = document.createElement("tr");
    const warn = r.warnings && r.warnings.length ? ` ⚠ ${r.warnings.join("; ")}` : "";
    tr.innerHTML = `<td>${r.category}</td><td>${r.when}</td><td><code>${r.path}</code>${warn}</td>`;
    tbody.appendChild(tr);
  }
}

async function loadLayout() {
  const s = await api("/api/layout");
  $("layout-current").textContent = s.template;
  $("layout-default").textContent = s.is_default ? "(default)" : "";
  $("layout-template").value = s.template;
  const preset = $("layout-preset");
  preset.length = 1;
  for (const [name, tmpl] of Object.entries(s.presets)) {
    const opt = document.createElement("option");
    opt.value = tmpl;
    opt.textContent = `${name}  (${tmpl})`;
    preset.appendChild(opt);
  }
  renderLayoutPreview(s.preview);
}

async function previewLayout() {
  const template = $("layout-template").value.trim();
  const r = await api("/api/layout/preview", { template });
  $("layout-error").textContent = r.valid ? "" : `Invalid: ${r.error}`;
  $("layout-save").disabled = !r.valid;
  if (r.valid) renderLayoutPreview(r.preview);
}

$("layout-template").oninput = previewLayout;
$("layout-preset").onchange = () => {
  if ($("layout-preset").value) { $("layout-template").value = $("layout-preset").value; previewLayout(); }
};
$("layout-save").onclick = async () => {
  const r = await api("/api/layout", { template: $("layout-template").value.trim() });
  if (r.valid === false) { $("layout-error").textContent = `Invalid: ${r.error}`; return; }
  $("layout-current").textContent = r.template;
  $("layout-default").textContent = "";
  $("layout-error").textContent = "Saved.";
};

$("mig-preview").onclick = async () => {
  const path = $("mig-path").value.trim();
  $("mig-out").textContent = "planning…";
  const r = await api("/api/migrate/preview", { path });
  if (!r.ok) { $("mig-out").textContent = r.error; $("mig-run").classList.add("hidden"); return; }
  const lines = [
    `Drive '${r.label}' -> template ${r.template}`,
    `${r.moves.length} file(s) to relocate, ${r.unchanged} already in place.`,
    ...r.moves.slice(0, 20).map((m) => `  ${m.old}  ->  ${m.new}`),
    ...(r.moves.length > 20 ? [`  ... and ${r.moves.length - 20} more`] : []),
    ...r.warnings.map((w) => `  ! ${w}`),
    ...r.pending_drives.map((d) => `  pending: '${d}' has copies too -- reconnect and re-run`),
  ];
  $("mig-out").textContent = lines.join("\n");
  $("mig-run").classList.toggle("hidden", r.moves.length === 0);
};

let migJob = null;
$("mig-run").onclick = async () => {
  const { job_id } = await api("/api/migrate/run", { path: $("mig-path").value.trim() });
  migJob = job_id;
  $("mig-progress").classList.remove("hidden");
  streamJob(job_id,
    (d) => setBar("mig-bar", "mig-count", d.done, d.total),
    (d) => { $("mig-out").textContent = JSON.stringify(d.summary || d, null, 2); migJob = null; loadDrives(); });
};
$("mig-cancel").onclick = () => { if (migJob) api(`/api/jobs/${migJob}/cancel`, {}); };

loadLayout();
loadDrives();
