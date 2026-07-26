# Configurable Organization Structure - Phase 1 (recon + research)

Status: **Phase 1 deliverable, awaiting approval.** No code written. Closes BACKLOG item (h).

Two-tier customization (presets for normal users + a token template for power users), the
current opinionated structure staying the default. The load-bearing risk is not templates - it
is **mid-library template changes**; the feature only ships with a catalog-recorded template +
explicit warning + optional, dry-run-first migration. That is the bar this design is measured
against.

---

## Phase 1a - Recon (code truth)

### 1. Where destination-relative paths are built today

Path construction is **nearly centralized, but not single-site.** There are two places a
template must feed:

- **`build_relative(label, captured_at, filename)` - `organizer.py:112-121`.** The one true
  builder: `<Label>/YYYY/MM/<filename>`, or `<Label>/Undated/<filename>` when undated. Called
  from `plan()` at `organizer.py:171`. `build_destination()` (`organizer.py:124`) is a thin
  absolute-path wrapper over it for previews/tests.
- **`apply_events()` - `organizer.py:230-262`.** A **second, parallel construction site.** For
  files in a named event it *rewrites* the relative path, inlining the same `label / %Y / %m`
  logic (`organizer.py:253-259`) and inserting an event folder:
  `<Label>/YYYY/MM/YYYYMMDD_slug/<filename>`. It does **not** call `build_relative`. Any template
  must be threaded through here too, or event placement silently ignores the user's template.

Not separate sites (good news):

- **Ingest** reuses `plan()` (`service.ingest_preview`, the CLI `ingest` path) - it does not
  build paths itself, so no third site.
- **`_free_relative()` (`organizer.py:265-280`)** - collision suffixing - operates on the
  already-built relative string and is template-agnostic. It keeps working unchanged.

Today the "structure" has exactly two shapes, both flowing through `build_relative`: the default
derived label, and `--by-device` (label = device name). A template generalizes precisely this
choice.

**Implication:** introduce a single path-rendering seam (a `LayoutTemplate.render(fields)`),
call it from `build_relative`, and make `apply_events` render through the same template with an
extra `event` segment. Two call-sites to change, one renderer.

### 2. What the catalog knows per organized copy - is a migration expressible?

`file_copies` (schema v6, `catalog.py:81-91`) - the authoritative location record, one row per
`(content, drive)`:

```
file_copies(sha256, drive_uuid, relative, copy_sha256, size, copied_at, last_verified)
PRIMARY KEY (sha256, drive_uuid)
```

`relative` is stored per copy, so re-placement is expressible in principle:
**compute new relative → move at destination → UPDATE file_copies.relative.** But `file_copies`
does **not** store the fields a template needs (`category`, `captured_at`, `event_id`). Those
live in the `files` table (`catalog.py:25-40`: `category`, `captured_at`, `relative`,
`event_id`). So a migration run must:

1. `JOIN file_copies → files` (on `sha256`) to recover `category`, `captured_at`, `event_id`;
2. for event members, `JOIN files → events` (`catalog.py:55-62`: `slug`, `start_date`) to
   replay the event folder;
3. re-render the new template → new relative;
4. move the copy at the destination and `UPDATE file_copies.relative` (and the deprecated
   `files.relative`, kept in sync).

**Complications identified:**

- **Offline drives are the hard part.** `file_copies` holds rows for drives not currently
  connected. A migration can only physically move copies on **connected** drives; other drives'
  rows would become inconsistent with reality if we rewrote them without moving. The migration
  must be **per-drive and connected-only**, recording which drives are still pending so the run
  can be resumed when each is reconnected. (This mirrors the existing verify model, which already
  operates one connected drive at a time.)
- **Takeout-baked copies** (`copy_sha256 ≠ sha256`) are byte-for-byte different from their
  source, but a folder migration is a **move/rename at the destination** - the bytes do not
  change, so no re-bake and no hash change. `copy_sha256` stays valid; verify still passes.
- **Events** must be replayed, not guessed: the event slug + start month come from the `events`
  table, and the start-month-for-the-whole-event rule (`apply_events`) has to be honored so a
  migrated event stays whole.
- **Filename is untouched** (folders-only v1, see §4), so the `relative`'s basename is preserved
  across a migration - only the directory prefix changes.

**Verdict:** a migration run is expressible as `compute new relative per row → move → update`,
**provided** it is scoped to connected drives, joins through `files`/`events` for the template
fields, and defers offline drives.

### 3. Where per-run config lives - is there any settings persistence today?

**There is no settings/key-value persistence anywhere.** A grep for a settings or config table
across `packages/*/src` is empty. All configuration is per-run and ephemeral:

