# Date resolution: how others layer it, and what we lack

Status: **Research only (2026-07-28). No code changed, nothing implemented.** Recommendations
at the end; each is a decision to take separately.

---

## 1. What truestill does today, from the code

Read from `dates.py` and `exif.py` rather than memory:

**Tag preference**, one ordered tuple (`dates.DATE_TAGS`):
`DateTimeOriginal` → `CreationDate` → `CreateDate` → `MediaCreateDate` → `TrackCreateDate`

**Tier order** (`dates.resolve_capture_datetime`): sane embedded EXIF → Takeout `photoTakenTime`
→ Takeout `creationTime` → filename convention (messenger conventions refused) → `Undated/`.

**Guards:** hard sentinels `1904-01-01` and `1970-01-01` rejected at *every* tier; suspect camera
defaults (`1980-01-01`, `1999-12-31`, `2000-01-01` at exact midnight) accepted-and-flagged;
sanity window 1900–2100.

**`ModifyDate` and `FileModifyDate` appear nowhere in the codebase.** Confirmed by grep. That is
the single most important fact in this document, and §3 explains why.

## 2. How comparable tools layer it

| Tool | Order, in short | Notable |
|---|---|---|
| **Immich** | `DateTimeOriginal` → `CreateDate` → `MediaCreateDate`/QuickTime → filename patterns → file mtime | Falls back to **mtime** as a last resort; has repeatedly shipped bugs where a re-copied library dated to the copy date |
| **PhotoPrism** | EXIF `DateTimeOriginal` → XMP → embedded video tags → **filename** → mtime | Keeps a separate `TakenSrc` field recording *which* source won - the provenance idea `(n)`/`(ii)` want |
| **Elodie** | EXIF → **Google JSON sidecar** → filename → mtime | Sidecar tier is first-class, like ours |
| **Phockup** | EXIF `DateTimeOriginal` → other EXIF dates → filename → mtime | Explicit `--date-field` override for awkward libraries |
| **exiftool workflows** (`-FileModifyDate<DateTimeOriginal`) | whatever the user names, in order | The community norm is an explicit ordered `-d` list; the tool takes no position |

**The consensus shape is ours.** Every tool starts at `DateTimeOriginal`, falls through other
embedded tags, then filename. We match that, and we are *stricter* at the top (sentinel
rejection) and at the filename tier (messenger conventions refused, which none of the others
do).

## 3. The tier we deliberately lack, and should keep lacking

**Every surveyed tool falls back to file mtime. We do not, and that is the correct call.**

This is not a gap; it is the difference between the tools. A Takeout export, a cloud re-sync, a
drive-to-drive copy or a restore-from-backup all rewrite mtime, so the mtime fallback dates a
whole library to the day it was moved. It is the single most-reported dating complaint against
Immich and PhotoPrism, and `IMPLEMENTATION_STANDARDS.md` §1 already forbids it.

`ModifyDate` (the EXIF field, distinct from filesystem mtime) deserves the same refusal for a
related reason: it is the *edit* time. A photo cropped in 2024 carries a 2024 `ModifyDate` and a
2014 `DateTimeOriginal`. Reading it would silently re-date edited photos — and, worse, it is
often present when `DateTimeOriginal` is absent, so a naive "any date is better than none" chain
reaches for it precisely when it is most wrong. **Recommendation: continue to read neither, and
say so explicitly in the contract, since "we don't do this" is currently only visible as an
absence.**

## 4. Real gaps worth considering

**(a) XMP tags — probed, and the answer is no.** ⚠ **Superseded by the corpus probe below.**
Original reasoning retained: PhotoPrism consults XMP; we do not request any XMP
field. `XMP:DateTimeOriginal` and `XMP:CreateDate` matter for two real populations: files edited
by Adobe tooling, and sidecar-based RAW workflows where the date lives in the `.xmp` beside the
raw file. Both are plausible in a photographer's library.
**Recommendation: worth adding**, slotting *after* the embedded EXIF tags and *before* Takeout,
at a cost of two more names in `REQUESTED_TAGS` — exiftool already reads them in the same pass,
so this is close to free. Wants a corpus probe first, per the fallback-parser policy.

