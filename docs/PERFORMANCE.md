# Performance

The measured baseline of the pipeline, the two known scaling limits, and the things a future
optimizer should leave alone.

Numbers here are **measurements, not projections**, unless a cell says otherwise. A projection
is labelled as one. This document exists so that "is this fast enough?" is answered by a
recorded number rather than by an opinion, and so that the next person to reach for an
optimisation can see which ones have already been considered and rejected.

**Measured on:** AMD Ryzen 7 4800H (16 threads), Linux, Python 3.13, exiftool 13.50, SSD.
Corpus as stated per row. Re-measure before citing any of this on other hardware.

---

## 1. Baseline - cost per stage

Complexity is stated in *n*, the number of files. Timings are at **2,275 files**; the 100k
column projects from measured per-file cost, or from measured growth for the super-linear one.

| Stage | Complexity in n | 2,275 measured | %share | → 100k |
|---|---|---|---|---|
| scan / discover | **O(n)**- one `rglob`, one stat each | 0.042 s | 0.5% | ~1.8 s |
| exiftool read | **O(n)**, batched 200/process | 6.16 s | 74.5% | ~4–7 min |
| hashing | **O(total bytes)**, parallel, size pre-filtered | 1.93 s† | 23.3% | ~14 min cold, ~0 cached |
| exact dedup | **O(1)/file**- dict on sha256 | in above |- | flat |
| perceptual dedup | **O(n²)**- linear scan per file | 0.72 s |- | ≈ 22.6 min ⚠ see §3 |
| categorize | **O(n)**- 6 ordered rules, first match | 0.030 s | 0.4% | ~1.3 s |
| date-resolve | **O(n)**- ≤5 tag lookups + 3 regexes | 0.030 s | 0.4% | ~1.3 s |
| naming | **O(n)** | <0.001 s | 0.0% | <0.1 s |
| layout / render | **O(n)**- token substitution | 0.009 s | 0.1% | ~0.4 s |
| execute / copy | **O(total bytes)** | 0.073 s† | 0.9% | I/O-bound |
| metadata write (Takeout) | **O(n)**, batched 100/process | 9.3 ms/file |- | ~15.6 min |
| event clustering | **O(n log n)**- one sort, three linear passes | 0.004 s | 0.0% | ~0.2 s |
| verify | **O(total bytes)**- re-reads by design |- |- | I/O-bound |
| reclaim planning | **O(n)** + a full re-hash per candidate | 474 ms (query @ 100k) |- | <1 s query |
| catalog queries | **O(n)**, all indexed or inherently full-table | 17–474 ms @ 100k |- | see §4 |

† small fixtures (~8 KB). **File size flips the ranking**: at realistic 12 MP (11.6 MB),
exiftool reads cost 2.2 ms/file against 8.2 ms/file for hashing, which makes hashing ~79% of a
cold preview. Both orderings are real; which dominates depends on the library.

> **Provenance of this table: unrepeated, and marked as such (audited 2026-07-31).** No row above
> records a run count, and nothing in the repository reproduces them - `scripts/profile_organize_
> preview.py` is by its own description "one instrumented pipeline pass", i.e. n = 1. They are
> therefore **single samples**: still the best evidence we have for those stages, and directly
> responsible for two decisions that have held up (D4's batching, D8's no-BLAKE3), but not taken
> to the §2.1 standard and not to be quoted as if they were. The one table it was cheap to re-take
> has been re-taken (§3, which reproduced). Re-measuring the rest means re-running a full pipeline
> pass per sample and is worth doing the next time any of it is touched, not as make-work now.
> **Rows below this line in §1.1 and §3 carry an n; rows in this table do not. That is the
> difference, and it is deliberate rather than an oversight.**

### 1.1 Stages added after the 2026-07 baseline (measured 2026-07-31)

The table above predates seven stages. This is those stages, taken to the §2.1 method: median
and p95 over n runs, corpus and machine class named on every row. **Local SSD throughout, except
the two attach rows: the FUSE column was empty in the 2026-07-31 pass because the mount was
absent, not because it is fast, and it was measured for attach on 2026-07-31 once the mount was
back.**

