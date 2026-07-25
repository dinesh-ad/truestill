# Metadata Recovery Fallback Chain — Phase 1 (corpus + recon + research)

Status: **Decided.** Phase 2 shipped the never-silent **skipped-file reporting fix**
(`organizer.scan_source` + report); **no fallback parser was added** — declined on the evidence
below. The sentinel-rejection rule and the ffprobe/schema-v9 reservation are recorded as binding
conventions in `docs/IMPLEMENTATION_STANDARDS.md §1`. Recognizing more video extensions is tracked
as backlog item (l).

**Headline (extended corpus, 37 files across 22 formats):** on the 19 personal files, exiftool
dates **every file that carries a real embedded date**, and **no fallback parser recovers a
single genuine capture date exiftool missed**. Across the whole set the *only* unique recovery is
ffprobe reading a **sample's encode timestamp** from an `.ogv` — a downloaded sample, in an
extension vaeon doesn't even recognize, and an encode (not capture) date. Meanwhile the parsers
introduce two distinct hazards: hachoir reports EXIF **`ModifyDate`** as capture (2-week-wrong on
an edited photo), and on dateless videos hachoir/pymediainfo emit **epoch-sentinel dates**
(`1904-01-01` for ISO-BMFF/QuickTime, `1970-01-01` for ASF/WMV) that a naive chain would file
under **1904 / 1970** instead of `Undated/`. The evidence says **add no dependency.** Two things
do ship: the never-silent **skipped-file reporting fix** (§1b.2), now covering the **11
unrecognized extensions** the corpus surfaced; and — reserved for if a parser is ever justified —
a hard **sentinel-date rejection rule**.

---

## Phase 1a — The corpus test

Corpus: `/home/dinesh/Damon/vaeon-corpus`, treated strictly read-only. **37 files, 295 MB** across
22 extensions — **19 personal** files (higher-signal evidence) and **18 downloaded format
samples** (some with stripped metadata, so "nothing can date it" is a *valid* result for those,
distinct from "a fallback beat exiftool"). Candidate parsers were run standalone via throwaway
`uv run --with hachoir --with pymediainfo` and the `ffprobe` binary — **none added as a project
dependency**. Full per-file output: `scratchpad/corpus_probe.py`.

### Personal files — the diff that matters (18 probed; 1 `.pdf` is non-media)

| File | exiftool embedded | vaeon-final | fallback parsers |
| --- | --- | --- | --- |
| `00123.MTS` (Sony AVCHD) | **DateTimeOriginal** 2023-08-20 (+05:30) | exif 2023-08-20 | pymediainfo ✓ agrees · ffprobe — · hachoir — |
| `VID-…WA0020.mp4` (WhatsApp) | **CreateDate** 2025-08-04 | exif 2025-08-04 | all three ✓ agree |
| 8× camera JPEG (`IMG_*`, `CSC_0019`, `F18A0416`, `_TLS4688`, `Screenshot_*`) | **DateTimeOriginal** ✓ | exif ✓ | hachoir echoes, **except `F18A0416` → 2018-11-03 ✗** (ModifyDate, 2 wks wrong) |
| `IMG_20180819…` | NONE (only `ModifyDate`) | **filename** 2018-08-19 | hachoir = ModifyDate, same day (exiftool sees it too) |
| `2 012.jpg`, `2.png`, `881783.png`, `circle-cropped.png`, `scan-a.jpg` | NONE | **UNDATED** | all — (genuinely dateless scans/graphics) |
| `sample_1280x720*.3gp` ×2 (dateless) | NONE | UNDATED | **hachoir → 1904-01-01 ✗ sentinel** · others — |

**Every personal file with a real embedded date is dated by exiftool.** Unique capture-date
recoveries by a fallback: **zero**. The two dateless `.3gp` files expose the sentinel hazard
below.

### Downloaded samples (18) — mostly stripped, and where the sentinels showed up

