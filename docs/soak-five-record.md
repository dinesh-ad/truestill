# Soak five: the whole library, every feature - a record

**Ran 2026-08-25 (P95).** Machine: 16 cores / 30 GiB. Filesystem: **ext4** throughout
(`/data`, 742 G free). ⚠ `~/TruestillLibrary` is a **symlink** to `/data/TruestillLibrary` - one
library, two names, which matters to anything that resolves paths.

**Why it existed**: almost every defect this month was found by *reading code* and reproduced on a
fixture built for that defect. The library had been where scratch lives, not the thing under test,
and 3,190 passing tests make that easy not to notice. This ran the **product**.

⚠ **THIS IS HALF A SOAK, AND THE HALF IS NAMED BELOW.** Recording a partial soak as complete is
the worst outcome available here.

---

## The corpus, re-derived (nothing carried from the 2026-08-23 snapshot)

**20,237 files / 31 GB / 354 directories.** Two populations:

| | files | bytes |
|---|---|---|
| real material | **9,363** | ~25.6 GB |
| `metadata-extractor-images` + `exif-samples`, **copied into `Input/`** | **10,874** | 5.4 GB |

The planted archive is at the library root, not inside `Input/`:
`Photos-1-001_08_12_2021.zip`, **1.61 GB, 534 entries** - and `Input/Photos-1-001_08_12_2021/`
already holds exactly those 534 files.

**The gate accepts 10,768 (53.2%)**, skips 7,696 documents, and does not recognise **1,773 files
across 32 extensions**.

## ⚠ The gate is 65 extensions, not 62

Re-derived from `organizer.py`: **44 image + 14 video + 7 audio = 65**.
[`format-coverage-audit.md`](format-coverage-audit.md) says *"62-extension gate"* in its §0 scope
line. **That document is a record and is not edited**; this is the dated correction beside it.

**Real image formats present in the corpus that the gate does not recognise**, and the audit
**never considered** - `grep` returns **zero** mentions of each in it:

`.pcx` (57) · `.ico` (57) · `.tga` (26) · `.eps` (24) · `.jxr` (17) · `.ppm`/`.pnm`/`.pgm`/`.pbm`
(2 each) · plus **37 files with no extension**.

`.psd` (5) is different: the audit **explicitly excludes** it at `format-coverage-audit.md:198`
and `:248` - *"not 'photos to back up'"* - so it is ruled, not missed. **The other seven are
neither in the gate nor in the audit's exclusions**, which is a gap in the audit's coverage rather
than a decision anyone made.

---

## The headline: the baseline held

`scripts/golden_corpus.py check` - **79.2 s over 10,745 media files**:

> **The only drift is 2,955 files added. Zero decisions changed.**

Every file in the 2026-08-23 snapshot resolves to the same date, source, tag and placement after
this month's commits.

**And the invariant that matters more**: `Input/` is **byte-for-byte unchanged** - a size + mtime
manifest of all 20,237 files, identical before and after organize preview **and apply**, verify,
rescan, clean-empty, events and ingest. Both format repos remained git-clean;
`scratch-race-2026-08-22` (4,226 files) and `abs-repro-2026-08-23` untouched.

## What ran

| feature | result |
|---|---|
| organize preview | 105.6 s, 2.19 GB RSS - 10,745 analysed, **9,875 unique, 827 near-dup, 35 exact dup, 8 unreadable** |
| organize apply | **89.6 s**, 10,712 files / 28 GB written. Sources: exif 9,407 · **none 1,254** · inferred_local 20 · filename 18 · **rejected_future 3** |
| verify | 35 s - **10,710 verified; 0 missing, 0 mismatch, 0 unreadable, 0 unverifiable** |
| rescan | 10,710 in place; 0 stray, unaccounted or debris |
| clean-empty · status · drives · where | clean; the sentences they printed were true |
| events | **214 clusters** over 169 start-days |
| **ingest (archive)** | ⚠ **crashed** - `(ahp)` |

## Findings filed

* **`(ahp)`** - `truestill ingest --source <archive>` crashes on **every** archive, reproduced with
  a 77 KB two-file zip. Ranked first: shipped, unconditional, on the feature's own documented
  invocation.
* **`(ahq)`** - **89 files** within threshold 5 of the all-zero perceptual hash, **10 of them real
  photographs**, mutually near-duplicate by construction.

## ⚠ A finding I reported in P95 and withdraw here

P95 said event clustering showed "both failure modes" - days split, spans merged. **It does not.**
Checked against the shipped constants rather than against intuition:

| observation | measured | verdict |
|---|---|---|
| 2014-08-16 splits at 15:18, resumes 16:46 | boundary gap **1.45 h** | above `MIN_BOUNDARY_GAP_S` (**1 h**) - the floor permits it and it beat the local median. **By design** |
| one cluster spans 2019-11-23 → 12-05, 30 files | largest internal gap **43.9 h** | under `MAX_WITHIN_EVENT_GAP_S` (**48 h**). **By design** |

[`events-clustering-research.md`](events-clustering-research.md) is **"Built (2026-07-28)"** and
both constants shipped from it. Its §1 already predicted the shape - *"sparse data never splits;
dense data always does"* - and records a 5.6-year, 11-photo event as the defect those two bounds
were added to kill. So this is a **premise-check that confirms a recorded decision at full scale**,
not a new finding. 29 days split across more than one cluster; that is the rule working.

## A null, checked rather than assumed

**1,254 files resolve to no date.** Six real ones are `IMG-YYYYMMDD-WA####.jpg`, and
`date_from_filename` reads them correctly while `_filename_capture_date` returns `None`. That is
**deliberate**: its docstring refuses messenger conventions because the name carries the day
WhatsApp *delivered* the file, citing `IMPLEMENTATION_STANDARDS.md` §1. `exiftool` finds no
embedded date either - only `FileModifyDate`. **Correct behaviour**, and it was one read away from
being filed as a defect.

## ⚠ My own instrument was wrong first, for the third time this month

The first `Input` comparison reported **INPUT CHANGED** on all 20,237 rows. The cause was **my
manifests**: one built with `find Input` and the other with `find /data/TruestillLibrary/Input`, so
every path differed by a prefix. Re-run with matching roots, the files are identical.

**This is the third instrument defect in a month** - after the `/tmp`-is-tmpfs measurements that
mislabelled four findings, and the 20-vs-34 delta that compared two different surface sets. The
pattern is worth the line: **when a measurement says something alarming at scale, suspect the
instrument before the product.** All three were caught by re-deriving rather than by reasoning
about the result.

## ⚠ What was NOT run - the missing half

**backup · undo-organize · migrate-layout · the dates rescue flow · trips** (app-only, no CLI
surface) · **reclaim** (my invocation was wrong - a missing required argument, so its exit 2 was
mine and not the product's; the same for `analyze`, which does not take `--db`).

The browser lane was not run: no change was made, so §6.1's condition was not met.

**So: the read paths and the organize/verify/rescan write path are soaked. The reversal paths - the
ones that move a user's files back - are not.** That is the next soak, and it is the half where a
defect costs the most.
