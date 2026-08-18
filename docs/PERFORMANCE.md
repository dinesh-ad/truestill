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
| ~~attach, **re-attach**, warm-cache~~ | 2,269 copies, 6.2 GB | 5 | ~~0.350 s~~ | ~~0.354 s~~ | ~~1.02x~~ | ~~1.091 s~~ / ~~p95 1.113 s~~ |
| ~~attach by remembered path, cold~~ | 2,269 copies, 6.2 GB | 5 | ~~8.885 s~~ | ~~14.30 s~~ | ~~1.96x~~ | ~~15.92 s~~ |
| ~~attach by remembered path, warm~~ | 2,269 copies, 6.2 GB | 5 | ~~0.316 s~~ | ~~0.339 s~~ | ~~1.15x~~ | ~~0.282 s~~ |

> **The warm re-attach row is struck because the speedup was produced by a defect (2026-08-07).**
> Attach's second pass was fast because its first pass had written its own cache rows - and those
> rows carried `perceptual=None`, which a later organize preview took as a hit and used to skip
> near-duplicate detection for those files (§8; measured `near_dup=1` without an attach,
> `near_dup=0` after one). Attach now reads the cache and never writes it, so a repeat re-attach
> pays the cold price - **6.302 s local / 22.248 s FUSE** - unless something else hashed those
> paths. That is the honest cost of the fix, and it lands only on repeated re-attaches: the
> steady-state row is unaffected, because a file already at its recorded path is never read.

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

### 1.2 Thumbnails (measured 2026-08-13, 600 fenced-corpus files, median 8 MP JPEG)

**Not a pipeline stage**, and deliberately so: `thumbnails.py` offers no way to sweep a library.
One thumbnail is **O(1)** and they are built per visible tile, so a 12-photo run never pays for
33k files. `GRID_SAMPLE_LIMIT` (48) bounds what a single result can ask for.

| | ms/file |
|---|---:|
| decode at 1/8 DCT scale + resize | 20.0 |
| WebP encode, method 2 | 3.1 |
| **cold total** | **~23** |
| warm (cache hit, no catalog opened) | 0.05 |

Median entry 13,395 bytes. A 24-tile viewport costs **0.55 s cold, once**.

**Two numbers here were wrong before they were measured properly, and both were found by
re-running the alternatives against the SAME 600 files rather than comparing across runs:**

* **An 80-file sample said 14 ms and was out by 2.3x.** It skewed small. §2.1's rule is why the
  corpus figure is the one recorded.
* **`draft()` was under-scaling by a factor of four in pixels.** It picks its DCT scale from the
  *tighter* of the two ratios while `thumbnail()` fits the *long* edge, so a SQUARE target lets
  the short edge decide: 3200x2368 decoded at 800x592 (1/4) where the aspect-correct target gives
  400x296 (1/8). 25.8 -> 20.0 ms, at a mean per-channel difference from a full decode of 1.6/255.

**Leave alone - already priced and rejected:**

* **The embedded EXIF thumbnail** (~1 ms) is not reachable through a supported Pillow API: the
  IFD1 offsets (tags 513/514) are absent from `getexif()` on **0 of 600** files. Taking it means
  a hand-rolled JPEG marker scanner plus a fallback for what it misses.
* **WebP `method` above 2.** Encode ms / median bytes: m0 2.02/15,743 - m1 2.48/14,892 -
  **m2 3.09/13,395** - m3 6.28/13,025 - m4 6.25/13,031 - m6 17.83/12,341. Past 2 the encode
  doubles to buy 3% fewer bytes. Pillow's default is 4.
* **A batch endpoint for the grid.** It would defeat per-thumbnail HTTP caching - the thing that
  makes a revisit cost 0.05 ms - and put the whole grid behind its slowest decode.

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
| **Corpus fence holds** (`PROJECT_STATUS.md` §4): The Memory Cabinet, Output, or a hermetic fixture. **Never the fenced folder.** | Not a performance rule, but it binds this document like every other. |
| **A destructive stage is measured on a hermetic fixture**, restored between runs outside the stopwatch. | A benchmark must never be the thing that rearranges someone's library. This is why apply/undo/cleanup below are fixtures and not Output. |

**Two limits that apply to every local-SSD row here, stated once.** The OS page cache cannot be
dropped without root, so these are **page-cache-warm** figures; a genuinely cold-disk read is
not measured and would be slower. And the cloud FUSE class is **not measured at all** in this
pass, because the mount was absent when the numbers were taken - see the empty column in §1.1
rather than an interpolation from the local figures.

---

## 3. Known limit: perceptual dedup is O(n²)

> **The rest of §3 is the pre-2026-08-02 implementation and its conclusions are superseded by
> §3.0 below.** Kept because it is the measurement that justified replacing it. **Its opening
> claim - that the per-comparison cost was already optimal - is wrong**, and §3.0 says how.

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