| Stage | Corpus | n | median | p95 | spread | FUSE |
|---|---|---|---|---|---|---|
| catalog startup (`inspect_catalog`) | Output, 2,300-row catalog | 11 | **2.2 ms** | 2.4 ms | 1.19x | not measured |
| trip detection (`detect_trips`) | Output, 2,224 items -> 15 clusters | 11 | **0.31 ms** | 0.39 ms | 1.26x | not measured |
| trip review (`assemble_trip_review`) | Output, 2,224 rows -> 5 cards | 9 | **6.8 ms** | 9.1 ms | 1.34x | not measured |
| migration plan (`plan_migration` alone) | Output, 2,224 moves planned | 5 | **82 ms** | 84 ms | 1.03x | not measured |
| migration preview, **cold-cache** | Output, 2,224 files | 5 | **12.27 s** | 12.36 s | 1.01x | not measured |
| migration preview, **warm-cache** | Output, 2,224 files | 5 | **0.168 s** | 0.169 s | 1.02x | not measured |
| ~~migration preview, before F18~~ | Output, 2,224 files | 5 | ~~12.25 s~~ | ~~12.29 s~~ | ~~1.01x~~ | not measured |
| migration apply (`run_migration`) | hermetic, 500 files | 5 | **169 ms** | 172 ms | 1.02x | not measured |
| migration undo (`undo_migration`) | hermetic, 500 files | 5 | **154 ms** | 155 ms | 1.01x | not measured |
| cleanup plan + run | hermetic, 500-file skeleton | 5 | **11 ms** | 11 ms | 1.04x | not measured |
| undo plan (`plan_undo`) | hermetic, 500 files | 9 | **8.6 ms** | 9.2 ms | 1.08x | not measured |
| undo apply (`run_undo`) | hermetic, 500 files | 5 | **81 ms** | 82 ms | 1.01x | not measured |
| attach, **steady state** (drive already attached) | 2,269 copies, 6.2 GB | 5 | **0.098 s** | 0.106 s | 1.09x | **6.297 s** / p95 6.548 s / 1.09x |
| attach, **re-attach**, cold-cache | 2,269 copies, 6.2 GB | 5 | **6.302 s** | 8.387 s | 1.34x | **22.248 s** / p95 22.347 s / 1.03x |
| attach, **re-attach**, warm-cache | 2,269 copies, 6.2 GB | 5 | **0.350 s** | 0.354 s | 1.02x | **1.091 s** / p95 1.113 s / 1.09x |
| ~~attach by remembered path, cold~~ | 2,269 copies, 6.2 GB | 5 | ~~8.885 s~~ | ~~14.30 s~~ | ~~1.96x~~ | ~~15.92 s~~ |
| ~~attach by remembered path, warm~~ | 2,269 copies, 6.2 GB | 5 | ~~0.316 s~~ | ~~0.339 s~~ | ~~1.15x~~ | ~~0.282 s~~ |

**Cold/warm, per stage, rather than a duplicated column.** Only one of these stages touches
exiftool, so only one has a cold/warm axis at all: **migration preview**. The other nine are
catalog reads, in-memory computation, or renames, and repeating them changes nothing but the OS
page cache - there is no second number to report, and inventing one would imply a cache that is
not there.

> **The migration preview row was the finding, and its *lack* of variance is what found it.**
> Before the fix, five runs over the same 2,224 files: 12.27, 12.21, 12.22, 12.28, 12.25 s.
> **Spread 1.01x - the second pass was not one percent faster than the first.** §8 says a warm
> second read "must make **zero** exiftool subprocess calls", and this path was exempt:
> `migrate.rederive_rules` called `read_metadata` with **no `HashCache`**, so every preview of
> the same drive paid full exiftool cost again, forever. Planning itself is 82 ms; the other
> **12.2 s was re-derivation nobody cached.** A single run would have read "12 s, a bit slow";
> five runs showed it was *structurally* uncached, which is the whole argument for n >= 5.
>
> **Fixed 2026-07-31 (audit F18).** Cold is unchanged at 12.27 s - a cold cache must still pay
> full price - and **warm is 0.168 s, a 73.2x reduction**, with **zero exiftool subprocess
> calls across five warm runs**, counted the same way `test_warm_second_read_makes_zero_exiftool_
> calls` counts them. §8's warm-read guarantee now covers this path; it did not before. Both §5
> preview-purity guards still pass unchanged, because the sidecar is neither the drive nor the
> catalog and `service.organize_preview` had always written it on a preview.

