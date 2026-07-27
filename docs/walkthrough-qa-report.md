# truestill - Full-App Walkthrough QA Report

> ## ✅ Re-run on the fixed build (2026-07-26) - verdict: **launch-ready**
>
> All approved fixes are shipped, each screenshot-verified on a live build; `make check` green
> throughout. **Both blockers are resolved and both approved features are built.**
> *(This line originally cited a test count as evidence. It has grown since, and the count was
> never the point - the standard says assert behaviour, not totals. Green is the claim.)*
>
> | Original finding | Status on the fixed build |
> |---|---|
> | **B1** - Organize reports "nothing to do" after a real run | **Fixed.** Handler unwraps the `summary` envelope like Verify/Migrate; a corpus run now reads "Done · 30 uploaded · 2 duplicate" (matches disk). Regression + source-guard tests. `08-B1-fixed-real-outcome.jpg` |
> | **B2** - Trips is a dead-end; named trips never reach disk | **Fixed.** Trips now reviews the organized library, links `files.event_id`, and applies via the journalled migrate engine (preview → confirm). Verified: Goa/Paris folders landed on disk. `09-B2-trips-preview-apply.jpg` |
> | **Dark-mode** - at-risk/warning banners illegible | **Fixed.** The `[data-theme=dark]` toggle now mirrors the full dark palette; every semantic pair WCAG-audited (muted bumped to AA; safety copy → secondary). Guard test prevents drift. `10-dark-atrisk-fixed.jpg` |
> | **Multi-drive** - no way to make a 2nd copy (3-2-1) | **Built.** In-app "Copy your library to another drive": per-drive presence, verify-after-write, free-space block, custody → "safe in 2 places". `11-backup-to-second-drive.jpg` |
> | Papercuts (fresh-catalog wording · photos/videos conflation · inert button · verify last-checked) | **Cleared** - see the `app(ui): clear up the walkthrough papercuts` commit. |
>
> **Fresh per-screen verdict:** Organize ✅ · Trips & events ✅ · Import ✅ · Backups ✅ · Find ✅ ·
> Settings ✅ · first-run empty states ✅ · console/terminal clean ✅. **Overall: launch-ready.**
> Remaining scope notes (not blockers): Trips clusters the default `Camera` label (by-device layout
> is a follow-on); rclone-export for power users is a later add; the report's original screen-by-screen
> findings below are retained for provenance.
>
> ---

# truestill - Full-App Walkthrough QA Report (original pass)

**Date:** 2026-07-26 · **Method:** Chrome-driven (Claude-in-Chrome), real app, real corpus, as a
first-time user. **Rule for this pass:** findings only - **no fixes applied**, awaiting approval.

**Setup:** dev catalog `reports/catalog.sqlite` backed up and set aside; all runs on throwaway
catalogs. Source (read-only): `$TRUESTILL_CORPUS` (45 files → 22 photos · 10 videos ·
13 skipped). Destinations under `/tmp/truestill-qa`. Realistic Backups catalog built via CLI (corpus on
DriveA + a single-copy at-risk set); synthetic clustered fixture for Trips; synthetic mini-Takeout
for Import. Both first-run-empty and populated states were exercised.

---

## Overall verdict: **NOT launch-ready**

Two **blockers** sit on the two primary creative flows. Neither loses or corrupts data - the
pipeline underneath is correct and honest - but in both cases the **UI tells the user the wrong
thing about what happened**, which for a trust-first app aimed at non-technical users is exactly the
launch-day embarrassment this pass was hunting for. Everything else (empty states, dedup, dating,
backups math, verify, find, settings, import, guardrails, console, terminal) is in good shape.

| Screen | Verdict |
|---|---|
| First-run empty states (all 6) | ✅ launch-ready |
| **Organize** | ❌ **BLOCKER** - success reports "nothing to do" |
| **Trips & events** | ❌ **BLOCKER** - named trips never reach disk (dead-end) |
| Import | ✅ preview launch-ready (real *ingest run* not exercised - see note) |
| Backups | ⚠️ launch-ready **after** the dark-mode fix; one product question |
| Find | ✅ launch-ready |
| Settings | ✅ launch-ready |
| Console / Terminal | ✅ clean (zero app errors, zero terminal noise) |

---

## BLOCKERS