**(b) `GPSDateStamp`/`GPSDateTime` — narrow but trustworthy.** GPS time comes from satellites,
not from a camera clock, so it is immune to the dead-battery defaults our Tier B flags. It is
absent from most files and only ever a *cross-check*.
**Recommendation: not a tier.** Its real use is validating a suspect Tier B date — a photo dated
`2000-01-01T00:00` with a 2014 GPS timestamp is provably a dead clock. Record as a possible
input to `(ii)`'s human-confirmation flow rather than as a resolution tier.

**(c) Timezone.** We convert Takeout epochs exactly once and expose `--tz` as a single fixed
offset; EXIF `DateTimeOriginal` is naive local wall-clock, which is the right reading. The
`CreationDate` preference over `CreateDate` for QuickTime is already correct and better than
most — `CreateDate` is UTC per spec and mis-dates near midnight.
**No gap.** The real improvement is the already-recorded backlog item: per-photo timezone from
GPS. `OffsetTimeOriginal` (EXIF 2.31) would let a modern file date itself exactly, and is a
cheap addition to the same `REQUESTED_TAGS` change as (a).

**(d) Video containers.** We read `CreateDate`, `MediaCreateDate`, `TrackCreateDate` and prefer
`CreationDate`. The metadata-chain research already established exiftool dates every datable
file in a 22-format corpus and that no fallback parser recovered a date it missed.
**No gap**, and the sentinel guard is what makes this safe where naive parsers report 1904.

## 5. Summary

| Candidate | Verdict |
|---|---|
| File mtime fallback | **Never.** The others' most-reported bug; already forbidden by §1 |
| EXIF `ModifyDate` | **Never.** Edit time, and most present exactly when it is most wrong |
| XMP `DateTimeOriginal`/`CreateDate` | **Add**, after embedded EXIF, before Takeout — corpus probe first |
| `OffsetTimeOriginal` | **Add** alongside XMP; makes modern files exactly datable |
| `GPSDateStamp` | Not a tier — a **cross-check** for suspect dates; feed into `(ii)` |
| Video container tags | Already complete |

**One structural observation.** PhotoPrism stores a `TakenSrc` field naming which source supplied
the date. We resolve the same information (`DateSource`) and then discard it at write time. Items
`(n)` and `(ii)` both need it persisted — this survey is a third argument for that same column,
and it is the cheapest of the three to justify.

**Complexity:** every recommendation here is additional *tags requested in the existing exiftool
batch*, not additional passes. `REQUESTED_TAGS` grows by a handful of names; the read stays one
batched invocation per chunk, so cost is unchanged in the number of files and unchanged in I/O.
Nothing proposed is worse than linear.


---

## 6. Corpus probe (2026-07-28) — the XMP recommendation is withdrawn

§4(a) recommended adding an XMP tier "pending a corpus probe", per the fallback-parser policy
that a tier is added only when a real corpus shows a file it — and only it — can correctly date.

**Probed: 400 files from the real library.**

| | |
|---|---|
| files read | 400 |
| with `DateTimeOriginal` | 398 |
| with **any** XMP date | **0** |
| that would **gain** a date from XMP | **0** |
| with `ModifyDate` but no `DateTimeOriginal` | 2 (of 2 such files — **100%**) |

**Recommendation withdrawn. Do not add the XMP tier.** Not one file in the library carries an
XMP date, so the tier would add two tag names, a branch and a test for zero files. It stays
available if a future corpus — an Adobe-heavy or sidecar-RAW library — shows otherwise; the
policy is unchanged, the evidence simply came back negative. **A null result is a result**, and
recording it stops the same recommendation being re-derived from first principles later.

**The same probe strengthened the `ModifyDate` refusal into a measurement.** Both files lacking
`DateTimeOriginal` carried a `ModifyDate` — the exact population §3 predicted, at 100% of the
sample. That refusal is now a named constant with a guard test rather than an absence.

`GPSDateStamp` is unchanged: a cross-check for dead-clock dates, never a tier.