> **Attach reads the drive on purpose, and this is the price.** It used to record
> `files.copy_sha256` -- a *per-content* value -- onto a *per-drive* row, which is sound only
> while every copy of a file is byte-identical to every other. The Takeout bake already breaks
> that, so the inherited value would have made `verify` compare a baked copy against a pre-bake
> hash and **report corruption on a file truestill itself wrote**. Attach now identifies each
> file by hashing it. The trade is a one-off read against a class of false corruption alarm.
>
> **Three states, because they cost different amounts and only one is common.** *Steady state* -
> the drive is already attached - reads nothing it has a record of and costs **0.098 s** locally:
> a walk and a stat per file. *Re-attach*, where the drive's copy rows are gone and every file
> must be identified, costs **6.302 s local / 22.248 s FUSE** once, and **0.350 s / 1.091 s**
> warm, because the hash cache answers the second pass.
>
> **The FUSE steady-state figure is the price of files truestill does not know about.** That
> drive holds **399 files with no catalog row** - they are hashed on every attach, because
> "unknown" cannot be established without reading them, and that is the whole of its 6.297 s.
> The local drive has none, hence 0.098 s. So the steady-state cost scales with *unrecognised*
> files, not with library size, and it is counted and reported (`unmatched`) rather than ignored.
>
> **Corpus:** the Output drive (local SSD) and The Memory Cabinet (cloud FUSE) - the same 2,269
> copies, 6.2 GB, organized from the same source. Measured against a **scratch copy** of the real
> catalog, restored before every run outside the stopwatch; the drives themselves are only read,
> and both already carry markers so nothing was written to them.
>
> **Limits, stated rather than smoothed over.** FUSE cold is **3.5x** local, not the 13x
> `preview-performance-profile.md` measured, because the mount's own local cache was populated
> for these files - **a genuinely cold cloud fetch is not measured and would be slower.** The
> local re-attach spread is **1.34x**, the widest of these rows. Warm still reads no file bytes,
> which is why the machine class nearly stops mattering.
>
> **Correction (2026-07-31): an earlier version of this note overstated the bug it describes.**
> It said attach "finds nothing and reports every file absent" on a migrated library. Measured,
> that was wrong in severity. On the live catalog `files.relative` is stale - **0 of 2,300** of
> those paths exist on the drive, because `migrate-layout` rewrites `file_copies.relative` and
> nothing ever updates the per-content column - but a fully attached drive answers from its
> recorded copies first, so it reported **linked=0, absent=31**, and all 31 were genuinely gone.
> The damage landed on **re-attach**, the disaster-recovery path: **linked=0, absent=2,300 on a
> drive physically holding 2,269 of those files.** Attach was correct exactly while it had
> nothing to do and failed completely when it did. Fixed by matching on content; the two struck
> rows above are the old path-based figures, kept because they are what the fix is measured
> against.

**Why the destructive four are fixtures, not Output.** Migration apply, migration undo, undo and
cleanup all rearrange or delete. They are measured on a hermetic 500-file drive with real files
and real catalog rows, restored from a pristine copy before every run **outside** the stopwatch.
Per-file they are 0.34 / 0.31 / 0.02 / 0.16 ms, all rename-and-journal work with no hashing, so
they scale linearly and cheaply; the honest limit is that 500 files is a fixture, not a library,
and a 100k projection from it would be arithmetic rather than measurement.

### Fixed in the 2026-07 pass

Two stages in that table used to be the two worst things in the pipeline.

| Fix | Before | After | At 100k |
|---|---|---|---|
| Metadata write batched (`exif.write_metadata_batch`) | 254.9 ms/file | 9.3 ms/file | 7.1 h → **15.6 min** |
| Custody count (`Catalog.single_copy_count`) | 224 ms | 17.5 ms | per refresh, **13× cheaper** |

