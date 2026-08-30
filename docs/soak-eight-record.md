# Soak eight: the messy library - record

> ⚠ **CORRECTION, 2026-08-30 (P148/P149) - THIS RECORD'S ANSWER KEY IS WRONG BY 20 FILES.**
> **Added beside, never edited into the numbers below**: a record rewritten to stay correct stops
> being one. The defect is `(ait)` - `make_messy_corpus.py` keys every destination on
> `source.name`, and `Input/` holds two pairs of *different* photographs sharing one, so ten
> destinations each are written twice and **the manifest counts both writes while only one file
> survives**. Soak nine rebuilt the identical corpus (same seed, same source, one file added by
> P146) and hashed it from disk.
>
> **AFFECTED - do not quote these:**
>
> | §  | published | corrected |
> |---|---|---|
> | 1 | files **8,970** | **8,950** |
> | 2 | total files **8,970** | **8,950** |
> | 2 | distinct contents (sha256) **2,530** | **2,524** |
> | 2 | expected exact-duplicate skips **6,440** (**6,170** media-only) | **6,426** (**6,156** media-only) |
> | 2 | derived perceptual candidates **1,866** | **1,860** |
> | 5 | *"Expected 6,440, reported 6,156… the 284 are almost entirely the 267 `.chk` files"* | **there is no gap** |
>
> 🔑 **AND THE CORRECTION IS IN THE PRODUCT'S FAVOUR, which is why it is worth making.** §5
> explained a 284-file shortfall as the `.chk` files organize skips by extension, and reconciled
> to *"6,436 against 6,440"*. Against a key computed from the bytes, the media-only expectation is
> **6,156** and the product reported **6,156** - **exact, with nothing to reconcile.** The gap was
> the instrument, not the engine.
>
> **UNAFFECTED - these stand**, because they were measured from the catalog and the product rather
> than from the manifest: §1's size, generation time and shape list; §3's whole arc; §4's headline
> (500 of 500 stripped copies filed away from their dated twin); §5's perceptual recall table and
> its **zero false pairs** - all of it reproduced independently in
> [`soak-nine-record.md`](soak-nine-record.md) §5, role for role. Distinct source photographs
> (**666**) and the largest identical group (**52**) also stand.
>
> ⚠ **The three instrument defects §1 already records were fixed mid-run; this fourth one was
> never noticed**, and it is the one that reached the published numbers.

**Ran 2026-08-29.** Machine: 16 cores, 30 GiB RAM, Python 3.14.4, **ext4 on `/dev/nvme0n1p1`
(`rw,noatime`)** - every timing below is that machine and that filesystem. Corpus built by
`scripts/make_messy_corpus.py` at **seed 20260829**, `--files 2000`, from
`/data/TruestillLibrary/Input` **by copying**; the source was verified byte-untouched afterwards.
The plan and the sealed prediction are [`soak-seven-plan.md`](soak-seven-plan.md), read only
**after** every measurement below existed.

**This is a complete forward arc and half a reversal arc.** Organize preview, organize apply,
verify, backup and restore all ran. `reclaim`, `migrate-layout`, `undo-organize`, the dates rescue
and every app screen did **not** - named here rather than skipped, and §"What was not run" says so
again at the end.

## 1. The corpus (Q798)

| | |
|---|---|
| files | **8,970** |
| size | **18.7 GB** |
| generation | **392 s** |
| shapes | 15 emitted (S1–S9, S11–S16) |

Shape distribution: S1 1,998 · S2 1,095 · S3 1,000 · S4 1,600 · S5 999 · S6 532 · S7 667 ·
S8 400 · S9 2 · S11 6 · S12 2 · S13 2 · S14 1 · S15 166 · S16 500.

⚠ **THE GENERATOR HAD TO BE FIXED THREE TIMES BEFORE IT COULD BUILD THIS, AND ALL THREE ARE
INSTRUMENT DEFECTS I SHIPPED YESTERDAY IN `577ce65`.** Recorded because a soak whose instrument
was repaired mid-run is not the same evidence as one whose instrument held:

1. **The corpus did not scale.** Every shape used a fixed slice (`sample[:20]`), so `--files 2000`
   built **byte-for-byte the same 320-file / 610 MB corpus as `--files 60`** - and
   `soak-seven-plan.md` had already published the projection *"`--files 2000` lands near 20 GB"*,
   which could never have come true. Fixed by making the shares proportional (`_SHARE`), and
   **guarded** by `test_the_corpus_grows_with_the_sample`.
