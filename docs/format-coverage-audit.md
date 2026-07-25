# Format Coverage Audit - Phase 1 (recon + research)

Status: **Implemented (Phase 2).** Added `pillow-heif` (graceful-degradation guarded) so
HEIC/HEIF get perceptual dedup, and the full list-only extension set (`.hif` + JPEG aliases + the
mainstream RAW family). Legacy video remains backlog item (l); RAW+JPEG pairing remains deferred.

**Correction found during Phase 2 (good news):** the Phase-1 claim "all RAW → perceptual `None`"
was **too pessimistic**. It was based on Pillow's *extension* registry, but `Image.open()`
content-sniffs by magic bytes - so **TIFF-based RAW (CR2, NEF, DNG, ARW, ORF, RW2, PEF, SRW, …)
opens via Pillow's TIFF decoder and perceptual-hashes with no extra dependency.** Only
container-based RAW (CR3, RAF) falls back to exact-only. Verified on real corpus files below.

**End-to-end verification (real corpus HEIC + RAW, this machine):**

| File | vaeon date | category | perceptual (before → after pillow-heif) |
| --- | --- | --- | --- |
| `shelf-christmas-decoration.heic` (Samsung) | `2023-12-13` (EXIF) | Camera | `None` → real hash |
| `childrens-show-theater.heic` (Apple iPad) | `2022-11-08` (EXIF) | Camera | `None` → real hash |
| `heic-icon-128x128.heic` (no EXIF) | Undated | Saved | `None` → real hash |
| `cr2-sample-file.cr2` (Canon 6D) | `2016-10-06` (EXIF) | Camera | **real hash already** (TIFF sniff) |
| `sample-nef-files-sample1.nef` (Nikon D3) | `2008-03-15` (EXIF) | Camera | **real hash already** |
| `sample-dng-files-sample1.dng` (Canon 350D) | `2008-12-14` (EXIF) | Camera | **real hash already** |

**Headline:** vaeon's *recognition* is already strong - HEIC/HEIF, AVIF, and the mainstream RAW
family are all on the list. The real findings are two, and neither is "we forgot a common
format":

1. **A depth gap, not a breadth gap.** HEIC/HEIF and every RAW format are recognized, dated
   (exiftool), and **exact-deduped** (SHA-256) - but I verified empirically that **Pillow 12.3
   cannot open HEIC/HEIF or any RAW**, so their **perceptual (near-duplicate) hash is silently
   `None`**. For the iPhone-default format since 2017, near-dup detection is effectively off.
   Fixing it means one dependency, **`pillow-heif`** (the sole "needs-dep" decision in this audit).
2. **Small breadth gaps.** Exactly one standard-image extension is missing (`.hif`, the HEIF
   variant); a set of mainstream **RAW** extensions the benchmark lists are absent (`.pef .crw
   .nrw .x3f …`) but are **zero-cost list-only** adds; and the **legacy video** set is the
   corpus-proven backlog item (l).

---

## Phase 1a - Recon (code truth)

### The current recognized list (`organizer.py:47-95`)

- **Images (21):** `.jpg .jpeg .png .gif .bmp .webp .tif .tiff .heic .heif .avif` · RAW: `.dng
  .raw .cr2 .cr3 .nef .arw .orf .rw2 .raf .srw`
- **Video (14):** `.mp4 .mov .m4v .3gp .3g2 .avi .mkv .webm .mpg .mpeg .wmv .flv .mts .m2ts`
- **Audio (7):** `.m4a .aac .opus .ogg .mp3 .wav .amr` (vaeon-specific - messenger voice notes;
  not part of the photo-manager benchmark)

### Where recognition gates - one hard gate, one soft dependency

| Stage | Format-sensitivity | Evidence |
| --- | --- | --- |
| **Discovery** | **The only hard gate.** Extension ∈ `MEDIA_EXTENSIONS` → organized; else skipped (now *reported*, per `scan_source`). | `organizer.py:164` |
| **Categorization** | **Format-agnostic.** Rules key off EXIF tags (`Make`/`Model`, `SamsungCaptureInfo`) and filename conventions - never the extension. | `categorize.py` (rule chain; no `suffix` checks) |
| **Dating** | **Format-agnostic.** Purely exiftool-tag driven (`DATE_TAGS`) + filename; no MIME/extension branch. | `dates.py:107` (`resolve_capture_datetime`) |
| **Exact dedup** | **Format-agnostic.** SHA-256 of bytes; always works. | `hashing.py:42` |
| **Perceptual dedup** | **Format-DEPENDENT.** `Image.open()` via Pillow; on failure returns `None` (caught silently). | `hashing.py:51-63` - `except (UnidentifiedImageError, OSError, ValueError): return None` |