**The table above is the implementation that shipped until 2026-08-02**, kept because it is the
measurement that justified replacing it. Everything below supersedes its conclusions.

### 3.0 Superseded 2026-08-02: the per-comparison cost was not optimal after all

The paragraph opening this section said the cost per comparison *"is already optimal - a 64-bit
XOR and a CPU popcount"*. **That reading was wrong, and it is the reason the fix took a year to
find.** The code was `(int(hex_a, 16) ^ int(hex_b, 16)).bit_count()`: the XOR and the popcount
were indeed nearly free, but each pair first **re-parsed two hex strings into Python integers**.
Measured 2026-08-02 at **263-269 ns/pair, flat in n** - the parsing was essentially the entire
number, and "optimal" described the two operations that were not the cost.

Hashes are now packed to `uint64` once at registration and compared with one vectorised
`np.bitwise_xor` + `np.bitwise_count` per incoming file. **Same O(n²) pair count**; the constant
falls by ~300x.

| n images | before (per pair) | after (per pair) | before (total) | after (total) | speedup |
|---|---|---|---|---|---|
| 10,000 | 269 ns | 1.3 ns | 13.5 s | 0.1 s | 210x |
| 33,457 | 263 ns | 0.9 ns | 147 s | 0.5 s | 291x |
| 150,000 | 266 ns | 0.8 ns | 2,996 s | 8.9 s | 338x |

**Method** (§2.1): synthetic 64-bit dHash-shaped values with ~8% planted near-duplicate
clusters, median of 60 probes against a full index at each n, per-pair cost multiplied by
N(N+1)/2 for the totals. AMD Ryzen 7 4800H, Linux, Python 3.13, NumPy 2.5.1.
**The method is validated against this document rather than trusted:** the same extrapolation
applied to the *old* implementation projects **13.5 s at 10,000** against the **13.709 s**
measured independently in §3's table above - 1.5% apart.

**The alarm is gone.** `dedup.LINEAR_SCAN_ALARM` warned at 10,000 that *"perceptual matching is
now the slow path"*. True of the old loop, false of this one - the same 10,000 now costs ~0.1 s -
and there is no larger n to re-aim it at either: at 150,000 matching is ~9 s against per-file
stages measured in the thousands of seconds. A threshold with no honest value is worse than no
threshold, so the constant and its warning were removed rather than adjusted.

**No BK-tree - `(v)` is closed on measurement, not deferred again.** The reasoning is in
`SHIPPED.md` `(v)`; the number is that it prunes only ~85% at threshold 5 and loses to the
packed scan by 89x at 150,000.

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
- ⚠ **`hamming_distance` was on this list and should not have been. Withdrawn 2026-08-02.** The
  entry read *"already optimal … replacing this function would win nothing"*, and replacing it
  won **291x** (§3.0). The reasoning had one flaw doing all the damage: it priced the XOR and the
  popcount, which are indeed free, and never priced the `int(hex, 16)` on either side of them -
  which was ~260 of the ~271 ns. From "the cost per comparison is optimal" it followed that only
  the *number* of comparisons could be attacked, which is what pointed `(v)` at a BK-tree for a
  year. **The lesson is this list's own rule: a "leave it alone" entry must name what was
  measured, not what was inspected.** An unmeasured one does not merely fail to help - it stops
  the next person looking.
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

Mean wall-clock per lane, over the six most recent runs.

⚠ **The e2e row was re-measured 2026-08-14 and the rest were not.** It read `e2e (chromium,
ubuntu) | 2.0 min` until then, which had been wrong since `(9cdd85d)` added WebKit - the
engine the Tauri shell actually renders in on Linux and macOS. A lane that doubled its
browser count kept a single-engine number, and the row still said `chromium` while the
workflow ran both. **The other three rows are still the 2026-08-01 measurement**; do not read
this table as uniformly current.

⚠ **Re-measured again 2026-08-15, and a single figure was the wrong shape for this lane.** The
row read **18.6 min**, one run (`31823157259`, 1114 s), and that is below the range the lane
actually occupies: **1169-1391 s (19.5-23.2 min) across eight consecutive CI runs**, and
**1475 s (24.6 min)** for `make e2e` locally. A lane with a `(ado)`-shaped tail varies by 19%
run to run, so one number reads as precision it does not have. The range is the honest form.

| Lane | Wall-clock | GitHub billing multiplier |
|---|---|---|
| `check (windows-latest)` | **6.2 min** | 2x |
| `check (ubuntu-latest)` | 2.3 min | 1x |
| `e2e (chromium + webkit, ubuntu)` | **19.5-23.2 min** (8 runs, 2026-08-15) | 1x |
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

### 5.0 What a long write's health check costs (measured 2026-08-03)

Recorded so nobody re-derives whether watching a run is affordable. Local disk, temp dir,
20,000 iterations each:

| operation | cost |
|---|---|
| `shutil.disk_usage()` | **1.96 us** |
| `Path.exists()` on a marker | 1.94 us |
| `read_marker()` (opens + parses JSON) | 21.18 us |
| a `stat` on a cloud FUSE mount | **~600 us** (from tier 0's measured 1,661 files/second) |

**Per file is unaffordable on the medium that matters**: 32,628 files x ~600 us is **~20 s**,
the entire tier-0 budget spent again on every run. At `run_health.TICK_SECONDS` it is
**~0.2 s over a thirty-minute run**, even assuming FUSE inflates every read.

`run_health`'s tick, its 3-strike rule and its span window are **judgement, not measurement** -
no dropping mount was available to time them against and one cannot be staged. They are
recorded that way in the code, the same way `insights.SLOW_PERCEPTUAL_WARN_SHARE` is.

**The honest limit, stated so the checks do not read as a guarantee:** they detect the ground
*moving* - a drive that disappears, a local disk that drains. They do **not** detect a mount
that is silently returning *wrong data* rather than going away. There is no evidence that
happens, and nothing was built for it speculatively.

### 5.2 What an encrypted cloud mount costs, and why no time is forecast (observed 2026-08-04)

**This is an OBSERVATION, not a benchmark row, and §2.1 is why.** That method binds every figure
here: n >= 5, median and p95, spread, cold and warm apart. This is **n = 1** - a single
54-minute run over the maintainer's own 192 GB library - and §2.1's own instruction for a figure
that cannot meet the method is to write it as *"not measured, because X"* rather than fill it in
with a guess. So: **not benchmarked, because the run is 54 minutes long on a real library behind
the corpus fence, and five of them is not a reasonable ask.** Recorded because the *scale* is
decision-shaping even when the precision is not.

| what | observed |
|---|---|
| corpus | 32,628 files / 192.49 GB, encrypted cloud mount (client-side decryption) |
| machine class | **cloud FUSE, encrypted** - a class §1.1 leaves empty |
| tier 0 (walk + `stat`) | **21 s** for all 32,628 files |
| tiers 1 + 2a (content) | **29.4 GB at ~9 MB/s**, ~53 minutes |
| CPU over the run | **3%** |
| I/O to CPU | **~31x** (~105 s of computation inside 54 minutes of waiting) |
| advance projection | 3.6x-36x, from a 5 GB sample - **it held**, at the low-middle of a 10x range |

**One mount, one connection, one evening.** A different provider, link or time of day moves
every row. Nothing here should be quoted as "Truestill's speed".

**Encryption is a separate cost from the network**, and is worth its own line.
That mount decrypts client-side, so every byte passes through their client **in addition
to** being pulled over the link. An unencrypted mount on the same connection is not this
measurement.

**The contrast is the useful part, and it is the one thing here that generalises.** Tier 0 reads
**directory metadata**; the expensive tiers read **contents**. That is why 32,628 files can be
censused in 21 s on a mount that then needs 53 minutes for 29.4 GB - and why the cheap answer
stays cheap on any mount while the expensive ones scale with the connection.

#### Why there is no in-product time forecast

The obvious signal is tier 0's own measured throughput, and it **cannot carry the claim**. Tier 0
times `stat` calls against directory metadata; tier 2a reads file contents. Those are not the
slow and fast versions of one thing, and a FUSE client that serves directory listings from its
local cache - the common case - produces a **fast tier 0 on an arbitrarily slow link**. The
correlation is therefore not merely weak; it can be **absent or inverted**, and the better the
cache, the more confident and more wrong the estimate would be.

The 3.6x-36x projection above is the evidence that settles it. That spread came from a sample of
**content reads** - a far better predictor than a stat rate - and it still spans **tenfold**. A
forecast built on the weaker signal would be worse than that, and **a wrong time estimate is
worse than none**: it is the number a user plans their evening around.

So the report states what it will read and says the honest half of the rest - the census was
quick because it read folder listings, this reads the files themselves - and no number. That is
the accurate-or-absent rule `cli._rate_note` already follows, where a files-per-second figure is
withheld below one second because it would describe interpreter startup rather than the source.
Pinned by `test_forecast_makes_no_time_claim.py`, which is a guard against a **future good
intention**: adding an estimate should fail and force this conversation rather than land because
it looked helpful.

---

### 5.1 The Windows lane's problem is variance, not trend (measured 2026-08-03)

**The rule, first, because it is what the next person needs:** reach for `pytest-xdist` when the
lane's **median** rises, not when its maximum does. Parallelism does not reduce variance; it
gives a slow machine more to do at once.

A 23-minute Windows run (`37ee466`, pytest step **1308 s**) looked like a regression against the
~450 s the exiftool-batching win had established. It was not. Three measurements, in order of
how conclusive they are:

| evidence | reading |
|---|---|
| **Ubuntu ran the same commits at 115-201 s throughout**, with `37ee466` at 158 s - dead average | the suite did not slow down |
| **`Install exiftool` moved 12 s -> 42 s -> 55 s** on exactly the three slow runs, `r = 0.75` against the pytest step | it is fixed work our code cannot touch, so the *machine* was slow |
| **exiftool spawns fell to 139**, from the 182 measured after batching | no test reintroduced per-file spawning |

Windows pytest ranged **405-1308 s** over fourteen runs on a suite that grew 1,313 -> 1,455
tests, while Ubuntu's mean *fell* from 166 s to 135 s across the same span. **Cost per test went
down.** The growth was absorbed.

**The instrument that makes this answerable without a `gh` dig** is
`scripts/ci_timing_summary.py`, which writes the pytest-to-fixed-cost ratio into each run's
summary. It discriminates because a fixed-cost step cannot be affected by our code:

| run | pytest | exiftool | ratio |
|---|---|---|---|
| `c719875` (healthy, 9 min) | 497 s | 12 s | **41x** |
| `37ee466` (slow, 23 min) | 1308 s | 55 s | **24x** |

The slow run scores *lower*, which is the whole point: both numbers rose together. A genuinely
slower suite raises the ratio instead. It is **recorded and never enforced** - a threshold would
fire on this variance, and a gate that fires on noise gets switched off and takes its signal
with it.

### 5.3 The Windows lane is I/O, not a slow machine (measured 2026-08-14, run 31795323999)

§5.1 attributed a 23-minute Windows run to the machine, and its evidence was that the fixed-cost
steps rose *with* the pytest step. **On this run they did not**, which points somewhere else:

| | windows | ubuntu | ratio |
|---|---:|---:|---:|
| pytest, summed test time | 1638 s | 121 s | **13.5x** |
| pytest, wall clock (`-n auto`) | 831 s | 67 s | 12.4x |
| `Install exiftool` - fixed work our code cannot touch | 23 s | 13 s | **1.8x** |

A machine 1.8x slower on fixed work is not producing a 13.5x suite by being slow. **The cost is
syscalls**, and the per-file ratios say so: the worst are catalog and SQLite tests - `trip_review`
79x, `clean_empty_cli` 70x, `catalog_statistics` 66x, `migrate` 56x - while the top fourteen files
are only 39% of the total. A broad, file-system-shaped tax rather than a few slow tests.

**Two causes found, one of them a guard aimed at the wrong place.**

* Python's `tempfile` reads `TEMP`, which defaults to `C:\Users\runneradmin\AppData\Local\Temp`
  on these runners. **`RUNNER_TEMP` is a different directory**, and it was the one the Defender
  exclusion named - so pytest's temp trees were never excluded. An exclusion pointed at a path the
  workload does not use cannot work, and it read as done for as long as it sat there.
* GitHub's Windows C: is the slow, read-optimised volume; D: is fast local storage. pip measured
  **10-28%** off an I/O-heavy Python suite by moving `TEMP` to D: alone
  ([write-up](https://sichard.ca/blog/2025/03/faster-pip-ci-on-windows-d-drive/)). Standard
  runners only - larger paid runners have no D:.

⚠ **NOT YET PROVEN HERE, and one run cannot prove it.** §5.1 records this lane at 405-1308 s over
fourteen runs on a near-constant suite, so a single green run is inside the noise either way. Read
the **median** of `TS_PYTEST_SECONDS` across several runs. If it does not move, delete both steps -
§5.1's own rule, and the reason it is written on the Defender step too.

## 6. Local lane durations, and the ceilings that hold them (measured 2026-08-09)

**Both lanes got materially faster on 2026-08-09, and the numbers below are the state after
that, not before.** They exist so the next person can tell drift from a bad afternoon.

| Lane | Before | After | What changed |
|---|---|---|---|
| `make test` (1,968 tests) | 89.95 s | **15.7-18.8 s**, median 17.2 s | `pytest -n auto` |
| `make e2e` (387 tests) | 417-423 s | **362.7 s** | deferred server teardown |

**Where the browser lane's time actually goes**, measured by running the same suite four ways:

| Capture | Wall clock |
|---|---|
| neither | **252.2 s** |
| `--video retain-on-failure` only | 295.7 s (+43 s) |
| `--tracing retain-on-failure` only | **322.5 s (+70 s)** |
| both (what `make e2e` runs) | 362.7 s (+110 s) |

**The trace is the expensive one, not the video** - the opposite of the guess that prompted the
measurement. It is also the one that has paid: `(abq)`'s mechanism was proven from `trace.network`
showing that no request was ever issued. The video contributed nothing to that diagnosis. So the
70 s stays, and **the 43 s of video is the candidate if this lane ever has to be cheaper** -
recorded rather than acted on, because it trades a debugging capability for time.

**Per-test server cost** (the reason the lane moved): booting one costs 6.2 ms and `create_app`
1.5 ms; **tearing one down costs 196.9 ms**, 96% of it uvicorn noticing `should_exit` on a 0.1 s
main-loop tick, twice. `force_exit` does not change it. Sharing the server would have bought the
6.2 ms and cost isolation, since `create_app` builds a live `JobManager()` per app.

**A floor no hardware beats:** the suite cannot go below ~5.5 s while its slowest single test is
5.45 s - `test_catalog_busy_refusal`, which waits out `sqlite3.connect`'s own 5 s `busy_timeout`
because that wait *is* the behaviour under test.

### The ceilings

`TEST_SECONDS_MAX = 45` and `E2E_SECONDS_MAX = 2000` in the Makefile, with CI overriding the
second to **3600**: **limits that fail the build**, at roughly 2.5x and 1.8x the medians
above. (This said `600` until 2026-08-14, a figure that predated WebKit by two engines' worth
of work - the number in the doc and the number in the Makefile drifted apart the moment the
lane grew, and nothing reads a doc.) They catch a doubling and ignore a busy
laptop. Raising one is a decision made on purpose, in its own commit, with a new measurement -
the failure message says so.

**Not enforced in CI, deliberately.** The same Windows step measured 566 s, 1009 s, 1472 s and
596 s on commits whose test counts differ by under 2%. A ceiling there would fire on variance
rather than drift, and a gate that fires on noise gets switched off and takes its signal with it -
the same reasoning §5 already applies to its own ratio.

### What speeding up the suite did to the collection-order pass

**A second cost moved when the first one did**, which is the part worth recording. CI run
`31321298111`, ubuntu lane:

| step | wall clock |
|---|---|
| `Pytest` (parallel) | **157 s** |
| `Pytest (different collection order)` (serial) | **290 s** |

The order pass stayed serial on purpose - a parallel run has no single order to be green in - so
parallelising the main suite made the **double-check nearly twice the cost of the thing it
checks**, and the largest single step in the job. Its own comment used to say it "costs nothing
in wall-clock", which was true when both passes took the same time and the ubuntu lane finished
long before Windows regardless. That sentence was correct when written and stopped being correct
without anyone touching it.

**Moved to nightly (plus pull requests) rather than dropped.** Order-dependence is a real class,
but a slow-moving one, and the specific bug it was written for is now prevented by construction:
the root `conftest.py` gives every test a data root no other test can name. So it is a backstop,
not a live catch. What that trades: order-dependence can sit on `main` for up to a day, and the
nightly that finds it has several commits to choose between.

*One honesty note about the condition:* this repo has had exactly one pull request ever, a
throwaway CI experiment, and zero merge commits. `pull_request` in that trigger is completeness,
not a second safety net - in practice this runs nightly.

### 5.4 The catalog schema race, and what a 20-second lock cost (measured 2026-08-14)

`f7a2654` took CI e2e from 2 failures to 29 and the lane stayed red for five runs. The cause was
not the commit that surfaced it: `Catalog._migrate` read `PRAGMA user_version`, read
`sqlite_master`, then wrote - three unsynchronised steps, so **two openers on a fresh catalog
both decided it was empty and both built the schema**. 21 statements each, rollback journal,
`synchronous=FULL`, all fsyncing against one another.

| | before | after `BEGIN IMMEDIATE` | after startup migration |
|---|---:|---:|---:|
| `database is locked` | **104** | 0 | 0 |
| `duplicate column` | 4 | 0 | 0 |
| schema writes / opens | 2076 / 7716 | 912 / 7828 | 912 / 8754 |
| holder median | 62.02 ms | 1.30 ms | 0.80 ms |
| holder max | **20260.04 ms** | 49.48 ms | 7.57 ms |
| lock wait p90 | n/a | 128.60 ms | **3.50 ms** |
| lock wait max | n/a | 2832.77 ms | 2034.99 ms |
| waits over 1 s | n/a | 155 | 7 |
| e2e failures | 29 | 4 | **0** |

⚠ **The last column is one run, and the lane is not green.** The very next run failed three
WebKit tests with no code change touching it. The e2e row here records what the *lock* defect
cost and what fixing it recovered; a separate rotating WebKit tail remains, censused in
`BACKLOG.md` `(ado)`, whose exit condition is **zero failures across ten consecutive runs**. One
green was read as "the lane is green" here once already.

⚠ **That exit condition was "three consecutive greens" until 2026-08-15, and this row is why the
number is not what changed.** The lane then delivered **four** greens and failed twice on an
unchanged tree. A streak of greens is the wrong instrument for an intermittent failure at any
length; the replacement counts failures over a fixed window instead.

**The number that ended the investigation is the 20260 ms holder.** Every figure before it was a
*waiter's* 5 s timeout - the same number whatever caused it, saying a lock was held and nothing
about by whom or for how long. Instrumenting the write itself took one run. Runs `31810809571`
(holder), `31821214510` (cross-process fix), `31823157259` (startup migration, green).

**2076 -> 912 is the race, not a saving.** 912 is one build per fresh catalog and the e2e lane
has ~946 tests with a function-scoped server: it is the floor. The extra 1164 were openers
rebuilding a schema another had just built. That 912 then held **exactly** across the startup
migration is what proves nothing else moved.

**Three structural hypotheses died by measurement, and they are why the conclusion is
trustworthy:**

| killed | how |
|---|---|
| "the session wrapper holds a lock across drive I/O" | the open path measured **2.26 ms** fresh, 0.31 ms migrated. Transactions are short and taken *after* drive I/O, never across it. |
| "six concurrent opens serialise into seconds" | six openers on a real runner, released by a barrier: **62-116 ms**. Even 48 openers - past the 40 Starlette's threadpool allows - reached only 2083 ms. |
| "the holder is descheduled, so it is starved rather than slow" | the same sweep under 8 cpu burners and a continuous fsync writer on 4 cores: 6 openers went 82 -> 116 ms, and the loaded shape was a **tight convoy** (spread 0.11), not one long outlier. |

A fourth was killed the same way: Playwright's video and trace capture write to the same ext4
device, so they were the obvious suspect for the tail. With both off the tail **survived** -
19198 ms against 20260 - which cleared them and left the redundant writers as the only candidate.

⚠ **Every one of those negatives was measured on an idle rig first and was wrong for it.** The
first contended figure, 36.85 ms, was taken on `/tmp` - which is **tmpfs** on the author's
machine, where `fsync` costs 0.0014 ms against 0.0010 ms without it, a ratio of 1.3x. It was RAM
speed with no durable write in it, and it was attributed to NVMe because the `df -T` that named
the disk had been run against the checkout instead. On the runner the same probe measured 213x.
**A performance number without a durability control is not a measurement of this system.**

⚠ **AMENDED 2026-08-15: THE STARTUP MIGRATION MOVED THE SCHEMA BUILD OFF THE REQUEST PATH. IT DID
NOT MAKE IT CHEAP.** The table above reads as though the cost went away - holder max 20260 ms ->
7.57 ms - and what it actually shows is the cost leaving the *measured* path. Instrumented on the
runner (`(adt)` item 5 M4, run `31905224028`, four full lanes, ~144,000 phase records):

| | p50 | p99 | max | over 1 s |
|---|---:|---:|---:|---:|
| `commit` building a **fresh** schema | 2.16 ms | 2163.6 ms | **5091.2 ms** | **153 of 3,680** |
| `commit` on an existing schema | 0.011 ms | 1.1 ms | 9.0 ms | **0 of 32,119** |
| `BEGIN IMMEDIATE` (all opens) | 0.075 ms | 18.3 ms | **5011.3 ms** | - |

**Every event over 1 s in 144,000 records is a fresh-schema commit.** The ordinary path never
exceeds 9 ms. A waiter parked **5011 ms** at `BEGIN IMMEDIATE` behind one, which is the mechanism
by which a trivial write inherits a schema build's cost - and it lands exactly on the 5 s
`busy_timeout`, so the next caller is not merely slow, it is **refused**.

**Two consequences that are easy to miss.** The lane pays this **920 times per run**, once per
test's fresh catalog - so it is a real component of lane duration, not a startup curiosity. And
**every user pays one on first run**: a new library builds the schema once, and on hardware like
the runner that is seconds, not milliseconds. Nothing here is a defect; it is a price that was
never priced.

### 5.5 What the per-open write lock costs - and what it does NOT explain (measured 2026-08-15)

§5.4 bought `BEGIN IMMEDIATE` on every open and measured the **holder** afterwards (7.57 ms max).
It never priced the **acquisition**, which every open now pays even when it will change nothing:
`Catalog.__init__` calls `_migrate` (`catalog.py:781`), which takes RESERVED (`catalog.py:830`)
before it can decide the schema is current. `(adt)` item 5 asked what that costs. Throwaway rig,
CI run **`31904426333`**, three repeats per OS, catalog at schema v19.

| | fsync p50 | uncontended open p50 | `BEGIN IMMEDIATE` p50 | N=12 p99 | N=12 max | refusals |
|---|---:|---:|---:|---:|---:|---:|
| local, ext4 | 0.855 ms | 0.227 ms | **0.008 ms** | 79.7 ms | 330.3 ms | 0 |
| ubuntu runner | 0.50-0.66 ms | **0.096-0.133 ms** | **0.004 ms** | 33.6-34.2 ms | 80.3-107.2 ms | 0 |
| windows runner | 2.31-2.47 ms | 0.574-0.613 ms | 0.055 ms | 266-309 ms | 759-875 ms | 0 |

**The lock is cheap, and the disk does not change that.** Acquisition is **4-8 microseconds**;
the dominant phase of an open is the schema *check* (0.074 ms), not the lock. A 1300x range in
fsync cost moves the open barely at all, for a structural reason worth keeping: the migration
check on a current catalog **writes nothing**, so its commit has no journal to flush. Windows is
~6x Linux throughout, in line with §5.3.

⚠ **AND THE NEGATIVE RESULT IS THE POINT: this does not explain the 6558 ms settings write that
produced `(adt)`.** Against the ubuntu runner - the platform it happened on - that observation is
**68,000x** the uncontended open and **61x** the worst contended maximum. **Zero busy refusals in
2,160 contended opens** across every configuration: the lock never refused anybody here, while the
real lane refused a job. The leading hypothesis was that per-open lock acquisition explained the
duration. **It does not, and no number in this table gets within 60x of it.** `(adt)` item 5
stays open; server-side instrumentation of the real lane is the only instrument left, which is
what §5.4 already had to do for the 20260 ms holder.

⚠ **The first local run of this rig was on tmpfs and reported fsync at 0.0004 ms** - the exact
trap the paragraph above documents, walked into by the rig that cites it. Caught by `df -T` and
re-run on ext4; both rows are above, and the conclusion held either way only because nothing here
fsyncs. **A durability control is not optional even when you have read the warning.**

### 5.6 What the per-open lock FORECLOSED, and what removing it bought (measured 2026-08-18)

✅ **SHIPPED the same day as `BACKLOG.md` `(adu)`** - `SHIPPED.md` carries the entry. The table
below is the *decision*; the landed figures are at the end of this section and they hold.

§5.5 priced the lock at 4-8 microseconds and concluded it is close to free. It is. **This
section is not about what it costs - it is about what it prevents**, which is `BACKLOG.md`
`(adu)`. Rig on ext4, `fsync` control **256x** (the scratchpad on this machine is tmpfs and
measured **1.1x**; it was refused before anything ran - §5.4's own trap, met at the door).

**The lock protects exactly one state, and it happens once per catalog.** Five opens of an
already-migrated catalog leave the file byte-identical, `total_changes = 0`, and no journal
sidecar. Removing `BEGIN IMMEDIATE` is **caught immediately on a fresh catalog** (2 openers both
build the schema) and **survives entirely on a migrated one** (0 builders, both openers fine,
file unchanged).

**What it costs to keep taking it.** Concurrency sweep on an already-migrated catalog against a
double-checked fast path that skips the transaction when the schema is current:

| | shipped p50 | fast path p50 | shipped p99 | fast path p99 | shipped max | fast path max |
|---|---:|---:|---:|---:|---:|---:|
| N=1 | 0.575 ms | 0.670 ms | 0.695 ms | 0.774 ms | 1.04 ms | 1.08 ms |
| N=4 | 2.286 ms | **0.807 ms** | 9.692 ms | **1.398 ms** | 19.0 ms | **1.70 ms** |
| N=12 | 9.565 ms | **2.201 ms** | 181.9 ms | **3.93 ms** | 232.5 ms | **4.63 ms** |

**46x on p99 at twelve openers, 50x on the worst case - and slightly SLOWER uncontended**
(0.575 -> 0.670 ms, one extra read). It is a trade, not a free win, and the uncontended row is
here so it is not read as one.

⚠ **THE FINDING THAT WAS NOT BEING LOOKED FOR: the lock does not serialise the migration chain.**
`_migrate` commits, and the `_MIGRATIONS` loop runs after that commit, outside any lock. On a
catalog stepped back one version, 150 trials, **six openers ran the same migration more than once
in 20 of them**. No errors - the migrations are idempotent - so nothing has ever failed for it.
`BACKLOG.md` `(adl)` owns it.

**Re-measured after landing, same rig**, so the decision's numbers are not left as a forecast:

| already-migrated catalog | p50 | p99 | max |
|---|---:|---:|---:|
| N=1 | 0.612 ms | 0.727 ms | 1.04 ms |
| N=4 | 1.336 ms | 2.401 ms | 2.74 ms |
| N=12 | **2.237 ms** | **3.586 ms** | **4.29 ms** |

Against 9.565 / 181.9 / 232.5 ms before. ⚠ **And N=1 is still slightly slower than the 0.575 ms it
replaced** - the trade is real and it is priced here rather than rounded away.

---

## 7. Catalog audit (measured 2026-08-09)

Read-only audit of the schema and its use, against the real 6.37 MB catalog (2,695 files, 4,933
copies). Everything here is a measurement or a query plan, not an inspection.

### Acted on

**`ANALYZE` had never run.** No `sqlite_stat1` existed, so the planner had no statistics and was
guessing at every join. Measured on a copy:

| query | no statistics | after `ANALYZE` |
|---|---|---|
| Find (`find_copies`) | 4.59 ms | **2.15 ms** |
| drive listing | 2.04 ms | **1.79 ms** |

**When it runs, decided rather than left to a schedule this app does not have:** after a unit of
work that WROTE, and only once the library has grown by `ANALYZE_GROWTH_ROWS` (1,000) `files`
rows since the last time. Never on open - that would charge `status` and `where` for statistics
they cannot use. The check itself is one `MAX(id)` (`O(1)` on the primary key) and one settings
read, on a dirty close only. `ANALYZE` costs **1.8 ms** here and **17 ms** against a 172,480-row
table, so the trigger can afford to be generous.

### Declined, with the reason, so nobody revisits them as obvious wins

**WAL - CONSIDERED AND DECLINED ON MEASUREMENT.** `journal_mode` is `delete`. WAL is the standard
recommendation for a local-first app and the 5 s busy-timeout test looks like evidence of
contention, but that test *deliberately* holds `BEGIN IMMEDIATE` from a second process. Measured
against exactly that case: **two writers block identically in both modes** (301 ms to fail at a
0.3 s timeout), and a reader was never blocked in either mode at this scale. WAL's real win is
readers not blocking writers, and no measurement here shows that problem existing. It is a lever
with no measured problem to fix; revisit it with a measurement, not with reputation.

⚠ **AMENDED 2026-08-18: THE DECLINE IS SOUND FOR THE CODE IT MEASURED AND IS NOW DATABLY STALE.**
*"A reader was never blocked"* was measured on **2026-08-09**. §5.4 landed `BEGIN IMMEDIATE` on
**every catalog open** on **2026-08-14**, so a reader stopped being a reader five days later and
nothing re-ran this. **Neither statement is wrong; the code moved between them.** ⚠ It also cuts
the other way and that is the more useful half: **while every open is a writer, WAL has nothing to
act on** - *"two writers block identically in both modes"* is exactly what a run comparing the
modes would keep finding. So this paragraph's *"revisit it with a measurement"* is right and
**incomplete**: the measurement needs a **control** with `_migrate`'s `BEGIN IMMEDIATE` made
conditional, or it reproduces this null result forever. Filed as `BACKLOG.md` **`(adu)`** (the
per-open lock, which gates it) and `(ads)` (the mode).

✅ **RE-RUN WITH THAT CONTROL ON 2026-08-18, AFTER `(adu)` SHIPPED, AND THE DECLINE STANDS - for a
better reason than this paragraph had.** A copy of the real catalog, a preview-shaped reader and a
settings writer. The decisive case is `(adt)`'s own shape, one long-held write with a reader
arriving 200 ms in: **pre-`(adu)` `delete` 1848.3 ms and `wal` 1850.6 ms - identical, this
paragraph's finding reproduced on a real workload - and post-`(adu)` `delete` 6.1 ms against
`wal` 12.4 ms, with WAL SLOWER.** WAL wins only under sustained commits (reader p99 at a
zero-delay writer: 3211.4 ms `delete` against 18.5 ms `wal`), and the crossover sits at roughly one
write per 10-20 ms. The app's only sustained writer is an organize run, which writes once per file
after a copy - mean file 2.82 MB on the measured corpus, hashing alone 3.6 ms/file warm - so it
lands at or beyond 20 ms, where `delete`'s p50 is **better**. ⚠ **And this paragraph's own
mechanism sentence was wrong**: a writer does *not* exclude readers in rollback-journal mode.
RESERVED permits them; only the commit's brief EXCLUSIVE window does not. Full tables in
`research/backlog/ads.md`. ⚠ **This entry and `(ads)` were written
without knowing about each other**, between two canon documents - which is what the reframing in
`(ads)` records.

**STRICT tables - available and declined on cost.** 0 of 16 tables are STRICT (SQLite 3.50.4
supports it), so `TEXT` columns holding sha256s, ISO dates and uuids will accept an integer.
STRICT cannot be added by `ALTER TABLE`: every table must be recreated, copied and re-indexed, on
a live user file, for a bug class this project has not hit.

**`VACUUM` - not run anywhere, and not worth running.** The real file carries **149 free pages of
1,554 - 9.6%, about 596 KB** on a 6.37 MB file. Recorded as the baseline for a future decision.

**The album insert loop** (`catalog.py:2281`) inserts row by row with a follow-up `SELECT` per
album. Albums are unbuilt and the table is empty, so it costs nothing today; fix it when albums
are built, not before.

### `find_copies` is an FTS question, not a missing index - see `(abj)`

It plans as `SCAN file_copies` and cannot be indexed as written: it filters
`LIKE '%term%'` across three columns with `OR`, and a leading wildcard defeats a B-tree **by
construction**. No index would change that plan. If Find ever needs to be faster, the answer is
FTS5 over the searchable columns, which is `(abj)`'s subject.

### The account question, decided so it is not re-derived

**An account is one row in `settings`, never a column on every table.** The catalog is already
per-user by construction - a file in one person's home directory, resolved per process - and the
filesystem is stronger isolation than a column. True multi-user sharing one catalog is a different
product, and a column now does not get there.

**The decisions document should not carry an origin field yet.** Unknown sections are preserved by
construction, so adding one later is exactly as cheap as adding it now - and a field added now
would still be absent from every document already on a drive, so a restore must handle "no origin"
either way. **If one ever lands, it reports rather than gates:** a new refusal on a rescue path,
hitting someone mid-crisis, to enforce a field that is documentation, is the wrong trade.