2. **A fuzzed PNG killed the run**: `_decodable` caught `(OSError, ValueError, SyntaxError)` and
   an `IndexError` came out of `PngImagePlugin.verify`. Enumerating what a fuzzer can provoke from
   a decoder is not a list anyone finishes; the boundary is now `Exception`, with the reason.
3. **`verify()` is not decodability.** A fuzzed TIFF passed `Image.verify()` and then raised
   `OSError: decoder error -2` from `convert("RGB")` **half way through a 2,000-file build**,
   leaving 3,190 files and no manifest. The filter now does the same decode the shapes do.

**All three came from `metadata-extractor-images`' 1,461 deliberately fuzzed files.** The format
corpus attacked the instrument before the product ever saw it, which is an argument for the format
corpus rather than against it.

## 2. The answer key, computed before the product was allowed an opinion (Q799)

From the manifest alone:

| | |
|---|---|
| total files | 8,970 |
| distinct contents (sha256) | **2,530** |
| contents appearing more than once | 672 |
| expected exact-duplicate skips | **6,440** (6,170 counting media extensions only) |
| largest identical group | **52 files, one photograph**, spread across ten shapes |
| derived perceptual candidates | **1,866** - 500 stripped, 1,200 resized, 166 rotated |
| distinct source photographs | 666 |

## 3. The arc (Q800)

| step | elapsed | result |
|---|---|---|
| organize **preview** | **92 s** | 8,675 analysed · 864 unique · 1,655 near-dup · **6,156 exact-dup skipped** · 0 unreadable |
| organize **apply** | **17 s** | same counts; **2.9 GB written from an 18.7 GB source**; 15.0 GB not copied |
| **verify** | **7 s** | 0 missing · 0 mismatch · 0 unreadable · 0 unverifiable |
| **backup** | **21 s** | 2,519 files / 3.0 GB copied to a second drive |
| **restore** | **<1 s** | 1 decision (the drive). Thin **and correct** - nothing was named in this corpus |

Categories: Camera 1,825 · WhatsApp 498 · Saved 196. Date sources: **exif 1,847 · none 672**.

## 4. FINDING - the headline: a stripped copy is filed a year from its twin (Q801)

**500 of 500 stripped copies landed in a different folder from their dated original. Zero landed
together.**

```
original: 2019/2019-09/2019-09-19 - Everyday/20190919_234225_IMG_20190919_234224.jpg   [exif]
stripped: WhatsApp/Undated/IMG-20190712-WA0000.jpg                                     [none]

original: 2014/2014-08/2014-08-16 - Everyday/20140816_101508_2014816101508_1.jpg       [exif]
stripped: WhatsApp/Undated/IMG-20190712-WA0002.jpg                                     [none]
```

**What a user sees:** the same photograph twice, one filed under the year it was taken and one in
`Undated/`, five folders apart. This is the shape every incumbent gets wrong - and Truestill is
**one step from the answer nobody has**, because the perceptual tier *already pairs them*:
**499 of those 500 pair at Hamming distance ≤ 5, 427 of them at distance 0.** The date is
recoverable from the pair and nothing consumes the link. Filed as **`(aih)`**.

## 5. The answer key versus the product (Q802)

**Exact duplicates - the product is right, and the gap is a different finding.** Expected 6,440,
reported **6,156**. The 284 are almost entirely the **267 `.chk` files** of S6, which organize
skips by extension as *"unrecognized"* and never analyses. Reconciled: the skips implied by the
contents the catalog did record are **6,436** against 6,440. **Exact dedup found every duplicate
among the files it was willing to look at.**

**Perceptual - recall measured at the real threshold (5):**

| role | n | paired (≤5) | missed | median | p90 | max |
|---|---|---|---|---|---|---|
| stripped | 500 | **499** | 1 | 0 | 1 | 26 |
| resized-half | 398 | **392** | 6 | 0 | 1 | 24 |
| resized-quarter | 398 | **391** | 7 | 0 | 2 | 24 |
| resized-web | 398 | **389** | 9 | 0 | 2 | 26 |
| rotated | 166 | **1** | 165 | 32 | 38 | 46 |

