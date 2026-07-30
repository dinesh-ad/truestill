# Job-run skeleton inventory (audit F38, commit 1)

Hand inventory of the thirteen `awaitJob` call sites in
`packages/truestill-app/src/truestill_app/static/app.js`. **No extraction yet** - this
record exists so commit 2 cannot silently impose one copy's behaviour on the other twelve.

Line numbers are from `main` at the time of this note (`1f81ca8` era). They will drift;
identity is by function / click handler name.

---

## The thirteen sites

| # | Site | Approx. line |
|---|---|---|
| 1 | `startUndoPreview` (migrate undo) | 593 |
| 2 | `startUndoApply` (migrate undo) | 636 |
| 3 | `startOrganizeUndoPreview` | 1158 |
| 4 | `startOrganizeUndoApply` | 1195 |
| 5 | `#org-dedup` click (organize preview job) | 1319 |
| 6 | `startOrganizeRun` | 1365 |
| 7 | `#verify-run` click | 1474 |
| 8 | `#rc-preview` click (Takeout ingest preview) | 1606 |
| 9 | `#ev-apply` nested trip-preview job | 1832 |
| 10 | `#ev-apply-disk` click | 1878 |
| 11 | `#bk-run` click | 1925 |
| 12 | `startMigrateRun` | 2052 |
| 13 | `#mig-preview` click | 2096 |

Not in the thirteen (use `withBusy` but **not** `awaitJob`): organize inventory, clean-empty
preview/apply, backup preview, events propose/merge/split, sync settings saves. Those are
request/response, not the job skeleton.

---

## What all thirteen have in common

1. Wrapped in `withBusy(button, label, async (…) => { … })`.
2. `POST` via `api(...)` that returns a start payload with `job_id` on success.
3. Assign the id to a module-level `*Job` handle (cancel wiring).
4. Drive a `createProgress(...)` instance: `start` → `awaitJob` + `update` → `stop`.
5. Clear the `*Job` handle after the terminal event.
6. Render into a result/stage node from the normalized `{ ok, status, error, summary }` shape
   that `streamJob` / `awaitJob` already produce.

That is the extractable core. Everything else is a parameter or a post-hook.

---

## Every difference (site → what → deliberate or drift)

### A. Soft-refuse before treating the response as a job

| Sites | Behaviour |
|---|---|
| 1, 2, 5–13 | `if (started.ok === false) { startRefusedCard(...); return; }` (5, 8, 13 also `progress.stop()` first) |
| 3, 4 | Only special-case `started.ok === true && started.armed === false` (spent journal); **no** `started.ok === false` branch |

**Verdict: drift → latent bug on 3 and 4.** A `DriveBusy` / drive-unavailable soft-fail
(`ok: false`) falls through, assigns `orgUndoJob = started.job_id` (undefined), and enters
`awaitJob` on a nonsense id. Migrate-undo twins (1, 2) already refuse correctly. Fix in its
own commit before extraction, with a regression test.

### B. When `progress.start` runs

| Sites | Behaviour |
|---|---|
| 5, 8, 13 | `progress.start` **before** the start `POST`; stop again if refuse |
| 1–4, 6, 7, 9–12 | `progress.start` **after** the job is accepted |

**Verdict: deliberate UX split, not a correctness bug.** Previews that can sit in POST for a
while (organize dedup, Takeout scan, migrate plan) show the bar immediately. Runs and undos
start the bar once the server has accepted the job. Extraction should parameterize
`progressBeforeStart: boolean` (or call sites keep an optional pre-start), not pick one
globally.

### C. Park `#undo-card` in a stage host

| Sites | Behaviour |
|---|---|
| 1–4 | Empty stage, `appendChild($("undo-card"))`, restore to `document.body` + hide after |
| 5–13 | No parking |

**Verdict: deliberate.** Only the undo pair shares the global `#undo-card` progress node
(F45 / migrate-undo precedent). Parameter: `parkProgressIn` / cleanup callback.

### D. Outcome insertion vs replace

| Sites | Behaviour |
|---|---|
| 2, 4 | `refresh*Affordance` then `insertAdjacentHTML("afterbegin", summaryHtml)` so the
  outcome survives a spent journal / re-armed card (F0) |
| 1, 3 | Write into the stage host (preview still needs typed confirm) |
| 5–13 | Replace the result panel's `innerHTML` |

**Verdict: deliberate** for apply undos (2, 4). Preview undos writing the stage is deliberate.
Do not make all thirteen prepend.

