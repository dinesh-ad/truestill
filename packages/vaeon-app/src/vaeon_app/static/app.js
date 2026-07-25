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

loadDrives();