The metadata-write figure is measured over 1,203 real JPEGs, staging copy included in both
columns - that is why it is 9.3 ms rather than the 5.2 ms of the bake alone. The write path
had been spawning one exiftool process per file, and process startup, not work, was ~98% of it.

**The known next rung on the metadata write, deliberately not built.** exiftool's persistent
`-stay_open True -@ -` mode was measured against the argfile batch and is **1.12× faster**-
on top of a 27× win already banked. That 12% costs a persistent child process, a reader
thread, timeout handling and a mid-batch-death lifecycle, on the one path that modifies bytes
the user keeps. It is the correct escalation *if the batch ever becomes the bottleneck again*,
and it gets built when a measurement says so - not before. Full rationale: `DECISIONS.md` D4.

Also recorded: the **hash cache** (`hash_cache.py`) took a repeat preview of 2,275 unchanged
files from 15.8 s to 4.7 s by never reading an unchanged file twice.

---

## 2. The rule

> **Every new pipeline stage states its complexity in *n*, in its module docstring. A stage
> worse than O(n log n) must say so explicitly and justify why the simpler thing is the right
> trade at the scale we serve.** New stages get a row in §1 - measured, not asserted.

This is a quality gate, referenced from
[`IMPLEMENTATION_STANDARDS.md`](IMPLEMENTATION_STANDARDS.md) §6. The point is not to forbid
quadratic code; `DedupIndex` is quadratic on purpose (§3). The point is that it must be a
decision on the record rather than an accident nobody priced.

### 2.1 How a number gets into this document (binding method)

These figures are quoted in decisions and outlive the person who took them, so how they were
taken is part of the claim. Every row added from 2026-07-31 follows all of this, and a row that
cannot is written as a **"not measured, because X"** row rather than filled in with a guess.

| Rule | Why |
|---|---|
| **`time.perf_counter()` around the stage only**, never around its setup. | Restoring a fixture is not the stage. Timing it inflates the row and hides the thing being measured. |
| **n >= 5 always; n >= 9 where a run is cheap.** | One run is an anecdote. It cannot tell a 12 s stage from a 12 s stage that should have been 0.1 s warm - see the migration preview row, where the *absence* of variance is the entire finding. |
| **Report median and p95, never a mean.** | A mean is dragged by one scheduler hiccup. Below n = 20, p95 is reported as the observed **maximum** and means exactly that - no interpolation, which would invent resolution the sample size does not have. |
| **Report the spread (max/min).** | The number that says whether to trust the median at all. |
| **Cold and warm are separate rows, never averaged.** | The metadata cache is ~170x. An average of cold and warm describes a run that never happens. Label them cold-cache / warm-cache, never run 1 / run 2. |
| **State the corpus and its size on every row.** | "0.08 s" is meaningless without "over 2,224 rows". |
| **State the machine class:** local SSD or cloud FUSE. | `preview-performance-profile.md` measured **13x** between them. A row without it cannot be compared to anything. |
| **Corpus fence holds** (`PROJECT_STATUS.md` §4): The Memory Cabinet, Output, or a hermetic fixture. **Never `Crypto Folder/`.** | Not a performance rule, but it binds this document like every other. |
| **A destructive stage is measured on a hermetic fixture**, restored between runs outside the stopwatch. | A benchmark must never be the thing that rearranges someone's library. This is why apply/undo/cleanup below are fixtures and not Output. |

**Two limits that apply to every local-SSD row here, stated once.** The OS page cache cannot be
dropped without root, so these are **page-cache-warm** figures; a genuinely cold-disk read is
not measured and would be slower. And the cloud FUSE class is **not measured at all** in this
pass, because the mount was absent when the numbers were taken - see the empty column in §1.1
rather than an interpolation from the local figures.

---

## 3. Known limit: perceptual dedup is O(n²)

`DedupIndex.check` compares each incoming file against every known perceptual hash. The cost
per comparison is already optimal - a 64-bit XOR and a CPU popcount, ~271 ns including loop
overhead - so what grows is the *number* of comparisons, not their price.

