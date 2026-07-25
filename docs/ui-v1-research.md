# vaeon UI v1 - recon, research & design (Phase 1)

Design gate for the local web UI (`packages/vaeon-app`). **No build in this phase.** Decision
already fixed: a plain **local web app** (Python server + browser UI on localhost), no
Tauri/Electron/Rust; a native shell may wrap it later. The engine is untouched - `vaeon-app`
calls `vaeon-core` as a library, exactly as `vaeon-cli` does, and `vaeon-cli` stays co-equal.

---

## Part A - Reconnaissance (code truth, file:line)

### A1. Interaction inventory (what the UI must expose)
| Interaction | Where | Shape today |
|---|---|---|
| **Event review name/skip** | `vaeon_cli/events_review.py::run_event_stage` (L92); prompt type `Prompt = Callable[[EventCandidate], str \| None]` (L22) | Already **injectable** - the prompt is a callback. `_stdin_prompt` (L83, `input()`/`isatty`) is the CLI's implementation. |
| **`--map-albums` auto-name** | `events_review.py::album_prompt` (L67) | A non-interactive `Prompt` that returns the majority album. |
| **Dry-run vs apply** | `organizer.execute(apply=...)`; CLI `_run_pipeline` | A *mode*, not a prompt - clean to model as a request flag. |
| **Verify** | `cli.py::_cmd_verify` (L213); `verify.verify_copies` (core) | Core is pure; the CLI prints a single end report. |

**Takeaway:** the one genuinely interactive stage (event review) already takes an injected
callback - good. But it lives in `vaeon-cli` (see A2).

### A2. Purity check - the required refactor
`run_event_stage` and its helper `camera_items` live in **`vaeon-cli/events_review.py`**, yet
every import they use is from **`vaeon-core`** (`catalog`, `events`, `hashing`, `models`,
`organizer`). The only CLI-specific things inside are `print(...)` calls and `_stdin_prompt`.

> **Refactor R1 (required):** move the *pure orchestration* (cluster → resolve names against
> the catalog → `apply_events`) into **`vaeon-core`** (e.g. `vaeon_core/event_review.py`), prompt
> injected, **no printing** - it returns structured proposals/results. `vaeon-cli` keeps its
> `_stdin_prompt`/`album_prompt`/printing; `vaeon-app` supplies a UI-driven prompt. This is what
> lets `vaeon-app` **never import `vaeon-cli`** (the architecture rule).

Everything else the UI needs is already pure and injectable: `plan`, `resolve`, `execute`,
`scan.compute_hashes`, `verify.verify_copies`, `cluster_camera`, the catalog, `drive.py`.

### A3. Long-task reality - no progress or cancellation exists
The three long operations run minutes-to-hours on a big library and have **no hooks**:
- `scan.compute_hashes` (`scan.py` L71) - `executor.map` (L93), no progress, no cancel.
- `verify.verify_copies` (`verify.py`) - `executor.map` (L69), no progress, no cancel.
- `organizer.execute` (L340) - `for resolution in resolutions` (L364), no progress, no cancel.

> **Refactor R2 (required):** add an optional `progress: Callable[[int done, int total], None]`
> and cooperative cancellation (`cancel: threading.Event | None`, checked between items) to those
> three. The CLI passes a simple progress printer; the UI streams progress over SSE and posts a
> cancel. Without R2 the UI cannot show progress or stop a run.

> **Refactor R3 (event API, for merge/split):** the CLI prompt is name-or-skip. The UI is *why*
> merge/split were deferred, so the core orchestrator must expose proposed clusters **as data**
> and accept a richer decision (name / skip / **merge** ids / **split** at index) rather than a
> `(cluster) -> str|None` callback. R1 and R3 are done together.

---

## Part B - Research (community truth)

