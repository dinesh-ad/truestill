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

## 1. Baseline — cost per stage

Complexity is stated in *n*, the number of files. Timings are at **2,275 files**; the 100k
column projects from measured per-file cost, or from measured growth for the super-linear one.

| Stage | Complexity in n | 2,275 measured | %share | → 100k |
|---|---|---|---|---|
| scan / discover | **O(n)** — one `rglob`, one stat each | 0.042 s | 0.5% | ~1.8 s |
| exiftool read | **O(n)**, batched 200/process | 6.16 s | 74.5% | ~4–7 min |
| hashing | **O(total bytes)**, parallel, size pre-filtered | 1.93 s† | 23.3% | ~14 min cold, ~0 cached |
| exact dedup | **O(1)/file** — dict on sha256 | in above | — | flat |
| perceptual dedup | **O(n²)** — linear scan per file | 0.72 s | — | ≈ 22.6 min ⚠ see §3 |
| categorize | **O(n)** — 6 ordered rules, first match | 0.030 s | 0.4% | ~1.3 s |
| date-resolve | **O(n)** — ≤5 tag lookups + 3 regexes | 0.030 s | 0.4% | ~1.3 s |
| naming | **O(n)** | <0.001 s | 0.0% | <0.1 s |
| layout / render | **O(n)** — token substitution | 0.009 s | 0.1% | ~0.4 s |
| execute / copy | **O(total bytes)** | 0.073 s† | 0.9% | I/O-bound |
| metadata write (Takeout) | **O(n)**, batched 100/process | 9.3 ms/file | — | ~15.6 min |
| event clustering | **O(n log n)** — one sort, three linear passes | 0.004 s | 0.0% | ~0.2 s |
| verify | **O(total bytes)** — re-reads by design | — | — | I/O-bound |
| reclaim planning | **O(n)** + a full re-hash per candidate | 474 ms (query @ 100k) | — | <1 s query |
| catalog queries | **O(n)**, all indexed or inherently full-table | 17–474 ms @ 100k | — | see §4 |

† small fixtures (~8 KB). **File size flips the ranking**: at realistic 12 MP (11.6 MB),
exiftool reads cost 2.2 ms/file against 8.2 ms/file for hashing, which makes hashing ~79% of a
cold preview. Both orderings are real; which dominates depends on the library.

### Fixed in the 2026-07 pass

Two stages in that table used to be the two worst things in the pipeline.

| Fix | Before | After | At 100k |
|---|---|---|---|
| Metadata write batched (`exif.write_metadata_batch`) | 254.9 ms/file | 9.3 ms/file | 7.1 h → **15.6 min** |
| Custody count (`Catalog.single_copy_count`) | 224 ms | 17.5 ms | per refresh, **13× cheaper** |

The metadata-write figure is measured over 1,203 real JPEGs, staging copy included in both
columns — that is why it is 9.3 ms rather than the 5.2 ms of the bake alone. The write path
had been spawning one exiftool process per file, and process startup, not work, was ~98% of it.

**The known next rung on the metadata write, deliberately not built.** exiftool's persistent
`-stay_open True -@ -` mode was measured against the argfile batch and is **1.12× faster** —
on top of a 27× win already banked. That 12% costs a persistent child process, a reader
thread, timeout handling and a mid-batch-death lifecycle, on the one path that modifies bytes
the user keeps. It is the correct escalation *if the batch ever becomes the bottleneck again*,
and it gets built when a measurement says so — not before. Full rationale: `DECISIONS.md` D4.

Also recorded: the **hash cache** (`hash_cache.py`) took a repeat preview of 2,275 unchanged
files from 15.8 s to 4.7 s by never reading an unchanged file twice.

---

## 2. The rule

> **Every new pipeline stage states its complexity in *n*, in its module docstring. A stage
> worse than O(n log n) must say so explicitly and justify why the simpler thing is the right
> trade at the scale we serve.** New stages get a row in §1 — measured, not asserted.

This is a quality gate, referenced from
[`IMPLEMENTATION_STANDARDS.md`](IMPLEMENTATION_STANDARDS.md) §6. The point is not to forbid
quadratic code; `DedupIndex` is quadratic on purpose (§3). The point is that it must be a
decision on the record rather than an accident nobody priced.

---

## 3. Known limit: perceptual dedup is O(n²)

`DedupIndex.check` compares each incoming file against every known perceptual hash. The cost
per comparison is already optimal — a 64-bit XOR and a CPU popcount, ~271 ns including loop
overhead — so what grows is the *number* of comparisons, not their price.

| n | total | per file |
|---|---|---|
| 1,000 | 0.14 s | 0.14 ms |
| 2,275 | 0.72 s | 0.32 ms |
| 5,000 | 3.39 s | 0.68 ms |
| 10,000 | 13.5 s | 1.35 ms |
| 20,000 | 54.3 s | 2.71 ms |
| 100,000 | ≈ 22.6 min (projected) | 13.6 ms |

**It does not matter below ~10k images in one index, and it is intolerable above ~20k.** At
today's scale it is 0.7 s, and a BK-tree would be real machinery bought for a real 0.7 s. So it
has deliberately **not** been built.

**The alarm, so the trigger reaches whoever hits it.** `dedup.LINEAR_SCAN_ALARM` is 10,000: the
first index to cross it logs one line — *"perceptual matching is now the slow path … known,
planned"* — at the crossing itself. One integer comparison per registration, once per index.
A threshold that lives only in a document reaches people who read documents; this one reaches
the person with 10,000 photos.

**When it is due:** a BK-tree over Hamming distance is the literature-standard fit for a fixed
small threshold like `DEFAULT_PHASH_THRESHOLD`, and `DedupIndex`'s interface was designed for
the swap. A VP-tree is the more general metric-space answer and buys nothing extra here; LSH
suits *approximate* nearest-neighbour at far larger scale and would trade away exactness we
currently have.

---

## 4. Non-findings — things to leave alone

Recorded so a future optimizer doesn't "improve" them:

- **The size pre-filter** (`scan._needs_sha`) is the single best optimisation in the codebase:
  it removes SHA-256 for ~94% of realistic-size files. Do not "simplify" it away.
- **Exact dedup** is a dict lookup — O(1)/file. Nothing to win.
- **categorize / date-resolve / naming / layout** together cost **~30 µs/file** (≈3 s at 100k).
  They look loop-heavy and are not worth touching; optimising them would trade readability for
  noise.
- **Event clustering is O(n log n)** — one sort, three linear passes. It is not the quadratic
  thing it resembles.
- **`hamming_distance`** is already optimal: `int(a,16) ^ int(b,16)` then `.bit_count()`, a CPU
  popcount at ~271 ns including loop overhead. The O(n²) is the *number* of comparisons, not
  their cost — replacing this function would win nothing.
- **Verify re-reads every byte on purpose.** It exists to catch silent corruption, which changes
  content without changing size or mtime. Never cache it. (Already contract-recorded.)
- **exiftool as the sole metadata reader**, batched — the per-file cost is 2.2 ms at 12 MP
  because it reads headers, not whole files.

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