**Re-measured 2026-07-31 to the §2.1 method.** The original figures carried no run count - like
every row written before that method existed - so they were re-taken rather than left as a
weaker number beside stronger ones. They **reproduced**: the table was accurate, it was only its
provenance that was missing. Hermetic, synthetic 64-bit dHash-shaped values, local SSD.

| n images | total (median) | p95 | runs | per file | original figure |
|---|---|---|---|---|---|
| 1,000 | 0.134 s | 0.143 s | 9 | 0.134 ms | 0.14 s |
| 2,275 | 0.685 s | 0.694 s | 9 | 0.301 ms | 0.72 s |
| 5,000 | 3.363 s | 3.442 s | 9 | 0.673 ms | 3.39 s |
| 10,000 | 13.709 s | 13.873 s | 5 | 1.371 ms | 13.5 s |
| 20,000 | 55.460 s | 59.376 s | 5 | 2.773 ms | 54.3 s |
| 100,000 | ≈ 23 min (**projected**, never run) | - | 0 | 13.7 ms | ≈ 22.6 min |

Spread is 1.03x to 1.09x across every size: a CPU-bound comparison loop with nothing to vary.
That tightness is what makes the quadratic growth legible - each doubling of *n* is a clean 4x,
measured, not fitted. The 100,000 row is and always was an extrapolation and is now labelled as
one on its own row rather than in a footnote.

**It does not matter below ~10k images in one index, and it is intolerable above ~20k.** At
today's scale it is 0.7 s, and a BK-tree would be real machinery bought for a real 0.7 s. So it
has deliberately **not** been built.

**The alarm, so the trigger reaches whoever hits it.** `dedup.LINEAR_SCAN_ALARM` is 10,000: the
first index to cross it logs one line- *"perceptual matching is now the slow path … known,
planned"*- at the crossing itself. One integer comparison per registration, once per index.
A threshold that lives only in a document reaches people who read documents; this one reaches
the person with 10,000 photos.

**When it is due:** a BK-tree over Hamming distance is the literature-standard fit for a fixed
small threshold like `DEFAULT_PHASH_THRESHOLD`, and `DedupIndex`'s interface was designed for
the swap. A VP-tree is the more general metric-space answer and buys nothing extra here; LSH
suits *approximate* nearest-neighbour at far larger scale and would trade away exactness we
currently have.

---

### 3.1 Known limit: a HEIC costs ~50x a JPEG to perceptually hash, and the reason is fixable

Perceptual hashing works for HEIC/HEIF - `pillow-heif` is a declared dependency, its opener is
registered at import in `hashing.py`, and `HEIF_AVAILABLE` reports the degraded case. What was
not recorded until now is what it **costs**.

**The cause, which is the useful half.** `perceptual_hash` calls `image.draft("L", (64, 64))`
before hashing - a hint asking the decoder for a cheap, small, grayscale read, since a dHash only
ever needs 8x8. **`draft()` reaches JPEG and does nothing for HEIF.** Measured directly on one
4000x3000 image saved both ways:

| format | `draft("L", (64,64))` | result |
|---|---|---|
| JPEG | `(4000, 3000)` -> `(500, 375)` | **effective** - a DCT-scaled 1/8 decode |
| HEIC | `(4000, 3000)` -> `(4000, 3000)` | **no-op** - the full 12 MP frame is decoded, then thrown away |

So this is not "HEIF is a heavier codec" so much as **the existing optimisation does not reach
it**. That distinction is the whole reason to record this.

**Measured 2026-08-02**, to the §2.1 method (median and observed max over n runs, machine class
named). AMD Ryzen 7 4800H, Linux, Python 3.13, Pillow 12.3.0, pillow-heif 1.5.0.

| content | n | JPEG median | JPEG max | HEIC median | HEIC max | ratio |
|---|---|---|---|---|---|---|
| photo-like (smooth + mild texture) | 7 | **6.2 ms** | 6.6 ms | **319.5 ms** | 361.7 ms | **52x** |
| pure noise | 7 | 49.7 ms | 50.2 ms | 1064.1 ms | 1087.5 ms | 21x |