### E. Cancelled terminal status (`d.status === "cancelled"`, with `ok: true`)

| Sites | Behaviour |
|---|---|
| 5 | Explicit "Check cancelled" card |
| 6 | Shows `organizeCompletion({ …, cancelled: true })` - partial work is real |
| 8, 9, 13 | Explicit "Preview cancelled" card |
| 1–4, 7, 10–12 | **No** cancelled branch; `ok: true` falls into the success path |

**Verdict: mixed.**

- **6 is deliberate** - organize run must not pretend nothing happened.
- **5, 8, 9, 13 are deliberate** - dry-run previews should say cancelled, not show a fake plan.
- **7, 10, 11, 12 (and undo 1–4) are drift → latent bug.** Cancel arrives as
  `{ ok: true, status: "cancelled", summary: … }`. Without a branch, verify can paint a
  "Checked" tally from an empty/partial summary; backup can paint `backupCompletion`; trip
  apply-to-disk can paint result cards; migrate run can claim "Moved 0 files"; undo apply can
  prepend "Put N files back" from a partial summary. Same class as the soak finding that
  forced cancelled-says-cancelled on organize. Each needs its own fix+test before or as part
  of making extraction choose the correct behaviour (preview wording vs run wording), not the
  majority silence.

### F. Progress status text (`setStatus` / `scaleStatus`)

| Sites | Behaviour |
|---|---|
| 5, 8 | Phase-aware (`scanning` / `hashing` / fallback) |
| 9, 10 | Unit `"photos"` |
| Others with `setStatus` | Unit `"files"`, single verb |
| Labels / verbs | Per-surface copy ("Checking undo", "Organizing", "Copying", …) |

**Verdict: deliberate.** Parameters: `label`, `unit`, optional `statusForProgress(p)`.

### G. Refuse field id / card target

Different DOM targets and `startRefusedCard(..., fieldId)` per screen (`org-dest`,
`verify-path`, `mig-path`, panel-dependent for migrate undo, etc.).

**Verdict: deliberate.** Parameters: `refusedInto` (setter or element id) and `refusedField`.

### H. Post-terminal side effects

| Effect | Sites |
|---|---|
| `loadCustody()` | 2, 4 (on ok), 6, 7, 10 |
| `loadDrives()` / `refreshDriveState()` | 7, 11, 12 |
| `refreshUndoAffordance` / organize twin | 2, 4, 10, 12 |
| `cleanupOffer = …` | 6, 10, 12 |
| Clear typed confirm / hide run button | 6, 11, 12, 10 |

**Verdict: deliberate.** Extraction returns `d`; callers keep side effects.

### I. Summary key names / render functions

`reversed_files` vs `restored`, `organizeCompletion` vs `backupCompletion` vs
`reviewResultCards` vs ad-hoc headlines. Entirely surface-specific.

**Verdict: deliberate.** `onDone(d)` callback, not one HTML template.

### J. Order: clear job handle vs render

Most clear `*Job = null` before or with render; 6/10/11 clear after rendering. No user-visible
bug found; cancel button may briefly still target a finished id. **Minor drift, not a latent
product bug.** Prefer clear-before-render in the helper for consistency.

---

## Latent bugs to fix before (or as dedicated commits ahead of) extraction

1. **Organize-undo preview/apply missing `started.ok === false`** (sites 3, 4) - DriveBusy /
   soft-fail can enter `awaitJob` without a job id. Mirror migrate-undo.
2. **Cancelled-says-cancelled missing on verify, backup run, trip apply-to-disk, migrate run,
   and both undo applies/previews** (sites 1–4, 7, 10–12) - success path on cancel. Align with
   the explicit cancelled cards on the preview jobs, except organize **run** which keeps its
   partial-completion card.

Extraction must not "fix" these by majority vote. Correct behaviour is the refused /
cancelled-honest paths already proven on the migrate-undo and preview sites.

---

## What commit 2 should parameterize (preview only)

```
runJob({
  button, busyLabel,
  start: () => api(...),          // or endpoint+body
  jobRef: { get, set },           // *Job handle
  progress, progressLabel,
  progressBeforeStart?: boolean,
  parkProgressIn?: HTMLElement,   // undo-card parking
  refusedInto, refusedField,
  unit, statusForProgress?,
  onDone: (d) => void,            // includes cancelled / error / success rendering + side effects
})
```

Callers own refuse HTML targets, cancelled copy, and post-success refreshes. The helper owns
only the shared sequence that, when hand-copied, produced F0.