- **CLI:** argparse flags on each invocation - `--by-device`, `--no-rename`, `--events`,
  `--tz`, `--db`, etc. (`cli.py:66-145`). Nothing is remembered between runs.
- **App:** request bodies passed straight into `service.py` (`source`, `destination`, `db`) -
  again nothing persisted.

A persistent, per-catalog template is therefore **a genuinely new concept**: it needs a new
`settings` table added via the migration framework (`_MIGRATIONS`, `catalog.py:179-185`), which
would take the schema to **v7**. Storing it in the catalog (not a dotfile) is correct because
the template is a property *of a given organized library* - the migration-on-change logic keys
off exactly this.

### 4. Filename template vs folder template - same mechanism or separate?

**Separate mechanisms, cleanly.** The destination *filename* is produced by
`dated_filename()` in `naming.py` (the `YYYYMMDD_HHMMSS_<original>` stamp), gated by the
`rename` flag / `--no-rename`. Folder placement is `build_relative`. They share only the capture
date as input; the code paths are independent.

**Recommendation: v1 is folder-structure only.** The filename stamp stays exactly as it is.
Reasons: (a) it keeps the two path-construction sites (§1) as the entire blast radius; (b) it
keeps migrations trivially filename-preserving (§2); (c) filename templating is a separable,
lower-risk follow-up. A filename token template is on the explicit NOT-in-v1 list.

### Recon summary - what this feature actually touches

| Concern | Site | Change |
| --- | --- | --- |
| Folder path render | `build_relative` `organizer.py:112` | render via template |
| Event folder render | `apply_events` `organizer.py:253-259` | render via same template + `event` seg |
| Template fields available | `Decision` (`models.py:113`) | `category.label`, `captured_at` free; camera/city need plumbing → NOT-in-v1 |
| Persist template | none today | new `settings` table, schema **v7** |
| Migration | `file_copies` + `files` + `events` | join, re-render, move connected drives, defer offline |
| Filename | `naming.py` | untouched in v1 |

---

## Phase 1b - Research (community truth)

Primary-source survey of the established tools. Full citations in the appendix; the load-bearing
findings:

### 1. Token grammar - adopt what users already know

| Tool | Delimiter family | Date tokens | Notable |
| --- | --- | --- | --- |
| **Mylio** (closest analog) | `{token}` curly | `{Y}{y}{m}{D}{d}` single-letter | The consumer reference. Wart: cryptic single letters (`{o}` `{q}` `{j}`). **No location token.** |
| **exiftool** | `${tag}` **and** `%Y` strftime (mixed) | `%Y %m %d` | Double-`%%` escaping is its most-reported footgun. Two families = confusion. |
| **digiKam** | `[token:fmt]` bracket | `[date:yyyyMMdd]` | Richest: chainable `{modifier}`s, incl. `{default:"…"}` fallback for empty values. |
| **ImageRanger** | `%code` | `%yyyy %MM %dd` | Ships `%c` city / `%l` country; empty → literal `unknown_date`/`unknown_city`. |
| **phockup** | bare `YYYY/MM/DD` | `YYYY M DD` | Ambiguous (literal vs token); undated → `unknown/` bucket. |
| **elodie** | `%name` | `%year %month %city` | Pipe fallback in-template: `%album|%location|%"Beats me"`. |