| Outcome | Files |
| --- | --- |
| exiftool NONE **and** every parser NONE → correctly `Undated/` | `.avi .hevc .m2ts .m2v .mjpeg .mpeg .rm .swf .ts .vob ×2 .webm .wtv` (13) |
| exiftool NONE, **ffprobe recovered a real date** (2013-05-03, the sample's *encode* time) | `sample-ogv…ogv` — **the one genuine unique recovery in the whole corpus** |
| exiftool NONE, parser returned an **epoch sentinel** (unset field read as a date) | `.mov`, `.f4v` → hachoir `1904-01-01`; `.asf`, `.wmv` → hachoir **and** pymediainfo `1970-01-01` |

### What the extended corpus says

- **exiftool is still the ceiling for real dates.** No parser recovered a genuine *capture* date
  exiftool missed. The single unique recovery (ffprobe on the `.ogv`) is a *sample's encode
  timestamp*, on an extension vaeon doesn't recognize — not evidence of value on personal media.
- **New, decisive hazard — epoch sentinels.** On dateless ISO-BMFF/QuickTime containers hachoir
  returns `1904-01-01` (that format's zero-epoch) and on ASF/WMV both hachoir and pymediainfo
  return `1970-01-01` — the *unset* field, reported as if it were a real date. A naive chain would
  file these under **1904 / 1970**, which is strictly worse than `Undated/` and violates the
  never-guess rule. vaeon already rejects exiftool's all-zero dates (`parse_exif_datetime` drops
  `0000…`); any future parser output would need the same sentinel rejection (see recommendation).
- **hachoir's `ModifyDate`-as-capture bug persists** (`F18A0416`, 2 weeks wrong) — unchanged and
  disqualifying on its own.
- **11 extensions are unrecognized by vaeon today** (`.asf .f4v .hevc .m2v .mjpeg .ogv .rm .swf
  .ts .vob .wtv`) — `discover` would silently skip them (§1b.2). Whether to *recognize* more video
  extensions is a separate call from the date chain; surfacing them is the immediate fix.

The corpus now covers the motivating formats and still yields no justification for a parser. The
sample set behaved exactly as flagged — stripped files are correctly undateable — so the
personal-file evidence is the deciding signal, and it says the same thing as the first pass, now
with a concrete new reason (sentinels) to be *especially* wary of naive fallbacks.

---

## Phase 1b — Recon (code truth)

### 1. The extraction seam and where a chain would insert

- exiftool is read in one place: `exif.read_metadata` (`exif.py:116`) — a batched
  (`BATCH_SIZE=200`) `exiftool -json` call returning the requested tags per file.
- The date decision is `dates.resolve_capture_datetime` (`dates.py:107`): it calls
  `_exif_datetime` (embedded `DATE_TAGS`), then Takeout sidecars, then `date_from_filename`, then
  `Undated`. **The fallback chain's natural insertion point is exactly here** — a new step
  *after* `_exif_datetime` returns `None` and *before* the filename fallback, since we only want
  a container parser when exiftool yielded no embedded date.
- Structurally a chain needs three things, all already available at that seam: the **file path**
  (`resolve_capture_datetime` already receives it), a **parser registry** returning
  `(datetime, tool, field)`, and a per-file lazy call (only the handful exiftool missed reach
  this branch, so batching is unnecessary). It returns a new `DateSource` (e.g. `CONTAINER`) so
  provenance and reporting can distinguish it. No change to `read_metadata`'s batch path.

### 2. Non-media handling today — silent, and the never-silent fix (ships with this feature)

`discover` (`organizer.py:98-108`) is the only filter: line **106**,
`if all_files or path.suffix.lower() in MEDIA_EXTENSIONS: found.append(path)`. Anything whose
extension is not in `MEDIA_EXTENSIONS` is **silently dropped** — never counted, logged, or
returned. The extended corpus made this vivid: not just the `.pdf`, but **11 video-ish extensions
vaeon doesn't recognize** (`.asf .f4v .hevc .m2v .mjpeg .ogv .rm .swf .ts .vob .wtv`) would all
vanish from every report with no trace. A user organizing a folder of `.vob` DVD rips would be
told nothing happened to them. That violates the never-silent principle exactly as a
silently-skipped undated file would.

**Proposed fix (in scope for this feature):** have `discover` (or a thin wrapper) also return the
skipped paths; the end-of-run report then shows a **count summarized by extension** — separating
*documents* (`.pdf ×1`) from *unrecognized video/media-ish* extensions (`.vob ×2, .ogv ×1, …`),
since the latter hint the user may want them recognized. **No copying** of skipped files in v1 —
an `Others/` sweep is explicitly future/demand-driven, and *expanding* `MEDIA_EXTENSIONS` is a
separate, deliberate decision (some of these — `.swf`, raw `.hevc`/`.m2v`/`.mjpeg` elementary
streams — are not obviously "photos to back up"). Surfacing makes "what happened to every file in
the source" fully accountable; recognition can follow on demand.

### 3. Provenance — schema impact

`files` (`catalog.py:25-40`) stores `captured_at` and `category` but **no date provenance**:
there is no `date_source`/`date_tag`/`date_tool` column, and `record_uploaded` doesn't persist
the `Decision.date_source`/`date_tag` it already computes. Recording "which tool + which field
dated this file" (Phase 2) is therefore a **new migration → schema v9**: add `date_tool` and
`date_field` (nullable `TEXT`) to `files`, populated from the resolver's result. Small, additive,
no backfill needed (legacy rows keep `NULL`). Current version is **8** (`catalog.py:115`).

---

## Phase 1c — Research (community truth)

The task scopes deep issue-tracker research to "each parser the corpus proves useful" — and the
extended corpus proves **none** useful for personal media. The findings below reinforce the
add-nothing recommendation and record the correctness hazards concretely.

- **hachoir** (pure-Python, no native dep — trivial to package, GPLv2). Disqualified twice over on
  *correctness*: (a) its JPEG "creation_date" is EXIF `ModifyDate` (last edit) → two-week-wrong on
  a normally-edited Canon photo; (b) it reports **epoch sentinels** (`1904-01-01`) for dateless
  ISO-BMFF/QuickTime as if they were real dates. It is *wrong* on the common edited-photo case and
  *dangerous* on the dateless-video case; packaging ease is irrelevant.
- **ffprobe** (the FFmpeg binary, LGPL/GPL). The only parser with a *genuine* unique recovery —
  the `.ogv` sample's encode time — and it also uniquely *avoided* the epoch-sentinel trap
  (returned `-`, not a fake date, for the dateless containers). But it recovered nothing on
  personal media, *failed* on the AVCHD `.mts`, and carries the heaviest packaging cost: vendoring
  a tens-of-MB multi-file binary or requiring users to install FFmpeg — disproportionate friction
  for the broad audience given the near-zero gain. If a future corpus ever justifies one parser,
  ffprobe's sentinel-safety makes it the front-runner despite the weight.
- **pymediainfo** (MIT wrapper over BSD-licensed MediaInfo; wheels bundle native `libMediaInfo`
  ~5–6 MB, prebuilt for Windows/macOS/Linux incl. arm64). Cleanest to package, matched exiftool on
  the real videos and carried tz offsets — but it *also* emits the `1970-01-01` sentinel on
  dateless ASF/WMV, so it would need the same guarding, and it recovers nothing exiftool lacks.

(All licenses are compatible; the point is moot while the recommendation is to add none.)

---

## Recommendation

1. **Add no fallback parser now.** The extended corpus (22 formats, the motivating ones included)
   yields **zero** genuine capture-date recoveries on personal media — the one unique recovery is
   a sample's *encode* time on an unrecognized extension. Meanwhile the parsers introduce wrong
   dates (hachoir `ModifyDate`) and, worse, **epoch sentinels** that would misfile to 1904/1970.
   The dependency policy's bar — a parser must date a file only it can — is not met, so no
   dependency is added.
2. **Ship the never-silent skipped-file reporting fix** (§1b.2) as the concrete, valuable part of
   this feature: count and summarize skipped files by extension (documents vs unrecognized
   media-ish) in the end-of-run report; no copying in v1. This is the one thing the corpus proved
   is *missing* today.
3. **Sentinel rejection is now a hard design rule** for any future parser: a fallback date equal
   to a known zero-epoch (`1904-01-01T00:00:00`, `1970-01-01T00:00:00`, or all-zero) must be
   treated as "no date", exactly as `parse_exif_datetime` already drops exiftool's `0000…`. Absent
   this, a naive chain is strictly worse than the current `Undated/` behaviour.
4. **If a parser is ever justified** (a future corpus showing a real unique *capture*-date
   recovery on personal media), **ffprobe is the front-runner** — it was the only sentinel-safe
   parser and the only one with a genuine recovery — accepting its packaging weight; **hachoir is
   ruled out** on correctness. Reserve schema **v9** for date provenance (`date_tool`,
   `date_field` on `files`) and put the seam in `resolve_capture_datetime` between embedded-EXIF
   and the filename fallback, emitting a `CONTAINER` `DateSource`.
5. **Separately, consider recognizing more video extensions** (`.vob`, `.ogv`, `.m2v`, …) in
   `MEDIA_EXTENSIONS` — a deliberate, orthogonal decision the reporting fix will inform, not part
   of the date chain.
6. The already-shipped **`CreationDate` fix** (`f89fec8`) remains the one real, evidence-backed
   video-date improvement — it fixed a *wrong* exiftool date (UTC vs local), a different problem
   than *missing* dates, and needed no dependency.

**Stopping here for approval** before adding any dependency or fallback code.