**Content-dependent, so quote the pair and never one number.** JPEG's `draft()` saving grows the
more compressible the image is, which is why the ratio moves from 21x on noise to ~50x on
photo-like content. Real photographs sit nearer the photo-like row; noise is a worst case for
both codecs and is included only to bracket the range.

**Corpus caveat, stated rather than smoothed over.** These are **synthetic 12 MP fixtures on one
machine**, not a real library, so this is a *known limit with numbers attached* and **not a
baseline row** in §1 - it does not describe a pipeline stage over a named corpus the way those
rows do. Two earlier photo-like runs gave 5.9 ms / 336.7 ms and 6.2 ms / 319.5 ms; treat the
ratio as "about fifty times", not as 52.

**Why it matters more than it looks.** HEIC has been the iPhone default capture format since
2017, so on a modern phone library this is the **common** path rather than an edge case, and
perceptual hashing runs for every image (unlike SHA-256, which the size pre-filter spares for
~94% of files). It is also parallelised across files by the worker pool, so the wall-clock effect
is the pool's throughput rather than a straight multiplication.

**The hypothesis was tested on 2026-08-02, and it does not survive the pinned library.** It read:
pillow-heif exposes an embedded thumbnail, a dHash needs 8x8, so decode the thumbnail instead of
the frame. The diagnosis was right and the lever does not exist.

- **`pillow-heif 1.5.0` exposes thumbnail *metadata* only.** `info["thumbnails"]` is a list of
  **integers** - the box sizes present in the container - not decodable images. There is no
  thumbnail image class among its exports (`HeifAuxImage` and `HeifDepthImage` exist; no
  thumbnail equivalent), and the library's own source collects those integers and stops. So
  there is no supported way to ask this version for the thumbnail's pixels. Reported rather
  than worked around: a private path into the C bindings would be a maintenance surface bought
  for a speed win, on the one library that reads untrusted media.
- **`DECODE_THREADS` is not the cheaper lever either.** Measured n=7 per setting on the same
  12 MP fixture: 1 thread 313.6 ms, 2 -> 335.1, 4 (default) -> 315.3, 8 -> 342.5, 16 -> 326.6.
  Every value sits inside the run-to-run band, on a 16-core machine. Changing it buys nothing.
- **Where the time actually goes, for whoever picks this up.** Split per phase, n=7: HEIC spends
  **285.5 ms decoding and 39.1 ms hashing**; JPEG spends 5.6 ms and 0.8 ms. Both are **88%
  decode**, so the diagnosis holds - a scaled decode is the right idea. Note the full-resolution
  frame is paid for twice: once to decode it, then again in the resize, which is why HEIC's hash
  step alone is 39 ms against JPEG's 0.8 ms (post-`draft()` JPEG is already 500x375).
- **Correctness was never reached**, so the stored-hash compatibility question is still open and
  would have to be answered before any future attempt: every HEIC already in a catalog was hashed
  at full resolution, and a thumbnail-derived dHash is not guaranteed to equal it. A silent
  near-duplicate regression on the majority format would be worse than a slow hash.

**Fixture caveat, because it limits what this measured.** A generated HEIF has **no embedded
thumbnail at all** - `img.save(..., format="HEIF")` yields `thumbnails == []`, and passing
`thumbnails=[256]` writes them but they still come back as sizes. Real iPhone captures normally
carry one; none were available here, so the thumbnail *presence rate* on real photographs is
**unmeasured**. That does not change the conclusion - the API to decode one is absent either way -
but a future attempt on a newer pillow-heif should re-check presence before assuming a win.

**Still not on the do-not-touch list in §4.** The idea is sound and the cost is real; what failed
is the route. If a later pillow-heif exposes a scaled or thumbnail decode, this is worth
re-testing - starting with the correctness question above, not the stopwatch.

### 3.2 The `(aac)` readability probe costs 3% of a pass that was already opening every file

Added 2026-08-02 with `(aac)`. `compute_hashes` now opens every path and reads one byte before
the cache split, so a file that cannot be read is **named** instead of collapsing into the same
`FileHashes(None, None)` the size pre-filter produces for a file it legitimately skipped.