Excluding rotation: **1,671 of 1,694 paired - 98.6 % recall, 23 missed.** The distance histogram
is `0:1151 · 1:355 · 2:106 · 3:42 · 4:10 · 5:7`, then a thin tail at 6, 7, 8, 12, 14, 16, 17, 19,
23, 24, 26.

⚠ **THE FIRST VERSION OF THIS PARAGRAPH WAS METHOD-LIMITED AND IS CORRECTED HERE BEFORE IT EVER
SHIPPED.** It read *"FALSE PAIRS: ZERO"* on a test that compared **identical hash strings** - while
the product pairs within **Hamming distance ≤ 5**. Two different photographs could pair inside the
threshold neighbourhood and that test would never have seen it. The claim was true by luck rather
than established, and a positive result nobody can defend is worth less than none.

**Re-measured properly (P132): all-pairs over the 2,491 organized files whose hash survives
`(ahq)`'s no-signal floor - 3,101,295 comparisons, 4,011 pairs within threshold 5.** Cross-source
pairs: **5 distinct** (45 raw, inflated because each resized copy pairs with each copy of the
other photograph). Every one:

| distance | pair | what it is |
|---|---|---|
| 0 | `2014816101549.jpg` ↔ `2014816101549_1.jpg` | **one photograph stored twice** in Ad's own library |
| 2, 3 | `IMG_20200714_213432_Bokeh.jpg` ↔ `..._213435_Bokeh.jpg` | **a burst - three seconds apart** |
| 4, 5 | `DSC_2141.JPG` ↔ `DSC_2142.JPG` | **consecutive camera frames** |

🔑 **The result survives and is now actually established: ZERO pairs between UNRELATED
photographs.** Two of the three are bursts, which is what a near-duplicate tier exists to catch -
finding them is the feature. On a corpus built to induce false pairs (1,200 resizes, 500 EXIF
strips, 166 rotations of real photographs), with 98.6 % recall at threshold 5, **the tier never
joined two photographs that are not of the same moment.** The two degenerate poles
(`0000000000000000`, `8000000000000000`) never enter this at all: `dedup.carries_no_signal(h, 5)`
returns **True** for both, so `(ahq)`'s floor refuses them from the index.

⚠ **And the bursts are a real constraint on `(aih)`**: `DSC_2141` and `DSC_2142` are **different
photographs** pairing at distance 4-5, so *"a near-duplicate is not the same photograph"* now has
measured instances rather than an abstract caution.

## 6. FINDING - one photograph 52 times is 51 sentences (Q803)

The largest identical group is **52 files of one photograph**, spread across ten shapes. The
product skips 51 of them correctly and **says so 51 separate times**:

```
  IMG_0001.JPG  [SKIP: exact duplicate]
      already here : /data/tmp/truestill/messy/DriveA/Full/IMG_20190919_234224.jpg
      via          : SHA-256, earlier in this batch
```

Every block names the same twin. There is no grouping, so the 52-way group is 51 entries
**scattered through** a section it shares with 6,100 others. Measured: the preview is
**45,653 lines**, of which the exact-duplicate section alone is **24,628 lines** for 6,156
duplicates and the near-duplicate section **14,898** for 1,655. The counts in `SUMMARY` are
correct and legible; the list a user would scroll to act on is not. Filed as **`(aii)`**.

## 7. FINDING - a remedy that fails when copied (Q805)

`backup` onto an unregistered folder refuses correctly and prints:

```
If this folder is new, register it:  truestill drives --init /data/tmp/.../backup
```

Running exactly that returns `error: --init requires --label`. **The suggested command cannot
work as printed.** Small, and exactly the class `(agp)`'s CLI-remedy census exists for. Filed as
**`(aij)`**.

## 8. The predictions, scored (Q804)