**Consensus:** curly-brace `{token}` is the grammar mainstream photo users have actually seen
(Mylio). The improvement everyone's warts point to: **full readable token names**
(`{yyyy}/{mm}/{category}`), not single letters (Mylio) or a mixed `${}`+`%%` scheme (exiftool).
Expose a **closed date vocabulary** rather than raw strftime (avoids exiftool's `%%` trap).

### 2. Failure modes (each with a real source)

- **Windows reserved names** (case-insensitive, reserved *even with an extension* - `NUL.txt` ≡
  `NUL`): `CON PRN AUX NUL COM1–9 LPT1–9`. **Reserved chars:** `< > : " / \ | ? *` + control
  chars. **Trailing dots/spaces** silently stripped. (Microsoft naming-rules doc.)
- **Colon** is the classic photo-tool offender - it appears in times (`HH:MM:SS`) and camera
  strings, and opens an alternate data stream on Windows. Mature tools sanitize (exiftool's
  `${model;}` cleanup helper).
- **Empty token values** - the big one. exiftool's trap: a missing source tag → it **silently
  does not rename** and reports "0 files updated" (looks organized, isn't). The good pattern
  (phockup/ImageRanger): a named `unknown`/`Unsorted` bucket; digiKam/elodie: per-token
  `{default:…}` / pipe fallback. **Every token must have defined, visible empty-value behavior.**
- **Case-insensitive-but-preserving filesystems** (APFS, NTFS): `Beach/` and `beach/` are one
  folder whose case is set by whoever created it first → non-deterministic casing + collisions.
- **Path length:** Windows `MAX_PATH` 260 (opt-in long paths need a registry key); component
  limit 255. Deep templates + long names overflow fast.
- **Separator injection:** a token value containing `/` or `\` (camera `DSC-RX100 M/II`, a city
  with a slash) silently creates unintended nested folders. Sanitize token *values*, never the
  user's literal separators.

### 3. Migration UX - the gap truestill can beat

- **Mylio Auto Organize** is the direct analog and the cautionary tale: presets + custom tokens,
  but its safety model is a single modal - *"a permanent action and cannot be undone,"* it
  propagates to disk, **no preview, no undo.**
- **Lightroom:** move *within the app* (updates the index atomically); moving in the OS breaks
  links. No dry-run. Cannot copy-in-app.
- **`tfeldmann/organize`** is the model to emulate: *"Everything can be simulated before touching
  your files"* - it prints the full planned move set, with conflicts, before executing.
- **phockup** is "safe by construction": copy-by-default, checksum collision handling, `unknown`
  catch-all.

**No consumer competitor offers preview + undo.** truestill already owns the checksum/dedup machinery
to do both - this is the differentiator and the reason the feature is worth shipping.

### 4. Presets that actually ship (ranked by real prevalence)

`Year/Month` (Mylio #1, PictureEcho) · `Year/Month/Day` (phockup default, forum consensus) ·
`Year` (Mylio/PictureEcho) · flat `YYYY-MM-DD` (Mylio "Day") · `Year/Event` (top forum *request*)
· `Country/City/Year` (ImageRanger/elodie, only if we extract location). Excire is the
counter-example - it declines auto-foldering and organizes virtually; not our model.

---

## Phase 1c - Design proposal

### C1. Token set + grammar

Curly-brace, full-word tokens; a **closed vocabulary** (no raw strftime). v1 tokens are exactly
those the recon proved are free on `Decision` (§1a.5) plus literal separators:

| Token | Expands to | Source (free today) |
| --- | --- | --- |
| `{category}` | the derived label (`Camera`, `WhatsApp`, `Screenshots`, …) | `Decision.category.label` |
| `{yyyy}` / `{yy}` | `2023` / `23` | `captured_at` |
| `{mm}` / `{mon}` / `{month}` | `08` / `Aug` / `August` | `captured_at` |
| `{dd}` | `20` | `captured_at` |
| `{event}` | event folder `YYYYMMDD_slug`, else empty→fallback | `apply_events` (event members only) |

`/` is the only separator; literals (e.g. `Photos/{yyyy}`) pass through. **Undated files** keep
today's behavior - any template with no resolvable date routes to `{category}/Undated/` (the
existing `UNDATED_DIRNAME`), never a guessed date.

**Explicitly NOT v1 tokens** (need plumbing/network we don't have): `{camera_make}` `{camera_model}`
(in metadata but not carried on `Decision`), `{city}` `{country}` (needs reverse-geocoding, no
network), filename tokens (filename stays the `naming.py` stamp - see §1a.4).

### C2. Validation rules (from §1b.2, applied to the fully-expanded path before any write)

1. Sanitize **token values** (not user separators): replace `< > : " / \ | ? *` + control chars;
   strip trailing dots/spaces per component; collapse empty segments.
2. Reject Windows reserved device names case-insensitively (incl. with-extension forms), even on
   Linux/macOS, so the produced library stays portable.
3. Deterministic casing: canonicalize `{category}` casing (it already comes from a fixed rule
   set) and detect case-only folder collisions before writing.
4. Path-budget warning approaching 260 chars, for portability.
5. **Every token has an explicit empty-value policy:** `{event}` empty → the file simply omits
   that segment (stays in `{category}/{yyyy}/{mm}`); a whole-path with no date → `Undated/`.
   Never a silent skip (exiftool's trap).
6. Template is validated at *set* time (parse + dry-render against 3 sample files) and rejected
   with a specific message if it references an unknown token or produces an invalid path.

### C3. Live preview (both CLI and app)

Render the template against **3 representative sample files** - a dated Camera photo, a WhatsApp
image, and an undated file - and show the resulting paths. In the app Settings screen this
updates on keystroke; in the CLI, `truestill config --set-template '…' --preview` prints the three
renderings and does not persist until confirmed. This is the exiftool-`-p`/organize-simulate
pattern, surfaced before the template is ever saved.

### C4. Presets (from §1b.4; the leading `{category}` keeps today's users a no-op)

1. `{category}/{yyyy}/{mm}` - **default** (= today's fixed structure, generalized).
2. `{category}/{yyyy}/{mm}/{dd}`
3. `{category}/{yyyy}`
4. `{yyyy}-{mm}-{dd}` (flat dated)
5. `{category}/{yyyy}/{event}` (event-aware; `{event}` falls back to month when absent)

### C5. Catalog change (schema v7, via the existing migration framework)

Add a key/value settings table (the first persistent per-catalog setting, §1a.3):

```sql
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
-- migration (7, _add_settings); layout template stored under key 'layout_template'.
```

A fresh catalog defaults to preset #1. The stored template is what the mid-library-change flow
(§C6) diffs against. `CURRENT_SCHEMA_VERSION → 7`.

### C6. The mid-library change flow (the whole reason the feature ships)

When a user sets a template that differs from the stored one **and** the catalog already has
copies, present a warning with two choices:

- **Split-era (default, zero-risk):** keep existing copies where they are; apply the new template
  only to files organized from now on. The catalog records the template in effect; no files move.
- **Migrate existing library:** re-place existing copies under the new template. This is
  **copy-only-invariant, preview-first, connected-drives-only, journaled**:

  Operation order per connected drive:
  1. **Plan (pure).** `JOIN file_copies → files → events` to recover `category`/`captured_at`/
     `event_id`; re-render the new template → `(old_relative → new_relative)` for every copy on
     that drive. Detect collisions, empty-token buckets, case-only clashes, over-length paths.
  2. **Preview.** Show counts + a sample diff + all flagged rows. Nothing moves until confirmed.
  3. **Apply, journaled.** Write an undo journal `(sha256, drive_uuid, old, new)` first; then per
     file: `destination.move(old, new)` (a rename - bytes unchanged, so `copy_sha256` stays valid
     and verify still passes), then `UPDATE file_copies.relative` (and deprecated `files.relative`)
     in the same catalog transaction. Idempotent/resumable: a re-run skips rows already at `new`.
  4. **Offline drives are deferred**, not rewritten: their rows are left untouched and reported as
     "pending - reconnect to migrate," so the catalog never claims a path that isn't on disk.

  Sources are **never touched** (the copy-only invariant): migration operates exclusively on
  destination copies recorded in `file_copies`. Crash-safety comes from the journal + the
  move-then-update-in-one-transaction ordering: a crash leaves either the old or new path on disk
  with the catalog agreeing after journal replay.

### C7. Surfaces

- **App:** a new minimal **Settings** screen (the app's first) - preset dropdown, editable
  template field, live 3-file preview, and a "Change existing library…" button that opens the
  §C6 preview-then-apply flow. Dry-run posture preserved: preview writes nothing.
- **CLI:** `truestill config --show` / `--set-template '…'` (validates + previews before persisting);
  `truestill organize` reads the stored template; `truestill migrate-layout [--apply]` runs §C6 (dry-run
  default, `--apply` to execute, one connected drive at a time). No new flag on `organize`.

### C8. Explicitly NOT in v1

- Filename templating (folders only; filename stays the `naming.py` stamp).
- `{camera_make}`/`{camera_model}`, `{city}`/`{country}` tokens (plumbing / no-network).
- Raw strftime tokens (closed vocabulary only).
- Multi-drive simultaneous migration and auto-migration on reconnect (offline drives are reported
  as pending; the user re-runs `migrate-layout` when a drive is back).
- Per-category or conditional templates (one template per catalog).

---

## Appendix - primary sources

exiftool [filename](https://exiftool.org/filename.html) · [FAQ](https://exiftool.sourceforge.net/faq.html) ·
Mylio [Auto Organize](https://manual.mylio.com/24.3/en/topic/auto-organize-folders) ·
[Rename tokens](https://manual.mylio.com/24.3/en/topic/rename-files-folders) ·
ImageRanger [Sort Into Folders](https://imageranger.com/docs/en/sort_into_folders.htm) ·
digiKam [rename](https://docs.digikam.org/en/main_window/image_view.html) ·
[phockup](https://github.com/ivandokov/phockup) · [elodie](https://github.com/jmathai/elodie) ·
[tfeldmann/organize](https://github.com/tfeldmann/organize) · [SortPhotos](https://github.com/andrewning/sortphotos) ·
[PictureEcho](https://pictureecho.com/blog/how-to-store-photo-albums-in-folders-based-on-their-date-taken/) ·
Microsoft [naming rules](https://learn.microsoft.com/en-us/windows/win32/fileio/naming-a-file) ·
[MAX_PATH](https://learn.microsoft.com/en-us/windows/win32/fileio/maximum-file-path-limitation) ·
Adobe [Lightroom folders](https://helpx.adobe.com/lightroom-classic/help/create-folders.html)