Recorded here because it is new per-file I/O on the preview path, which is the one place this
document says to be suspicious of, and because the obvious cheaper alternative was rejected on
correctness rather than on cost - see below.

**Measured 2026-08-02.** Hermetic fixture of 2,000 generated JPEGs (3.7 MB total), local SSD,
page-cache warm, AMD Ryzen 7 4800H, Linux, Python 3.13. n = 9 for the probe and the stat pass,
n = 5 for the two hashing passes. p95 is the observed maximum at these sample sizes.

| Pass, over the same 2,000 files | median | p95 (max) | spread | per file |
|---|---|---|---|---|
| **`_probe_readability` (new)** | **13.5 ms** | 14.3 ms | 1.08x | **6.7 us** |
| `_sizes` stat pass | 4.6 ms | 6.9 ms | 1.60x | 2.3 us |
| `sha256_file` | 19.5 ms | 19.8 ms | 1.03x | 9.7 us |
| `perceptual_hash` | 472.1 ms | 494.6 ms | 1.06x | 236.0 us |

**The probe is 3% of the perceptual pass, and 3% of all four combined.** It is dominated by
exiftool, which §1 has as the preview's real cost at ~231 s for 2,064 files on FUSE. **O(n)**
syscalls; **no extra bytes are read** - one byte, not one file.

**Why not read the answer off `perceptual_hash` for free.** That function already opens every
file, so the information looks like it costs nothing. Rejected on correctness: Pillow raises a
plain `OSError` for *"image file is truncated"*, a corrupt but perfectly **readable** JPEG.
Deriving readability from Pillow's exception taxonomy would report a corruption problem as a
permission problem, sending the user to fix a file mode that was never wrong. The saving would
have been 6.7 us per file. Pinned by
`test_a_corrupt_but_readable_image_is_not_called_unreadable`.

**Not a candidate for "only probe what the worker will not read anyway".** Probing only
unique-size files would halve nothing measurable and would reopen the cache hole: `HashCache`
keys on size and mtime, both from `stat`, and `stat` succeeds on an unreadable file - so a file
that was readable last run returns a cache hit and never reaches a worker at all. The probe
must stay ahead of the cache split. See §4.

## 4. Non-findings - things to leave alone

Recorded so a future optimizer doesn't "improve" them:

- **The size pre-filter** (`scan._needs_sha`) is the single best optimisation in the codebase:
  it removes SHA-256 for ~94% of realistic-size files. Do not "simplify" it away.
- **Exact dedup** is a dict lookup - O(1)/file. Nothing to win.
- **categorize / date-resolve / naming / layout** together cost **~30 µs/file** (≈3 s at 100k).
  They look loop-heavy and are not worth touching; optimising them would trade readability for
  noise.
- **Event clustering is O(n log n)**- one sort, three linear passes. It is not the quadratic
  thing it resembles.
- **`hamming_distance`** is already optimal: `int(a,16) ^ int(b,16)` then `.bit_count()`, a CPU
  popcount at ~271 ns including loop overhead. The O(n²) is the *number* of comparisons, not
  their cost - replacing this function would win nothing.
- **Verify re-reads every byte on purpose.** It exists to catch silent corruption, which changes
  content without changing size or mtime. Never cache it. (Already contract-recorded.)
- **exiftool as the sole metadata reader**, batched - the per-file cost is 2.2 ms at 12 MP
  because it reads headers, not whole files.