So a format added to `MEDIA_EXTENSIONS` immediately gets discovery + categorization + dating +
exact-dedup **for free** (all format-agnostic). The *only* thing gated on the actual pixel
decoder is perceptual near-dup detection.

### Empirical: what Pillow 12.3 actually opens (measured, this machine)

| Openable by Pillow (perceptual works) | NOT openable (perceptual → `None`) |
| --- | --- |
| `.jpg .png .gif .bmp .webp .tif` - **and `.avif`** (native in Pillow 12) | **`.heic` `.heif`** · RAW by *extension* registry |

> **Corrected in Phase 2:** this table used Pillow's *extension registry*, which is the wrong
> signal - `Image.open()` sniffs magic bytes, so **TIFF-based RAW (CR2/NEF/DNG/ARW/ORF/RW2/PEF/SRW)
> does open** and perceptual-hashes with no plugin. Only HEIC/HEIF (needs pillow-heif) and
> container-based RAW (CR3, RAF) return `None`. See the correction + verification at the top.

`perceptual_hash` swallows the failure (`hashing.py:62`) and `scan.py` "attempts it for every
file and simply returns `None` for non-images" - so this degrades **silently**: HEIC and RAW are
organized and exact-deduped, but two visually-identical-but-recompressed HEICs are never flagged
as near-duplicates. **No `pillow-heif` or `rawpy` dependency is present** (grep-confirmed).

---

## Phase 1b - Research (benchmark: Immich ∪ PhotoPrism)