### B1 - Organize success reports "Done / nothing to do"
**Screen:** Organize. **Screenshot:** `qa-screenshots/02-BLOCKER-done-nothing-to-do.jpg`
**What happened (100% reproducible, fresh catalog + fresh dest):** Preview shows
"22 photos · 10 videos found - 30 new". Click **Organize 30 files** → progress bar runs 0→32 →
result card reads **"Done / nothing to do."** Meanwhile the custody strip correctly updates to
"20 photos · 10 videos" and **all 30 files are on disk** (`Camera/YYYY/MM/…`, catalog has 30). The
organize *succeeded*; the confirmation is inverted.
**Why it matters:** This is the single most-used flow. A first user copies 30 irreplaceable files
and the app says nothing happened - they'll think it failed. Verified against both the Preview→Organize
path and a clean repro.
**Root cause (found, not fixed):** `jobs.py:57` wraps every job result under a `summary` key
(`{"type":"done","summary":{…}}`). `organize_run` returns `{"outcomes":{…}}` → it lands at
`d.summary.outcomes`. But `app.js:254` reads top-level `d.outcomes` → always `{}` → empty line →
`"nothing to do"`. **Verify (`app.js:294`) and Migrate (`app.js:420`) unwrap `d.summary` correctly;
Organize is the lone flow that forgot.**
**Fix direction:** `const o = (d.summary || d).outcomes || {};` - then reword the raw status line
(`"uploaded 30"`) into humane copy (e.g. "30 organized · 2 duplicates skipped · 14 with no date →
Undated").

### B2 - "Trips & events" is a dead-end: named trips never reach disk
**Screen:** Trips & events. **What happened (deterministic, via the exact endpoints the UI calls):**
Find trips on a clustered fixture → 2 events. **Propose ✓, Merge ✓** (2 → 1 "18 photos"), name
fields + Split present. **Save names** returns a *correct* placement plan
(`Camera/2024/06/20240615_goa-trip/…`, `…/20240618_paris-trip/…`) and persists the names to the
catalog - but the UI only shows *"Named 18 photo(s) into trips."* and **ignores the placements**.
Then organizing that same folder (the only UI write path) lands files in **plain `Camera/2024/06/`** -
the named event folders **never appear on disk**.
**Why it matters:** The entire headline "Trips & events" feature produces no durable on-disk outcome
in the UI. A user names their vacation "Goa", clicks Save, gets a success toast, and no Goa folder
is ever created.
**Root cause:** `organize_run` (`service.py:122`) does its own `plan()→resolve()→execute()` and never
calls `run_event_stage`/`apply_events`, so saved events are ignored. The Trips screen
(`index.html:78-94`) has **no destination field and no apply/organize control** - only Find/Merge/
Split/Save names. (The core *can* do it - `truestill organize --events` exists - the UI just never wires
it to disk.)
**Fix direction:** either give Trips a destination + an "Organize into these trips" run that uses the
event-applied session, or have `organize_run` apply saved catalog events so a later Organize picks up
named trips. Surface the placement preview; reword the toast to say what happens next.

---

## PAPERCUTS (works, but winces)

1. **Dark-mode: the at-risk / info banners are illegible.** `qa-screenshots/05-backups-dark-atrisk-illegible.jpg`.
   The amber "N photo(s) exist in only one place" banner (Backups) and "Nothing to organize" card
   (Organize) keep a pale cream background with pale text in dark mode → light-on-light, confirmed by
   zoom. This hits the **safety** message hardest. Needs a dark-theme variant for the amber banner/card.
2. **No UI path to build multi-drive redundancy (backup app!).** Backups. Re-organizing the library to
   a second drive hits catalog exact-dedup and skips everything → **BackupB shows "0 photos · 0 B"**,
   nothing written there. There is no "copy my library to this new drive" action anywhere in the UI
   (only Organize [dedups away] and Verify [read-only]). For a 3-2-1 tagline, the team should confirm
   the intended flow. *(Medium/high - product question, not a crash.)*
3. **"duplicates - already backed up, will skip" on a fresh catalog.** Organize result card. On a brand
   new library the 2 "duplicates" are intra-batch (a scanned document in the corpus, `scan-a.jpg`,
   and its `(Copy)` duplicate); nothing
   is "backed up" yet. Copy shouldn't assume a backup exists.
4. **"N photos" conflates videos in three places.** The picker footer button ("Use this folder · 32
   photos" - while the field itself correctly says "32 photos and videos"), the Backups at-risk banner
   ("48 photo(s)"), and per-drive counts. Given the whole stats-refinement split, these should read
   "N files" or "N photos · M videos".
5. **Organize-without-Preview button is silently inert.** With a valid source+dest but no Preview, the
   muted "Organize files" button does nothing on click - no result, no toast, no error. A visible
   button that no-ops reads as broken; either visibly disable it or have it trigger the Preview.
6. **Verify "last checked" doesn't refresh live.** After a successful Verify (result card correct:
   "48 verified · 0 missing · 0 changed"), the drive card still says "last checked: never" until you
   re-navigate to Backups (then shows the date). Refresh the drive list after verify.
7. **"14 no date → Undated" is a bare, non-clickable count.** Confirms backlog item (n): it should be
   explorable (which files, why undated).
8. **Post-organize state is stale.** After a run the button still says "Organize 30 files" and the dest
   field still reads "This folder doesn't exist yet" (even though the run created it and wrote 30 files).
9. **Long pages: sidebar isn't sticky + SPA nav doesn't reset scroll.** On Settings (a tall page) the
   nav scrolls out of view; navigating from a scrolled page lands the next screen scrolled down into
   empty space.

## POLISH (nice-to-have)

- Three unlabeled grey pips in the custody strip when 0 drives are connected - a first user may wonder
  what the little squares are.
- Trips inline count didn't refresh when the folder's contents changed but the path string didn't
  (expected; noted for completeness).

---

## What's solid (verified working)

- **Every empty state guides rather than confuses** - all six screens (`06-trips-empty-light.jpg`);
  custody strip honest "0 photos / not backed up yet".
- **Dry-run purity holds** - Preview never wrote to disk or catalog (custody stayed "0 photos"; files
  appeared only on Organize, single ctime burst). Core invariant intact.
- **Disk structure matches the card exactly** - `Camera/2008…2024/MM`, `Saved/Undated`,
  `Screenshots/2026/07`, `WhatsApp/2025/08`; capture-dated, never mtime.
- **Result card is honest and complete** (`01-organize-result-card-light.jpg`): photos·videos split
  headline, dedup counts, category **chips + first-timer legend** ("Saved - Images saved from apps or
  the web…"), collapsible **By format** (jpg 13 · png 3 · heic 3 · … / 3gp 2 · mts 1 · …, sums match),
  and **"13 file(s) skipped"** disclosure (documents + unrecognized by extension) - never-silent.
- **Folder picker** - Places + breadcrumb + live media count; "Create it" for a missing dest works.
- **Verify** - correct summary ("48 verified · 0 missing · 0 changed"), marker detection ("Ready ·
  backup drive ✓").
- **Find** - results table (File/Drive/Location, monospace) and a clean no-match state.
- **Settings** - live layout preview updates per preset; "affects files you organize from now on"
  copy present; Light/Dark/Match-system toggle works and persists (`04-organize-dark.jpg`).
- **Import** - validates the Takeout folder and **recovers dates from `photoTakenTime` sidecars**
  (EXIF stripped, 0 still undated).
- **Progress + cancel UI exists** (`07-organize-progress.jpg`, "17 / 32 · Cancel").
- **Console: clean** - 30 messages, all from the Claude-in-Chrome extension; **zero from truestill**.
- **Terminal: clean** - every app log is exactly one line (the startup URL); no warnings, no
  tracebacks, no DecompressionBomb, no request noise.

---

## Hero / README candidates (well-composed, seeded states)

> ⚠️ **Historical note (added 2026-07-26, post-rename): none of these 11 screenshots can ship
> in a user-facing README.** Every one was captured on the pre-rename build and shows the
> **`vaeon.` wordmark** in the sidebar and `vaeon` body copy ("Point vaeon at a messy folder"),
> plus machine-local absolute paths and `/tmp/vaeon-*` paths in the folder fields. They are retained
> as the **evidence record** for the findings below - that is all they are now.
> The README set must be **re-captured on the truestill build against a neutral demo library**;
> that requirement is recorded in `PROJECT_STATUS.md` road-item 2.
> *(Audited image-by-image: no photo thumbnails, no personal filenames - the UI is text and
> cards throughout. The only personal data in the set is path strings.)*

1. `qa-screenshots/01-organize-result-card-light.jpg` - the honest result card (split + legend + by-format).
2. `qa-screenshots/03-backups-light.jpg` - library summary + two drives + at-risk + verify result.
3. `qa-screenshots/04-organize-dark.jpg` - Organize, dark theme.
4. `qa-screenshots/06-trips-empty-light.jpg` - clean empty state.
5. `qa-screenshots/07-organize-progress.jpg` - live progress with Cancel.
6. `qa-screenshots/02-BLOCKER-done-nothing-to-do.jpg` - **evidence, not a hero** (the B1 contradiction).
7. `qa-screenshots/05-backups-dark-atrisk-illegible.jpg` - **evidence** of the dark-mode contrast bug.

*(1–5 were the composition candidates; 6–7 are bug evidence. All 11 need re-capture - see the
note above.)*

---

## Notes / not fully exercised

- **Import *ingest run*** (as opposed to preview) was not run end-to-end, so it was not confirmed
  whether it shares B1's `d.summary` done-handler bug - **worth checking** when fixing B1.
- **Cancel mid-operation**: the corpus/fixtures completed too fast to reliably interrupt a running
  job; the progress+Cancel UI is present and wired.
- Intermittent Chrome/CDP screenshot freezes during the session were a **browser-automation** artifact
  (backend stayed healthy throughout), not app behavior; the two Trips findings were confirmed
  deterministically via the API to avoid depending on the flaky renderer.

---

## Recommended fix order (on approval)

1. **B1** - one-line unwrap + humane result copy (small, high impact).
2. **B2** - wire named trips to disk (destination + apply, or apply saved events in organize).
3. **Dark-mode banner contrast** (papercut #1 - safety message legibility).
4. Papercuts #2–#9, then polish.