- **Defender exclusions do not speed up the Windows CI lane, because Defender real-time
  scanning is already off there.** Tested 2026-08-02 on the runner itself rather than reasoned
  about: a step added to the Windows lane excluded pytest's basetemp, `RUNNER_TEMP` and the
  chocolatey directory, and printed `Get-MpComputerStatus` first. It reported
  **`RealTimeProtectionEnabled = False`**, so there was nothing for an exclusion to prevent. The
  Pytest step came in at 1097 s against a 704 s / 1037 s baseline - no change, and the timing
  carries no information anyway given that lane's 45% run-to-run swing. The **mechanism** is what
  is ruled out, not the number, which is why one run settles it.
  **One thing worth keeping from it:** pytest's basetemp on a GitHub Windows runner is
  `C:\Users\RUNNER~1\AppData\Local\Temp`, while `RUNNER_TEMP` is `D:\a\_temp`. They are
  different directories. Anything aimed at "where the tests write" on that runner must use the
  former; the obvious `$env:RUNNER_TEMP` would have excluded a path the suite never touches.
  **The Windows lane is still ~13.5x ubuntu on the identical command and unexplained.** The
  measured facts stand: setup is 3 s so caching is a dead end, the Pytest step is 95% of the
  lane, and the suite performs 20,034 filesystem create/write operations and 287 spawns of a
  PAR-packed `exiftool.exe`. Those remain the candidates; antivirus is not.
- **The `(aac)` readability probe runs over *every* path, before the hash-cache split.** It
  looks like an easy 6.7 µs/file to reclaim by probing only files the worker will not read
  anyway. It is not: `HashCache` keys on size and mtime, both from `stat`, and `stat` succeeds
  on a file whose bytes cannot be read - so a file that was readable last run and is unreadable
  now returns a cache **hit** and never reaches a worker. Narrowing the probe restores the exact
  silence `(aac)` closed, on the repeat preview that is the ordinary way people use this tool.
  Measured in §3.2 at 3% of a pass that already opens every file. Pinned by
  `test_a_cached_file_that_became_unreadable_is_still_named`.

Two more, added by the pass that wrote this document:

- **The metadata write bakes a staged copy, never the source.** That is what makes batching it
  safe: a batch that dies part-way can only damage a temp file. Do not "optimise" the staging
  copy away by writing in place.
- **`WRITE_BATCH_SIZE` is 100, not 200 like the read batch.** Staged copies occupy real disk, so
  the constant is also the peak scratch footprint of an ingest. Raising it trades a few percent
  of speed for gigabytes of temp space on exactly the machines least likely to have it.

### Cleared suspects

- **No unindexed query that scales.** All 9 hot queries checked with `EXPLAIN QUERY PLAN` at
  100k rows; every `SCAN` is an inherently full-table read (`seed_rows`, `media_names`) rather
  than a missing index. Worst case 474 ms.
- **No N+1 in the UI.** Progress is SSE-pushed, not polled; the only `setInterval` is the 1 s
  repaint of the elapsed clock, which makes no requests.
- **No per-file subprocess anywhere.** Both the read and the write path batch.
- **No repeated disk pass.** One `rglob`; one read per file per run; `Destination.list()` is
  never called per-file.

---

## 5. CI lane durations (measured 2026-08-01, so they are not re-measured)

Gathered for the self-hosted-runner question, which is **deferred until the repo goes private**
(a self-hosted runner must never serve a public repo: a fork's pull request would run arbitrary
code on the machine). Recorded here because the numbers are the input to that decision and they
will keep.

Mean wall-clock per lane, over the six most recent runs:

| Lane | Mean | GitHub billing multiplier |
|---|---|---|
| `check (windows-latest)` | **6.2 min** | 2x |
| `check (ubuntu-latest)` | 2.3 min | 1x |
| `e2e (chromium, ubuntu)` | 2.0 min | 1x |
| `check (macos-latest)` | 1.8 min | 10x |

Two things follow, and both point away from self-hosting as the first move.

**Windows dominates wall-clock, and Hetzner cannot host it.** Hetzner is Linux only, so moving
the Linux lanes there would shorten the two lanes that already finish while Windows is still
running - saving nothing a user waits for.

**macOS dominates *billing* despite being the fastest lane.** At the 10x multiplier its 1.8
minutes cost more against a private-repo quota than Windows' 6.2 at 2x. So the cheapest lever is
**matrix restriction** (Ubuntu on push, full matrix on tags), not new infrastructure - and it
needs no machine to patch, monitor, or keep ephemeral.

The full costing was researched and is deliberately not written up until the repo actually
flips, since GitHub's rates changed in January 2026 and the self-hosted platform fee was
announced and then postponed rather than cancelled.