### B1. Backend: Starlette (+ uvicorn), not FastAPI, not raw stdlib
FastAPI *is* a wrapper over Starlette + Pydantic; for a **single-user local app** we don't want
Pydantic on internal models (our standard forbids it) or FastAPI's OpenAPI/validation weight.
Raw `http.server` is synchronous and would force hand-rolled routing, SSE, static serving and
background-task handling - fragile. **Starlette** is the smallest well-tested ASGI that gives
routing + SSE + static files + background tasks; **uvicorn** serves it. Two deps, isolated to
`vaeon-app` (vaeon-core stays imagehash+pillow only).
Sources: [DEV: FastAPI is overkill](https://dev.to/leapcell/fastapi-is-overkill-starlette-and-pydantic-are-all-you-really-need-1inp),
[Slant FastAPI vs Starlette](https://www.slant.co/versus/34241/34868/~fastapi_vs_starlette).

### B2. Frontend: server-rendered HTML + htmx, no build toolchain
2026 local tools ship server-rendered HTML; **htmx** (~14 KB, single vendored JS file, **no
build step, no npm/bundler**) adds interactivity by extending HTML. A React/pnpm/Vite pipeline
is unjustified against the TCO rule for a handful of screens. htmx's **SSE extension** swaps
progress into the DOM as events arrive.
Sources: [htmx in 2026](https://dev.to/pockit_tools/htmx-in-2026-when-you-dont-need-react-and-when-you-absolutely-do-2mf4),
[HTMX vs React 2026](https://www.pkgpulse.com/blog/htmx-vs-react-2026).

### B3. Long-task pattern: SSE (the boring one)
Progress is one-way server→client, which is exactly **Server-Sent Events**' shape - simpler than
WebSockets (bidirectional, overkill) and cheaper than polling. Cancellation is a separate small
`POST`. htmx has first-class SSE support.

### B4. Security of a localhost app (a real surface even with no server of ours)
DNS rebinding and localhost CSRF are real: a malicious web page can make the browser hit
`127.0.0.1` and, via rebinding, bypass same-origin. Standard mitigations, all adopted:
1. **Bind `127.0.0.1` only** (never `0.0.0.0`).
2. **Per-session token** required on every request (minted at start, delivered in the URL on
   first open - the Jupyter model); not a cookie, so rebinding/CSRF can't ride it.
3. **Host/Origin header check** - reject requests whose `Host`/`Origin` isn't our localhost
   binding (defeats DNS rebinding).
Sources: [GitHub blog: localhost CORS & DNS rebinding](https://github.blog/security/application-security/localhost-dangers-cors-and-dns-rebinding/),
[Unit42 DNS rebinding](https://unit42.paloaltonetworks.com/dns-rebinding/).

### B5. Port + browser open
Follow Syncthing/qBittorrent: a **fixed default port with fallback to an ephemeral free port**
if taken; bind `127.0.0.1`; open the browser at the exact URL **including the token** via stdlib
`webbrowser.open`. No configuration needed for the common case.

---

## Part C - Design proposal (for approval)

### C1. v1 screens (markdown wireframes)

**Home / launch**
```
+------------------------------------------------------+
|  vaeon                                     [Drives ▸] |
|  Organize a folder   |  Rescue a Takeout export       |
|  [ pick source … ]   |  [ pick takeout dir … ]        |
|  Recent runs: …                                       |
+------------------------------------------------------+
```

**Organize** (source pick → dry-run preview → run + progress)
```
Source: /photos/dump        Destination: [ Drive A ▾ ]   [ Dry run ]
── Preview (dry run) ───────────────────────────────
 New unique   : 812      Near-dups (kept) : 14
 Exact dups   : 240      Undated          : 9
 Folders      : Camera(410) Screenshots(180) WhatsApp(96) Saved(126)
 [ Review 3 event clusters ▸ ]           [ Run for real ▶ ]
── Running ────────────────  hashing 4,102 / 5,180  [■■■■□] [Cancel]
```

**Event review** (name / skip / **merge** / **split** - the deferred features land here)
```
Proposed events (Camera only)
 ▸ Jun 14–16  · 47 photos · ~(15.30, 74.12)   name:[ Goa Trip     ] [skip]
 ▸ Jul 02     · 12 photos                      name:[            ] [skip]
   selection: [ ☑ Jun14–16 ☑ Jul02 ]  [ Merge selected ] [ Split … ]
                                                        [ Apply events ]
```

**Drives** (list · status · verify with progress)
```
LABEL      FILES   SIZE   LAST SEEN     LAST VERIFIED
Drive A    5,180   38 GB  2026-07-25    2026-07-20     [ Verify ▶ ]
Drive B    5,180   38 GB  2026-06-30    never          [ Verify ▶ ]
At risk: 12 files exist on only one drive.        [ Where is…? ]
── Verifying Drive A ──  1,204 / 5,180  [■■□□]  verified 1204  ✗0  [Cancel]
```

**Rescue report** (Takeout ingest outcome) - the "wow" numbers already produced by ingest:
dates recovered vs approximate, album copies collapsed + space reclaimed, still-undated,
missing sidecars.

### C2. Explicitly NOT in v1
Remote access · any auth beyond the localhost token · rclone-remote configuration UI (use the
CLI) · a settings/preferences editor · multi-user or accounts · scheduling/automation · editing
or previewing media · packaging/native shell · anything that writes outside the existing
`--apply` paths. The UI is a front-end over the *existing* engine, nothing new server-side.

### C3. API surface (vaeon-app server ⇄ browser)
Small, REST-ish + one SSE stream per job. All require the session token + Host check.
```
GET  /                         -> home (html)
POST /api/organize/preview     {source, destination} -> dry-run summary (json)
POST /api/organize/run         {source, destination, options} -> {job_id}
GET  /api/jobs/{id}/events     -> SSE: {done,total,phase} … terminal {status,summary}
POST /api/jobs/{id}/cancel     -> 202
GET  /api/events/{job}/proposals -> cluster proposals (json)
POST /api/events/{job}/decide  {name|skip|merge:[ids]|split:{id,index}} -> updated proposals
POST /api/ingest/preview | /run  (mirrors organize; adds tz/prefer/map-albums)
GET  /api/drives               -> list + at-risk count
POST /api/drives/init          {root,label}
GET  /api/where?term=          -> copies with drive+path+last_verified
POST /api/verify/run           {path} -> {job_id}   (progress via /api/jobs/{id}/events)
```
Server calls `vaeon-core` only. Long endpoints start a background job (Starlette background task
/ a thread) that drives the core op with the R2 `progress`/`cancel` hooks and publishes SSE.

### C4. Dependency additions (each justified, per the dependency policy) - all in `vaeon-app` only
| Dep | Justification vs stdlib |
|---|---|
| `starlette` | Minimal ASGI: routing + SSE + static + background tasks. `http.server` is sync and would require hand-rolling all of it. Not FastAPI (wraps Starlette+Pydantic; Pydantic is disallowed for internal models and unneeded for one user). |
| `uvicorn` | The ASGI server to run Starlette. No stdlib ASGI server exists. |
| htmx (vendored JS, **not** a Python/npm dep) | ~14 KB single file, no build step; the whole point is avoiding a bundler pipeline. Shipped as a static asset in the package. |

`vaeon-core` gains **no** new dependency. Its only changes are the R1/R2/R3 refactors (pure
Python, stdlib `threading` for cancellation).

---

## Part D - Required core refactors before/with the build (summary)
- **R1** move event-review orchestration `vaeon-cli` → `vaeon-core` (prompt injected, no I/O).
- **R2** add `progress` + `cancel` to `compute_hashes`, `verify_copies`, `execute`.
- **R3** evolve the event decision from `(cluster)->str|None` to data-in/decision-out to support
  merge/split.

These keep `vaeon-app` free of any `vaeon-cli` import and give the UI progress, cancellation and
merge/split. `vaeon-cli` is updated to the new core APIs and stays co-equal; `make check` green.