Sources: Immich `server/src/utils/mime-types.ts` (authoritative; the docs page is abbreviated) +
[docs](https://docs.immich.app/features/supported-formats); PhotoPrism
[media dev-guide](https://docs.photoprism.app/developer-guide/media/) / `photoprism show
file-formats`. Confirmed claims: **HEIC = iPhone default since iOS 11 (Sept 2017)**; **exiftool
reads dates from HEIC + all major RAW**; **Pillow needs `pillow-heif` (libheif) for HEIC and
`rawpy`/LibRaw for RAW** - RAW files carry an embedded JPEG preview `rawpy.extract_thumb()` can
pull that Pillow can then read.

### Tiered gap table (benchmark has it, vaeon does not)

| Tier | Gap | In benchmark | vaeon cost |
| --- | --- | --- | --- |
| **T1** standard | `.hif` (HEIF variant, Canon/Fuji) | both | **list-only** (dating+exact); perceptual needs `pillow-heif` like HEIC |
| **T1** *depth* | HEIC/HEIF perceptual dedup (already recognized) | first-class in both | **needs-dep** (`pillow-heif`) |
| T1.5 | `.jxl` (JPEG XL - iOS 17+), `.jpe .jfif` (JPEG aliases) | both | JPEG aliases **list-only, fully supported**; `.jxl` list-only for dating, perceptual needs a JXL plugin |
| **T2** RAW | `.pef .crw .nrw .sr2 .srf .rwl .3fr .fff .cap .iiq .erf .mrw .dcr .kdc .x3f .ari` | both | **list-only, zero cost** - exiftool dates them; RAW perceptual is already N/A, so no dep, no regression |
| T2 tail | `.gpr .mos .mef .r3d .bay` | PhotoPrism only | list-only; lower prevalence |
| **T3** legacy video | `.vob .ts .m2t .asf .f4v .mxf .ogv .dv .mjpeg .mjpg` | both (mixed) | **list-only, zero cost** - video is exact-hash only. = backlog item (l) |
| - | `.rm` `.wtv` | **neither** benchmark | not recommended (corpus samples only; niche) |
| - | `.psd .svg .thm .apng .mpo`, codec-named `.hevc/.h264/.m2v` | mixed | not "photos to back up" / elementary streams - **exclude** |

**Key reframing vs the task's tiers:** the T1 breadth list (HEIC/HEIF, webp, png, gif, mkv, m4v,
webm) is **already fully recognized** - the only literal T1 extension gap is `.hif`. The T1
*substance* is the HEIC **perceptual** depth gap. T2 RAW is almost entirely list-only additions.
T3 is item (l).

---

## Per-gap cost & recommended v1 inclusion

### List-only (add to `MEDIA_EXTENSIONS`; free dating + exact-dedup) - **recommend for v1**

- **`.hif`** - HEIF variant; closes the one literal T1 image gap.
- **JPEG aliases `.jpe`, `.jfif`** - Pillow opens them as JPEG → *full* support incl. perceptual.
- **Mainstream RAW the benchmark lists:** `.pef .crw .nrw .sr2 .srf .rwl .3fr .fff .cap .iiq .erf
  .mrw .dcr .kdc .x3f .ari` (+ optionally `.gpr`). Zero cost - RAW perceptual is already N/A for
  the RAW vaeon *already* lists, so this adds no dependency and no regression, and closes the
  photographer-audience gap in one stroke.

### Needs-dep - **the one real decision: `pillow-heif`**

Adding `pillow-heif` (a maintained libheif binding; prebuilt wheels for Windows/macOS/Linux incl.
arm64) registers a HEIF opener so `Image.open()` handles `.heic/.heif/.hif`, which makes their
**perceptual near-dup dedup actually work**. **Written justification:** HEIC has been the iPhone
default capture format since 2017 - for a large share of a modern user's library, vaeon currently
recognizes and dates the file but cannot detect that an edited/re-saved/shared-and-recompressed
copy is a near-duplicate (exact-dup still works). That is a launch-quality gap for the single most
common phone-photo format, and one small dependency closes it. Both benchmark tools treat HEIC as
first-class via libheif - this is table stakes, not a nice-to-have.
*Alternative if declined:* ship HEIC as-is (recognized, dated, exact-deduped) and document the
perceptual limitation - acceptable for a backup tool, but a visible quality gap.

### Needs-work - **defer, note explicitly**

- **RAW perceptual dedup for container-based RAW only** (CR3, RAF - not TIFF-based, so Pillow
  can't open them). Would need `rawpy.extract_thumb()` (embedded JPEG preview). Deferred:
  TIFF-based RAW already perceptual-hashes for free (see the correction at the top), CR3/RAF
  near-dups are rare, and `rawpy`/LibRaw is a heavier native dependency. Exact-dedup covers
  byte-identical RAW of every kind.
- **RAW+JPEG pair handling** (`IMG_1234.CR2` + `IMG_1234.JPG` of the same shot). A real
  photographer expectation - **PhotoPrism stacks them natively** (same folder+basename, JPEG
  primary); Immich does it partially / via external tooling. vaeon today treats them as two
  distinct files (different SHA, different/absent perceptual) → **both kept, neither paired**.
  For a *backup* tool "keep both" is defensible, but adding the RAW extensions above makes this
  more visible. Recommend: **note as a known limitation now**; if built, key pairs on
  `(folder, basename)` and prefer the JPEG as display/hash target, RAW as retained master.

### Not recommended for v1

`.rm .wtv` (neither benchmark; corpus-sample only), `.psd .svg .thm .apng .mpo` (not
back-up-a-photo formats), codec-named elementary streams (`.hevc .h264 .m2v` - rarely real files).
`.jxl` - recognize as list-only if desired (emerging on iOS 17+), perceptual deferred.

---

## Recommended v1 list, concretely

1. **Images, list-only:** add `.hif .jpe .jfif` and RAW `.pef .crw .nrw .sr2 .srf .rwl .3fr .fff
   .cap .iiq .erf .mrw .dcr .kdc .x3f .ari .gpr`.
2. **Dependency:** add **`pillow-heif`** and register the HEIF opener so HEIC/HEIF/.hif get
   perceptual dedup (the one justified new dep; update the dependency inventory in
   `IMPLEMENTATION_STANDARDS.md §7`).
3. **Legacy video (item l):** fold `.vob .ts .asf .f4v .ogv .dv .mjpeg` into the demand-driven
   backlog item - zero-cost list adds, not launch-blocking.
4. **Document limitations:** RAW has no perceptual dedup (exact only) until `rawpy` is justified;
   RAW+JPEG pairs are kept separately (not stacked).

**Verification note:** the corpus contains **no HEIC or RAW files**, so per-format dating could
not be tested empirically here - the "exiftool dates HEIC/RAW" claim rests on exiftool's
documented format support (400+ formats incl. HEIC/CR2/CR3/NEF/ARW/DNG). Adding a couple of real
HEIC + RAW files to the corpus would let a follow-up probe confirm end-to-end before shipping.

**Stopping here for approval** on the recommended v1 list and, specifically, the `pillow-heif`
dependency.