| # | prediction | verdict |
|---|---|---|
| 1 | S3: stripped copy and original land in different folders, twin in `Undated/` | ✅ **HIT**, 500/500, and the placement is exactly as written |
| 2 | S3: pixels untouched → dHash distance 0 → flagged near-duplicate → copied in | ✅ **HIT** - 427 at distance 0, 499/500 within threshold |
| 3 | S3: often unique-size so no sha256 is computed at all (`(aac)`) | ⚠ **NOT TESTED** - the catalog does not record which files the size pre-filter skipped |
| 4 | S4 pairs by construction; the open question is the tail past 5 | ✅ **HIT**, and the tail is **smaller than implied**: 98.6 % recall, 23 misses in 1,694 |
| 5 | Exact dedup stays correct and fast however many copies exist | ✅ **HIT** - every duplicate among analysed files found; apply 17 s |
| 6 | The genuine quadratic is `organizer._free_relative`'s name probing | ❌ **MISS, by non-exercise.** Exactly **one** genuine collision suffix in the whole output, depth `_1`. All 51 extra copies were exact-dup **skipped before placement**, so the probe was never entered. To reach it a corpus needs many NEAR-duplicates sharing one original filename - a shape S1–S16 does not build |
| 7 | Decode time scales with copies, because `HashCache` misses on renamed files | ❌ **MISS.** Preview cost **10.6 ms/file** against soak five's **9.8 ms/file** on a clean corpus - essentially flat. The exact-duplicate path short-circuits before the perceptual decode, so 8,675 files needed only **2,518** decodes. The product is better than predicted |
| 8 | `(ahq)`'s no-signal floor amplifies across copies | ⚠ **PARTIAL** - 100 files were excluded as *"too little detail to compare"*, and the excluded set is dominated by repeated copies of a few PNG test patterns, so the amplification is real. It cost nothing here: their content was still deduped exactly |
| 9 | The two near-duplicate counts diverge | ⚠ **NOT TESTED** - that count is an app-screen statistic and no app surface was run |
| 10 | A many-way group leaves no durable trace | ✅ **HIT** - no table in the catalog records exact-duplicate skips; the 52-way group exists only in the transcript |
| 11 | Nothing can say "35" | ✅ **HIT** - 51 pairwise sentences, all naming one twin, no group concept |
| 12 | S15 rotated copies fall far outside threshold | ✅ **HIT** - median distance **32**, 165 of 166 unpaired |
| 13 | Dates survive backup-of-a-backup nesting (predicted PASS) | ✅ **HIT** - S5's nested copies are exact duplicates of their originals and dedup to the same content; no mtime tier exists to damage them |

**Two clean misses, and both are worth more than the hits.** Prediction 6 was right about the
code and wrong about the corpus - the shape needed to reach that path does not exist in S1–S16,
which is a design note for soak nine rather than a defect. Prediction 7 was simply wrong: I
predicted a cost the product does not pay.

## 9. What broke, and what was checked that could have been dirty (Q805)

**Nothing in the product broke.** Read from the artifacts rather than the exit codes:

- **verify** reported 0/0/0/0 across 2,519 files - and the log was read, not the tick.
- **The source is byte-untouched**: `find /data/TruestillLibrary/Input -newermt` returns nothing
  after every run.
- **Apply wrote 2.9 GB from an 18.7 GB source** and the arithmetic reconciles: 15.0 GB was
  correctly not copied.
- **Two refusals fired correctly** and both were checked rather than assumed: backup onto a
  missing folder, and backup onto an unregistered one. The second's *message* is `(aij)`; the
  refusal itself was right.
- **The one undecodable file** (S12's truncated JPEG) was organized normally and named in
  *"photos whose contents could not be decoded: 1"* - the never-silent rule holding on the exact
  file planted to test it.

⚠ **What could have been dirty and was not**: no false perceptual pair (§5), no collision
mis-naming (one `_1`, correct), no category churn between preview and apply (identical counts),
and no drive-identity mint on the backup target (it refused until registered).

## 10. What was NOT run

`reclaim`, `migrate-layout`, `undo-organize`, `clean-empty`, the dates rescue flow, trips and
event naming, `ingest`, and **every app screen** - the browser lane was not run. S9's case
collision is present in the corpus and **unobservable on ext4**; it is asserted only where a
case-insensitive filesystem exists, and CI's macOS lane is where that assertion runs.

⚠ **And the honest limit stands unchanged** ([`soak-seven-plan.md`](soak-seven-plan.md)): this is
the mess we could imagine from what a handful of people wrote in public forums. **S6's crash-rescue
population under-tests itself** - every `.chk` here is a copy of a photograph that also exists
under a proper name, so nothing was lost when they were skipped. A real chkdsk recovery has
`.chk` files with **no** twin, and that corpus has not been built.
